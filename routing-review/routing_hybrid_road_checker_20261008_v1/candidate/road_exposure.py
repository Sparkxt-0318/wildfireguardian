"""Rational outward spatial bounds for the declared finite-source model.

No quadrature or sampled peak decides acceptance. All geometry, transformed
footprints, source-time partitions and proof arithmetic use Fraction. The
intensity is the original resolved scalar floating-point intensity, interpreted
as an exact coefficient. This is a model-relative contract, not field evidence.
"""
from __future__ import annotations

from fractions import Fraction as F
from bisect import bisect_right
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

DEFAULT_SETTINGS = {
    "version": "wfg.road.bounds.settings/1",
    "sqrt_bits": 80,
    "atan_argument_bits": 56,
    "atan_terms": 20,
    "machin_terms": 32,
    "receiver_span_m": 32,
    "wall_s": 30.0,
    "max_spatial_slabs": 4096,
    "max_corner_evaluations": 65536,
}


class BoundLimit(RuntimeError):
    pass


def reject_masked(value):
    """Never let np.asarray discard unknown entries carried by a mask."""
    if np.ma.isMaskedArray(value) or np.ma.is_masked(value):
        raise ValueError("masked values require explicit unsupported handling")
    if isinstance(value, dict):
        for child in value.values():
            reject_masked(child)
    elif isinstance(value,(list,tuple)):
        for child in value:
            reject_masked(child)


def rational(value):
    reject_masked(value)
    if isinstance(value, F):
        return value
    if isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)):
        return F(int(value))
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("finite numeric value required")
    return F(value)


def outward_float(value, upper):
    result = float(value)
    if not math.isfinite(result):
        return result
    if (upper and F(result) < value) or (not upper and F(result) > value):
        result = math.nextafter(result, math.inf if upper else -math.inf)
    return result


def _series_atan(value, terms):
    """Alternating-series enclosure for 0<=value<=1 (including zero)."""
    if not 0 <= value <= 1:
        raise ValueError("atan series argument outside convergence domain")
    total, power, squared = F(0), value, value * value
    sign = 1
    for k in range(terms):
        total += sign * power / (2*k+1)
        power *= squared
        sign *= -1
    next_sum = total + sign * power / (2*terms+1)
    return min(total, next_sum), max(total, next_sum)


class RationalKernel:
    def __init__(self, height, settings, guard=None):
        self.h = rational(height)
        if self.h <= 0:
            raise ValueError("positive resolved source/receiver height separation required")
        self.settings = dict(settings)
        self.guard = guard
        self.corner_cache = {}
        self.corner_evaluations = 0
        self.corner_evaluation_limit = self.settings["max_corner_evaluations"]
        a = _series_atan(F(1,5), self.settings["machin_terms"])
        b = _series_atan(F(1,239), self.settings["machin_terms"])
        self.pi = (16*a[0]-4*b[1], 16*a[1]-4*b[0])
        if not 3 < self.pi[0] <= self.pi[1] < 4:
            raise ValueError("invalid Machin enclosure")

    def sqrt_bounds(self, value):
        value = rational(value)
        if value < 0:
            raise ValueError("negative square root")
        scale = 1 << self.settings["sqrt_bits"]
        # isqrt(floor(q*S²)) equals floor(sqrt(q)*S).
        m = math.isqrt((value.numerator * scale * scale)//value.denominator)
        lower = F(m,scale)
        upper = lower if lower*lower == value else F(m+1,scale)
        return lower, upper

    def _dyadic(self, value, upper):
        scale = 1 << self.settings["atan_argument_bits"]
        numerator = value.numerator * scale
        n = (numerator + value.denominator - 1)//value.denominator if upper else numerator//value.denominator
        return F(n,scale)

    def atan_bounds(self, value):
        value = rational(value)
        if value < 0:
            low,high = self.atan_bounds(-value)
            return -high,-low
        if value > 1:
            low,high = self.atan_bounds(1/value)
            return self.pi[0]/2-high,self.pi[1]/2-low
        # atan(z)=2 atan(z/(1+sqrt(1+z²))). The reduced argument
        # is at most sqrt(2)-1; rational dyadic rounding is outward.
        root_low,root_high = self.sqrt_bounds(1+value*value)
        low = self._dyadic(value/(1+root_high),False)
        high = self._dyadic(value/(1+root_low),True)
        return (2*_series_atan(low,self.settings["atan_terms"])[0],
                2*_series_atan(high,self.settings["atan_terms"])[1])

    def corner(self, x, y):
        x,y = rational(x),rational(y)
        key=(x,y)
        if key not in self.corner_cache:
            if self.guard is not None:
                self.guard()
            if self.corner_evaluations >= self.corner_evaluation_limit:
                raise BoundLimit("CORNER_CAP")
            self.corner_evaluations += 1
            if x == 0 or y == 0:
                value=(F(0),F(0))
            else:
                low,high=self.sqrt_bounds(x*x+y*y+self.h*self.h)
                magnitude=abs(x*y)
                angle_low=self.atan_bounds(magnitude/(self.h*high))[0]
                angle_high=self.atan_bounds(magnitude/(self.h*low))[1] if low else self.pi[1]/2
                value=(angle_low,angle_high) if x*y>0 else (-angle_high,-angle_low)
            self.corner_cache[key]=value
        return self.corner_cache[key]

    def rectangle(self, x0,x1,y0,y1):
        if x0>=x1 or y0>=y1:
            return F(0),F(0)
        a,b,c,d=(self.corner(x1,y1),self.corner(x0,y1),self.corner(x1,y0),self.corner(x0,y0))
        numerator_low=a[0]-b[1]-c[1]+d[0]
        numerator_high=a[1]-b[0]-c[0]+d[1]
        low=max(F(0),numerator_low/(4*self.pi[1]))
        high=min(F(1,2),max(F(0),numerator_high)/(4*self.pi[0]))
        if low>high:
            raise ArithmeticError("rectangle interval reversed")
        return low,high

    def source_receiver_box(self, source, receiver):
        sx0,sx1,sy0,sy1=source
        rx0,rx1,ry0,ry1=receiver
        # Every R-x contains the intersection box and lies within the union box.
        inner=(sx0-rx0,sx1-rx1,sy0-ry0,sy1-ry1)
        outer=(sx0-rx1,sx1-rx0,sy0-ry1,sy1-ry0)
        return self.rectangle(*inner)[0], self.rectangle(*outer)[1]


class RoadExposure:
    schema = "wfg.road.exposure.rational/1"

    def __init__(self, ignition_time_s, current_active, config, affine_transform,
                 scenario_ids=None, support=None, settings=None,
                 evidence_class="RESEARCH_CONSTRUCTION"):
        reject_masked((ignition_time_s,current_active,config,affine_transform,scenario_ids,support,settings))
        self.config=dict(config)
        self.settings={**DEFAULT_SETTINGS,**(settings or {})}
        for name in ("sqrt_bits","atan_argument_bits","atan_terms","machin_terms","max_spatial_slabs","max_corner_evaluations"):
            if type(self.settings[name]) is not int or self.settings[name]<1:
                raise ValueError("positive integer proof/cap settings required")
        if rational(self.settings["receiver_span_m"])<=0 or rational(self.settings["wall_s"])<=0:
            raise ValueError("positive receiver span and wall cap required")
        events=np.asarray(ignition_time_s)
        current=np.asarray(current_active)
        if events.ndim!=3 or min(events.shape)<1 or current.shape!=events.shape[1:] or current.dtype!=np.bool_:
            raise ValueError("events [S,H,W] and Boolean current grid required")
        if np.any(np.isnan(events)) or np.any(events<0) or np.isfinite(events[:,current]).any():
            raise ValueError("invalid events or overlapping current/new sources")
        self.scenario_count,self.height,self.width=events.shape
        self.ids=list(scenario_ids) if scenario_ids is not None else ["road:"+str(s) for s in range(self.scenario_count)]
        if len(self.ids)!=self.scenario_count or len(set(self.ids))!=len(self.ids):
            raise ValueError("unique member IDs required")
        self.horizon=rational(self.config["horizon_s"])
        self.duration=rational(self.config["burning_duration_s"])
        self.remaining=rational(self.config["initial_remaining_s"])
        if not 0<=self.remaining<=self.duration or self.duration<=0 or self.horizon<=0:
            raise ValueError("invalid phase/horizon")
        self.current=set(np.flatnonzero(current.ravel()).tolist())
        self.events=[]
        self.birth_times=[]
        self.birth_cells=[]
        for s in range(self.scenario_count):
            row={int(i):rational(t) for i,t in enumerate(events[s].ravel()) if math.isfinite(float(t))}
            if any(t>=self.horizon for t in row.values()):
                raise ValueError("finite ignition outside native horizon")
            self.events.append(row)
            ordered=sorted((t,i) for i,t in row.items())
            self.birth_times.append([t for t,i in ordered])
            self.birth_cells.append([i for t,i in ordered])
        self.expiry_times=[[t+self.duration for t in times] for times in self.birth_times]
        self.unsupported=[]
        if evidence_class!="RESEARCH_CONSTRUCTION" or self.config.get("version")!="wfg.hazard.construction/1":
            self.unsupported.append("COMPLETE_DECLARED_RESEARCH_SOURCE_LAW_REQUIRED")
        if support is None or np.asarray(support).dtype!=np.bool_ or not np.asarray(support).all():
            self.unsupported.append("UNKNOWN_SOURCE_SUPPORT")
        elif np.asarray(support).shape not in {(self.height,self.width),(self.scenario_count,self.height,self.width)}:
            raise ValueError("source support must be [H,W] or [S,H,W]")
        affine=tuple(rational(x) for x in affine_transform)
        if len(affine)!=6:
            raise ValueError("six affine coefficients required")
        a,b,c,d,e,f=affine
        if b!=0 or d!=0 or a==0 or e==0:
            self.unsupported.append("ONLY_NONDEGENERATE_AXIS_ALIGNED_AFFINE")
        self.affine=affine
        self.rectangles=[]
        for row in range(self.height):
            for col in range(self.width):
                x0,x1=c+col*a,c+(col+1)*a
                y0,y1=f+row*e,f+(row+1)*e
                self.rectangles.append((min(x0,x1),max(x0,x1),min(y0,y1),max(y0,y1)))
        self.domain=(min(c,c+self.width*a),max(c,c+self.width*a),min(f,f+self.height*e),max(f,f+self.height*e))
        # Preserve the original resolved intensity convention, then treat that
        # scalar coefficient exactly. Maps are unsupported rather than broadcast.
        numeric_keys=("fuel_load_kg_m2","heat_of_combustion_j_kg","consumed_fraction","radiative_fraction",
                      "atmospheric_transmissivity","emission_height_m","receiver_height_m")
        if any(np.asarray(self.config[k]).ndim!=0 for k in numeric_keys):
            raise ValueError("only scalar physical parameters supported")
        sys.path.insert(0,str(Path(__file__).resolve().parent/"mentor_runtime"))
        from expected_heat_flux.model import CombustionParameters
        combustion=CombustionParameters(fuel_load_kg_m2=self.config["fuel_load_kg_m2"],
                  heat_of_combustion_j_kg=self.config["heat_of_combustion_j_kg"],
                  burning_duration_s=self.config["burning_duration_s"],consumed_fraction=self.config["consumed_fraction"])
        rad,tau=float(self.config["radiative_fraction"]),float(self.config["atmospheric_transmissivity"])
        if not 0<=rad<=1 or not 0<=tau<=1:
            raise ValueError("fraction/transmissivity outside [0,1]")
        self.density=rational(float(combustion.heat_release_rate_density_w_m2)*rad*tau)
        self.height_separation=rational(float(self.config["emission_height_m"])-float(self.config["receiver_height_m"]))
        if self.height_separation<=0:
            self.unsupported.append("POSITIVE_HEIGHT_SEPARATION_REQUIRED")
        self.global_flux=self.density/2
        self.kernel=RationalKernel(self.height_separation if self.height_separation>0 else F(1),self.settings,self._guard)
        self.spatial_cache={}
        self.provenance={"source_histories_changed":False,"evidence_class":evidence_class}
        self._started=None
        self._deadline=None

    @classmethod
    def from_case(cls, case_dir, settings=None):
        case_dir=Path(case_dir)
        report=json.loads((case_dir/"REPORT.json").read_text())
        path=case_dir/"constructed_arrays.npz"
        with np.load(path,allow_pickle=False) as arrays:
            support=arrays["support"]
            # Source support is complete only if every represented time is complete.
            source_support=support.all(axis=1) if support.ndim==4 else support
            out=cls(arrays["ignition_time_s"],arrays["current_active"],report["native_metadata"]["construction"]["assumptions"],
                    report["native_metadata"]["affine_transform"],list(report["rows"][0]["request"]["incurred"]),source_support,settings)
        out.provenance.update({"case_directory":str(case_dir),"source_history_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                               "assumption_id":report["assumption_id"]})
        return out

    def _guard(self):
        if self._deadline is not None and time.perf_counter()>=self._deadline:
            raise BoundLimit("WALL_CAP")

    def _active(self,s,t):
        born=bisect_right(self.birth_times[s],t)
        expired=bisect_right(self.expiry_times[s],t)
        out=set(self.birth_cells[s][expired:born])
        if t<self.remaining:
            out.update(self.current)
        return out

    def _point(self,leg,t):
        if leg["end"]==leg["start"]:
            return leg["p0"]
        u=(t-leg["start"])/(leg["end"]-leg["start"])
        return tuple(x+(y-x)*u for x,y in zip(leg["p0"],leg["p1"]))

    def _inside(self,point):
        x0,x1,y0,y1=self.domain
        return x0<=point[0]<=x1 and y0<=point[1]<=y1

    def _cells(self,point):
        # Closed source footprints; shared-edge/corner contact checks neighbors.
        x,y=point
        a,_,c,_,e,f=self.affine
        u,v=(x-c)/a,(y-f)/e
        col,row=u.numerator//u.denominator,v.numerator//v.denominator
        cols=[col-1,col] if u.denominator==1 else [col]
        rows=[row-1,row] if v.denominator==1 else [row]
        return {r*self.width+k for r in rows for k in cols if 0<=r<self.height and 0<=k<self.width}

    def _flux(self,active,box):
        lows,highs=[],[]
        for indices in active:
            low,high=F(0),F(0)
            for i in sorted(indices):
                key=(i,box)
                if key not in self.spatial_cache:
                    self.spatial_cache[key]=self.kernel.source_receiver_box(self.rectangles[i],box)
                lo,hi=self.spatial_cache[key]
                low+=lo
                high+=hi
            # Original active cell footprints are disjoint up to area-zero edges.
            # Their sum integrates a subset of the plane, irrespective of overlap
            # among the expanded outer bounding rectangles.
            lows.append(low*self.density)
            highs.append(min(high,F(1,2))*self.density)
        return lows,highs

    def _geometry_cuts(self,leg):
        a,b=leg["start"],leg["end"]
        cuts={a,b}
        if a==b:
            return [a]
        ac,_,cx,_,ae,cy=self.affine
        for axis,lines in ((0,(cx+i*ac for i in range(self.width+1))),
                           (1,(cy+i*ae for i in range(self.height+1)))):
            delta=leg["p1"][axis]-leg["p0"][axis]
            if delta:
                for line in lines:
                    u=(line-leg["p0"][axis])/delta
                    if 0<u<1:
                        cuts.add(a+(b-a)*u)
        extent=max(abs(y-x) for x,y in zip(leg["p0"],leg["p1"]))
        ratio=extent/rational(self.settings["receiver_span_m"])
        count=max(1,(ratio.numerator+ratio.denominator-1)//ratio.denominator)
        if count>self.settings["max_spatial_slabs"]:
            raise BoundLimit("SPATIAL_SLAB_CAP")
        cuts.update(a+(b-a)*F(i,count) for i in range(1,count))
        return sorted(cuts)

    def _cuts(self,leg,geometry_cuts):
        a,b=leg["start"],leg["end"]
        cuts=set(geometry_cuts)
        for times in self.birth_times+self.expiry_times:
            left,right=bisect_right(times,a),bisect_right(times,b)
            cuts.update(t for t in times[left:right] if t<b)
        if a<self.remaining<b:
            cuts.add(self.remaining)
        return sorted(cuts)

    def _geometry_box(self,leg,geometry_cuts,t):
        if len(geometry_cuts)==1:
            point=leg["p0"]
            return (point[0],point[0],point[1],point[1])
        i=min(len(geometry_cuts)-2,max(0,bisect_right(geometry_cuts,t)-1))
        pa,pb=self._point(leg,geometry_cuts[i]),self._point(leg,geometry_cuts[i+1])
        return min(pa[0],pb[0]),max(pa[0],pb[0]),min(pa[1],pb[1]),max(pa[1],pb[1])

    def _normalise(self,legs):
        reject_masked(legs)
        result=[]
        previous_end=None
        for item in legs:
            a,b=rational(item["start"]),rational(item["end"])
            p0=tuple(rational(x) for x in item["p0"])
            p1=tuple(rational(x) for x in item.get("p1",item["p0"]))
            if len(p0)!=2 or len(p1)!=2 or not 0<=a<=b<=self.horizon:
                raise ValueError("finite 2D endpoints and covered times required")
            if previous_end is not None and a<previous_end:
                raise ValueError("legs must be chronologically nonoverlapping")
            if a==b and p0!=p1:
                raise ValueError("instantaneous leg cannot move")
            if item.get("kind","").upper() in {"WAIT","DWELL"} and p0!=p1:
                raise ValueError("wait/dwell must have identical actual endpoints")
            result.append({"start":a,"end":b,"p0":p0,"p1":p1,"kind":item.get("kind","EDGE")})
            previous_end=b
        if not result:
            raise ValueError("at least one occupancy leg required")
        return result

    def point_bound(self,x,y,t,**gate):
        return self.trajectory_bound([{"start":t,"end":t,"p0":[x,y],"p1":[x,y],"kind":"POINT"}],**gate)

    def trajectory_bound(self,legs,peak_budget_kw_m2=None,dose_budget_kj_m2=None,incurred=None,wall_s=None,deadline=None):
        legs=self._normalise(legs)
        self._started=time.perf_counter()
        duration=float(self.settings["wall_s"] if wall_s is None else wall_s)
        if not math.isfinite(duration) or duration<0:
            raise ValueError("nonnegative finite per-call wall cap required")
        self._deadline=self._started+duration
        if deadline is not None:
            if not math.isfinite(float(deadline)):
                raise ValueError("finite monotonic deadline required")
            self._deadline=min(self._deadline,float(deadline))
        initial_corners=self.kernel.corner_evaluations
        self.kernel.corner_evaluation_limit=initial_corners+self.settings["max_corner_evaluations"]
        n=self.scenario_count
        incurred={} if incurred is None else incurred
        doses_low=[rational(incurred.get(mid,0))*1000 for mid in self.ids]
        doses_high=list(doses_low)
        if any(x<0 for x in doses_low):
            raise ValueError("negative incurred dose")
        peaks_low=[F(0)]*n
        peaks_high=[F(0)]*n
        contacts=[False]*n
        contact_duration=[F(0)]*n
        unsupported=list(self.unsupported)
        if any(not self._inside(p) for leg in legs for p in (leg["p0"],leg["p1"])):
            unsupported.append("TRAJECTORY_OUTSIDE_SOURCE_GRID")
        complete=False
        cap=None
        completed_duration=F(0)
        total_duration=sum((leg["end"]-leg["start"] for leg in legs),F(0))
        slab_count=0
        try:
            if not unsupported:
                for leg in legs:
                    geometry_cuts=self._geometry_cuts(leg)
                    cuts=self._cuts(leg,geometry_cuts)
                    # Point states at every cut cover endpoint ignitions and
                    # closed contact at cell crossings. Slabs cover all interior
                    # positions and the one-sided limits before source extinction.
                    for t in cuts:
                        self._guard()
                        point=self._point(leg,t)
                        active=[self._active(s,t) for s in range(n)]
                        lo,hi=self._flux(active,self._geometry_box(leg,geometry_cuts,t))
                        cellset=self._cells(point)
                        for s in range(n):
                            peaks_low[s]=max(peaks_low[s],lo[s])
                            peaks_high[s]=max(peaks_high[s],hi[s])
                            contacts[s] |= bool(active[s]&cellset)
                    for a,b in zip(cuts[:-1],cuts[1:]):
                        self._guard()
                        slab_count+=1
                        if slab_count>self.settings["max_spatial_slabs"]:
                            raise BoundLimit("SPATIAL_SLAB_CAP")
                        box=self._geometry_box(leg,geometry_cuts,(a+b)/2)
                        active=[self._active(s,(a+b)/2) for s in range(n)]
                        lo,hi=self._flux(active,box)
                        cellset=self._cells(self._point(leg,(a+b)/2))
                        for s in range(n):
                            doses_low[s]+=lo[s]*(b-a)
                            doses_high[s]+=hi[s]*(b-a)
                            peaks_low[s]=max(peaks_low[s],lo[s])
                            peaks_high[s]=max(peaks_high[s],hi[s])
                            if active[s]&cellset:
                                contacts[s]=True
                                contact_duration[s]+=b-a
                        completed_duration+=b-a
                complete=True
        except BoundLimit as error:
            cap=str(error)
            # Complete the uncomputed radiation part with a proved global bound.
            # Contact remains unknown there, so an incomplete check cannot accept.
            for s in range(n):
                doses_high[s]+=self.global_flux*(total_duration-completed_duration)
                peaks_high[s]=max(peaks_high[s],self.global_flux)
        peak_limit=None if peak_budget_kw_m2 is None else rational(peak_budget_kw_m2)*1000
        dose_limit=None if dose_budget_kj_m2 is None else rational(dose_budget_kj_m2)*1000
        if (peak_limit is not None and peak_limit<0) or (dose_limit is not None and dose_limit<0):
            raise ValueError("nonnegative budgets required")
        members=[]
        for s,mid in enumerate(self.ids):
            if unsupported:
                status="UNSUPPORTED"
            elif contacts[s] or (peak_limit is not None and peaks_low[s]>peak_limit) or (dose_limit is not None and doses_low[s]>dose_limit):
                status="DEFINITE_REJECT"
            elif not complete:
                status="UNRESOLVED"
            elif (peak_limit is not None and peaks_high[s]>peak_limit) or (dose_limit is not None and doses_high[s]>dose_limit):
                status="UNRESOLVED"
            else:
                status="CERTIFIED_ACCEPT" if peak_limit is not None or dose_limit is not None else "BOUNDED"
            members.append({"id":mid,"status":status,"support":not bool(unsupported),
                "peak_lower_w_m2":None if unsupported else outward_float(peaks_low[s],False),
                "peak_upper_w_m2":None if unsupported else outward_float(peaks_high[s],True),
                "peak_lower_kw_m2":None if unsupported else outward_float(peaks_low[s]/1000,False),
                "peak_upper_kw_m2":None if unsupported else outward_float(peaks_high[s]/1000,True),
                "dose_lower_kj_m2":None if unsupported else outward_float(doses_low[s]/1000,False),
                "dose_upper_kj_m2":None if unsupported else outward_float(doses_high[s]/1000,True),
                "flame_contact":bool(contacts[s]) if complete or contacts[s] else None,
                "contact_duration_s":outward_float(contact_duration[s],False) if complete else None,
                "bound_certified":not bool(unsupported),"contact_complete":complete})
        statuses={r["status"] for r in members}
        status=("UNSUPPORTED" if "UNSUPPORTED" in statuses else "DEFINITE_REJECT" if "DEFINITE_REJECT" in statuses else
                "UNRESOLVED" if "UNRESOLVED" in statuses else "CERTIFIED_ACCEPT" if "CERTIFIED_ACCEPT" in statuses else "BOUNDED")
        result={"schema":self.schema,"status":status,"per_member":members,"complete":complete,"cap":cap,
                "unsupported_reasons":unsupported,"elapsed_s":time.perf_counter()-self._started,
                "spatial_slabs":slab_count,"corner_evaluations":self.kernel.corner_evaluations-initial_corners,
                "settings":dict(self.settings),"provenance":dict(self.provenance),
                "resolved_radiant_density_w_m2":outward_float(self.density,True),
                "resolved_height_separation_m":outward_float(self.height_separation,True),
                "proof_flags":{"rational_geometry_and_time":True,"outward_pi_sqrt_atan":True,
                     "positive_translated_footprint_enclosure":True,"disjoint_original_source_plane_cap":True,
                     "closed_occupancy_right_continuous_sources":True,"closed_source_footprints":True,
                     "all_interior_and_one_sided_peaks_enclosed":not bool(unsupported),
                     "partial_cap_uses_global_radiation_upper":cap is not None,
                     "sampled_peak_or_quadrature_acceptance":False,"physical_validation":False},
                "scope":"exact represented geometry/events and original resolved scalar intensity; conditional finite-source model, not field safety"}
        self._started=None
        self._deadline=None
        return result
