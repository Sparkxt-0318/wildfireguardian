"""Outward radial-tile bounds, exact represented source phases, whole receiver boxes.

Radiation-only result; complete mission/support/contact validation is the adapter's
responsibility. No sampled value decides acceptance. See RADIATION_SPEC.md.
"""
from __future__ import annotations
import hashlib,json,math,time,sys
from fractions import Fraction as F
from pathlib import Path
from types import MappingProxyType
from collections.abc import Mapping
import numpy as np
from road_exposure import RoadExposure,BoundLimit,rational,outward_float,reject_masked

DEFAULT_SETTINGS={'version':'wfg.radiation.radial.tiles/1','receiver_span_m':16,
 'source_tiles_per_axis':8,'near_distance_m':600,'wall_s':30.0,'max_spatial_slabs':4096,
 'max_refinement_levels':2}
NEG=-math.inf;POS=math.inf

def down(x):return np.nextafter(x,NEG)
def up(x):return np.nextafter(x,POS)
def addlo(a,b):return down(np.add(a,b))
def addhi(a,b):return up(np.add(a,b))
def mullo(a,b):return down(np.multiply(a,b))
def mulhi(a,b):return up(np.multiply(a,b))
def sublo(a,b):return down(np.subtract(a,b))
def subhi(a,b):return up(np.subtract(a,b))

def sqrt_bracket(x):
    """Candidate sqrt from host, bracket VERIFIED by interval squaring.

    Failed brackets use exact integer arithmetic, never trust a libm accuracy
    assumption. x is nonnegative represented binary64, possibly an ndarray.
    """
    a=np.asarray(x,dtype=np.float64)
    if np.any(a<0) or not np.isfinite(a).all():raise ValueError('finite positive sqrt input')
    z=np.sqrt(a);lo=np.maximum(0,down(down(z)));hi=up(up(z))
    ok=(mulhi(lo,lo)<=a)&(mullo(hi,hi)>=a)
    if not np.all(ok):
        lo=np.array(lo,copy=True);hi=np.array(hi,copy=True)
        for index in np.ndindex(a.shape):
            if not ok[index]:
                v=F(float(a[index]));scale=1<<100
                k=math.isqrt(v.numerator*scale*scale//v.denominator)
                l=F(k,scale);h=l if l*l==v else F(k+1,scale)
                lo[index]=outward_float(l,False);hi[index]=outward_float(h,True)
    return lo,hi

def interval(value):
    f=rational(value);return outward_float(f,False),outward_float(f,True)

def positive_sum(array,upper):
    """Vector reductions via pairwise directed addition, incl zero singleton."""
    a=np.asarray(array,dtype=np.float64).copy()
    if not a.size:return 0.0
    while a.size>1:
        n=a.size//2
        b=addhi(a[:2*n:2],a[1:2*n:2]) if upper else addlo(a[:2*n:2],a[1:2*n:2])
        a=np.concatenate((b,a[-1:])) if a.size%2 else b
    return max(0,float(a[0]))

class RadiationBounds:
    schema='wfg.radiation.bounds.radial/1'
    def __init__(self,ignition_time_s,current_active,config,affine_transform,
                 scenario_ids=None,support=None,settings=None,evidence_class='RESEARCH_CONSTRUCTION'):
        reject_masked((ignition_time_s,current_active,config,affine_transform,scenario_ids,support,settings))
        settings={**DEFAULT_SETTINGS,**(settings or {})}
        for k in ('source_tiles_per_axis','max_spatial_slabs','max_refinement_levels'):
            if type(settings[k]) is not int or settings[k]<1:raise ValueError('positive integer setting')
        for k in ('receiver_span_m','near_distance_m','wall_s'):
            if rational(settings[k])<=0:raise ValueError('positive setting')
        if (sys.float_info.radix!=2 or np.dtype(np.float64).itemsize!=8 or np.finfo(np.float64).eps!=2**-52
            or float(np.nextafter(np.float64(0),np.float64(1)))!=2**-1074
            or float(np.multiply(np.float64(2**-1022),np.float64(.5)))!=2**-1023):
            raise ValueError('binary64 runtime required')
        self.settings=MappingProxyType(dict(settings))
        # Inherited constructor validates source law. Its material content is
        # copied into tuples and read-only arrays before caller inputs can mutate.
        m=RoadExposure(np.array(ignition_time_s,copy=True),np.array(current_active,copy=True),dict(config),tuple(affine_transform),
                       list(scenario_ids) if scenario_ids is not None else None,np.array(support,copy=True) if support is not None else None)
        self._normalise=m._normalise;self._point=m._point;self._inside=m._inside
        self._rectangles=tuple(tuple(r) for r in m.rectangles);self._ids=tuple(m.ids)
        self._unsupported=tuple(m.unsupported);self._density=m.density;self._h=m.height_separation
        self._horizon=m.horizon;self._duration=m.duration;self._remaining=m.remaining
        self._current=tuple(sorted(m.current));self._events=tuple(tuple(sorted(r.items())) for r in m.events)
        self._domain=tuple(m.domain);self._cache={};self._hits=0;self._misses=0
        self._deadline=None;self._slabs=0;self._source_bounds=0;self._tile_bounds=0
        payload={'rectangles':[[str(v) for v in r] for r in self._rectangles],
          'events':[[[i,str(t)] for i,t in r] for r in self._events], 'current':self._current,
          'density':str(self._density),'height':str(self._h),'duration':str(self._duration),'remaining':str(self._remaining),
          'horizon':str(self._horizon),'ids':self._ids,'unsupported':self._unsupported,'settings':settings,'affine':[str(v) for v in m.affine],
          'all_source_config':{str(k):str(v) for k,v in sorted(dict(config).items())},'evidence_class':evidence_class}
        self.cache_identity=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        # pi uses the unchanged rational Machin enclosure; directed conversion.
        self._pi=(outward_float(m.kernel.pi[0],False),outward_float(m.kernel.pi[1],True))
        self._scalar_density=interval(self._density);self._scalar_h=interval(self._h)
        self._areas=[];self._source_lo=[];self._source_hi=[]
        for r in self._rectangles:
            self._source_lo.append([interval(v)[0] for v in r]);self._source_hi.append([interval(v)[1] for v in r])
            self._areas.append(interval((r[1]-r[0])*(r[3]-r[2])))
        self._source_lo=np.array(self._source_lo);self._source_hi=np.array(self._source_hi);self._areas=np.array(self._areas)
        for a in (self._source_lo,self._source_hi,self._areas):a.flags.writeable=False
        self._birth=[];self._expiry=[];self._possible=[]
        for events in self._events:
            b=np.full((len(self._rectangles),2),math.inf);e=np.full_like(b,math.inf)
            for i in self._current:b[i]=(0,0);e[i]=interval(self._remaining)
            for i,t in events:b[i]=interval(t);e[i]=interval(t+self._duration)
            possible=np.isfinite(b[:,0]);b.flags.writeable=False;e.flags.writeable=False;possible.flags.writeable=False
            self._birth.append(b);self._expiry.append(e);self._possible.append(possible)
        self._prepared_s=None

    @classmethod
    def from_case(cls,path,settings=None):
        path=Path(path);report=json.loads((path/'REPORT.json').read_text())
        with np.load(path/'constructed_arrays.npz',allow_pickle=False) as a:
            support=a['support'];support=support.all(axis=1) if support.ndim==4 else support
            return cls(a['ignition_time_s'],a['current_active'],report['native_metadata']['construction']['assumptions'],
                report['native_metadata']['affine_transform'],list(report['rows'][0]['request']['incurred']),support,settings)

    def _guard(self):
        if self._deadline is not None and time.perf_counter()>=self._deadline:raise BoundLimit('WALL_CAP')

    def cache_info(self):
        return {'identity':self.cache_identity,'entries':len(self._cache),'hits':self._hits,'misses':self._misses,
            'retained_numeric_bytes':sum(a.nbytes+b.nbytes for a,b in self._cache.values()),
            'source_numeric_bytes':sum(a.nbytes for a in (self._source_lo,self._source_hi,self._areas))+sum(a.nbytes for a in self._birth+self._expiry+self._possible),
            'scope':'numeric buffers only; Python object overhead covered by process RSS'}

    def _radial(self,sl,sh,areas,receiver):
        # sl/sh enclose exact source tile endpoints; receiver endpoints exact
        # Fraction are converted outward. Distance extrema are over whole boxes.
        rl=np.array([interval(v)[0] for v in receiver]);rh=np.array([interval(v)[1] for v in receiver])
        dx=np.maximum(0,np.maximum(sublo(sl[:,0],rh[1]),sublo(rl[0],sh[:,1])))
        dy=np.maximum(0,np.maximum(sublo(sl[:,2],rh[3]),sublo(rl[2],sh[:,3])))
        farx=np.maximum(np.maximum(np.abs(sublo(sl[:,0],rh[1])),np.abs(subhi(sh[:,0],rl[1]))),
                        np.maximum(np.abs(sublo(sl[:,1],rh[0])),np.abs(subhi(sh[:,1],rl[0]))))
        fary=np.maximum(np.maximum(np.abs(sublo(sl[:,2],rh[3])),np.abs(subhi(sh[:,2],rl[3]))),
                        np.maximum(np.abs(sublo(sl[:,3],rh[2])),np.abs(subhi(sh[:,3],rl[2]))))
        h0,h1=self._scalar_h
        d0=np.maximum(0,addlo(addlo(mullo(dx,dx),mullo(dy,dy)),mullo(h0,h0)))
        d1=addhi(addhi(mulhi(farx,farx),mulhi(fary,fary)),mulhi(h1,h1))
        root0=sqrt_bracket(d0)[0];root1=sqrt_bracket(d1)[1]
        den0=mullo(mullo(mullo(4.0,self._pi[0]),d0),root0)
        den1=mulhi(mulhi(mulhi(4.0,self._pi[1]),d1),root1)
        num0=mullo(mullo(self._scalar_density[0],areas[:,0]),h0)
        num1=mulhi(mulhi(self._scalar_density[1],areas[:,1]),h1)
        lo=np.maximum(0,down(np.divide(num0,den1)))
        den0=np.maximum(0,den0)
        hi=np.full_like(den0,outward_float(self._density/2,True))
        valid=den0>0
        hi[valid]=up(np.divide(num1[valid],den0[valid]))
        return lo,hi,dx,dy

    def _coefficients(self,box):
        key=(self.cache_identity,box)
        if key in self._cache:self._hits+=1;return self._cache[key]
        self._guard();self._misses+=1
        lo,hi,dx,dy=self._radial(self._source_lo,self._source_hi,self._areas,box)
        self._source_bounds+=len(self._rectangles)
        # Only geometry chooses near tiles; all sources, including distant
        # sources, remain explicitly present in coefficient vector.
        near=np.flatnonzero(np.maximum(dx,dy)<float(self.settings['near_distance_m']))
        n=self.settings['source_tiles_per_axis']
        if n>1 and near.size:
            tiles=[];areas=[]
            for i in near:
                self._guard();r=self._rectangles[i]
                area=(r[1]-r[0])*(r[3]-r[2])/n/n
                for x in range(n):
                    for y in range(n):
                        if y%64==0:self._guard()
                        tiles.append((r[0]+(r[1]-r[0])*F(x,n),r[0]+(r[1]-r[0])*F(x+1,n),
                                      r[2]+(r[3]-r[2])*F(y,n),r[2]+(r[3]-r[2])*F(y+1,n)))
                        areas.append(interval(area))
            sl=np.array([[interval(v)[0] for v in r] for r in tiles]);sh=np.array([[interval(v)[1] for v in r] for r in tiles])
            tl,th,_,_=self._radial(sl,sh,np.array(areas),box)
            self._tile_bounds+=len(tiles)
            for j,i in enumerate(near):
                lo[i]=max(lo[i],positive_sum(tl[j*n*n:(j+1)*n*n],False))
                hi[i]=min(hi[i],positive_sum(th[j*n*n:(j+1)*n*n],True))
        hi=np.minimum(hi,outward_float(self._density/2,True))
        lo.flags.writeable=False;hi.flags.writeable=False;self._guard()
        self._cache[key]=(lo,hi);return lo,hi

    def _pass(self,legs,span,incurred):
        count=len(self._ids);dl=np.array([interval(rational(incurred[mid])*1000)[0] for mid in self._ids]);dh=np.array([interval(rational(incurred[mid])*1000)[1] for mid in self._ids])
        pl=np.zeros(count);ph=np.zeros(count);total_sources=0
        for leg in legs:
            self._guard();extent=max(abs(v-u) for u,v in zip(leg['p0'],leg['p1']))
            n=max(1,math.ceil(extent/span));
            for k in range(n):
                self._guard();self._slabs+=1
                if self._slabs>self.settings['max_spatial_slabs']:raise BoundLimit('SPATIAL_SLAB_CAP')
                a=leg['start']+(leg['end']-leg['start'])*F(k,n);b=leg['start']+(leg['end']-leg['start'])*F(k+1,n)
                pa,pb=self._point(leg,a),self._point(leg,b)
                box=(min(pa[0],pb[0]),max(pa[0],pb[0]),min(pa[1],pb[1]),max(pa[1],pb[1]))
                cl,ch=self._coefficients(box);a0,a1=interval(a);b0,b1=interval(b)
                for s in range(count):
                    birth,expiry=self._birth[s],self._expiry[s];possible=self._possible[s]
                    # Endpoints included for peaks, half-open source activity.
                    any_active=possible&(birth[:,0]<=b1)&(expiry[:,1]>a0)
                    durationlo=np.zeros(len(cl));durationhi=np.zeros(len(cl))
                    if any_active.any():
                        idx=np.flatnonzero(any_active);total_sources+=idx.size
                        durationlo[idx]=np.maximum(0,sublo(np.minimum(b0,expiry[idx,0]),np.maximum(a1,birth[idx,1])))
                        durationhi[idx]=np.maximum(0,subhi(np.minimum(b1,expiry[idx,1]),np.maximum(a0,birth[idx,0])))
                        dl[s]=max(0,float(addlo(dl[s],positive_sum(np.maximum(0,mullo(cl[idx],durationlo[idx])),False))))
                        dh[s]=float(addhi(dh[s],positive_sum(mulhi(ch[idx],durationhi[idx]),True)))
                        ph[s]=max(ph[s],min(outward_float(self._density/2,True),positive_sum(ch[idx],True)))
                        start_active=idx[(birth[idx,1]<=a0)&(expiry[idx,0]>a1)]
                        if start_active.size:pl[s]=max(pl[s],positive_sum(cl[start_active],False))
        return dl,dh,pl,ph,total_sources

    def trajectory_bound(self,legs,peak_budget_kw_m2=None,dose_budget_kj_m2=None,incurred=None,wall_s=None,deadline=None):
        start=time.perf_counter();duration=float(self.settings['wall_s'] if wall_s is None else wall_s)
        if not math.isfinite(duration) or duration<0:raise ValueError('nonnegative finite wall cap')
        if deadline is not None and not math.isfinite(float(deadline)):raise ValueError('finite deadline')
        self._deadline=min(start+duration,float(deadline)) if deadline is not None else start+duration
        hits,misses=self._hits,self._misses;sources,tiles=self._source_bounds,self._tile_bounds;self._slabs=0;cap=None;levels=0;complete=False;record=None
        legs=self._normalise(legs);reject_masked(incurred)
        if incurred is None or set(incurred)!=set(self._ids):raise ValueError('explicit incurred dose for every member required')
        if any(rational(v)<0 for v in incurred.values()):raise ValueError('negative incurred')
        if peak_budget_kw_m2 is None or dose_budget_kj_m2 is None:raise ValueError('both declared budgets required')
        reject_masked((peak_budget_kw_m2,dose_budget_kj_m2))
        def budget(value):
            if isinstance(value,(bool,np.bool_)):raise ValueError('Boolean is not an exposure budget')
            result=rational(value)*1000
            if result<0:raise ValueError('negative budget')
            return result
        peak=budget(peak_budget_kw_m2)
        if isinstance(dose_budget_kj_m2,Mapping):
            if set(dose_budget_kj_m2)!=set(self._ids):raise ValueError('dose budget required for every exact member ID')
            doses=tuple(budget(dose_budget_kj_m2[mid]) for mid in self._ids)
        else:
            doses=(budget(dose_budget_kj_m2),)*len(self._ids)
        unsupported=list(self._unsupported)
        if any(not self._inside(p) for leg in legs for p in (leg['p0'],leg['p1'])):unsupported.append('OUTSIDE_SOURCE_GRID')
        status='UNRESOLVED';members=[]
        try:
            self._guard()
            if not unsupported:
                for level in range(self.settings['max_refinement_levels']):
                    levels=level+1
                    with np.errstate(over='raise',invalid='raise',divide='raise',under='ignore'):
                        record=self._pass(legs,rational(self.settings['receiver_span_m'])/2**level,incurred)
                    self._guard();complete=True
                    dl,dh,pl,ph,_=record
                    # Compare exact represented budgets, never rounded floats.
                    if any(F(float(l))>d or F(float(p))>peak for l,p,d in zip(dl,pl,doses)):status='DEFINITE_REJECT';break
                    if all(F(float(h))<=d and F(float(p))<=peak for h,p,d in zip(dh,ph,doses)):status='CERTIFIED_RADIATION';break
        except BoundLimit as e:cap=str(e);status='UNRESOLVED';complete=False
        except (FloatingPointError,OverflowError,ArithmeticError) as e:
            cap='NUMERICAL_RANGE_UNSUPPORTED:'+type(e).__name__;status='UNRESOLVED';complete=False
        if unsupported:status='UNRESOLVED'
        if record is not None:
            dl,dh,pl,ph,source_evals=record
            for i,mid in enumerate(self._ids):members.append({'id':mid,'dose_lower_kj_m2':outward_float(F(float(dl[i]))/1000,False),'dose_upper_kj_m2':outward_float(F(float(dh[i]))/1000,True),'peak_lower_kw_m2':outward_float(F(float(pl[i]))/1000,False),'peak_upper_kw_m2':outward_float(F(float(ph[i]))/1000,True)})
        else:source_evals=0
        result={'schema':self.schema,'status':status,'complete':complete,'cap':cap,'unsupported_reasons':unsupported,'per_member':members,
            'elapsed_s':time.perf_counter()-start,'spatial_slabs':self._slabs,'refinement_levels':levels,'source_active_slab_pairs':source_evals,
            'cache_hits':self._hits-hits,'cache_misses':self._misses-misses,'source_geometry_bounds':self._source_bounds-sources,'source_tile_bounds':self._tile_bounds-tiles,'cache':self.cache_info(),'settings':dict(self.settings),'resolved_dose_budgets_kj_m2':{mid:str(d/1000) for mid,d in zip(self._ids,doses)},
            'proof_flags':{'radial_monotonicity_over_whole_source_receiver_boxes':True,'all_sources_bounded':True,'source_phase_overlap_outward':True,'sqrt_brackets_verified':True,'elementary_binary64_outward':True,'sampled_peak_acceptance':False,'physical_validation':False},
            'scope':'radiation only; root must establish complete supported contact clearance and mission coverage'}
        # A late complete certificate is retained only as a checked record.
        if time.perf_counter()>=self._deadline:
            result['checked_record_status']=result['status'];result['status']='UNRESOLVED';result['complete']=False;result['cap']='WALL_CAP_AFTER_CHECK'
        self._deadline=None;return result
