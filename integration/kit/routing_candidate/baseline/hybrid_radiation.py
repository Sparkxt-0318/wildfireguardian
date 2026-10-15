"""Compatible radial/analytic enclosures over immutable complete source histories.

No source law or budget change; radiation-only API. Analytic bounds use the
unchanged rational translated-rectangle kernel. See HYBRID_RADIATION_SPEC.md.
"""
from __future__ import annotations
from fractions import Fraction as F
import math,sys,time
import numpy as np
from radiation_bounds import RadiationBounds,DEFAULT_SETTINGS as RADIAL_SETTINGS,interval,positive_sum
from road_exposure import RationalKernel,DEFAULT_SETTINGS as RATIONAL_SETTINGS,BoundLimit,rational,outward_float

DEFAULT_SETTINGS={**RADIAL_SETTINGS,'version':'wfg.radiation.hybrid/1',
 'analytic_near_height_multiple':16,'analytic_sparse_source_limit':8,
 'max_analytic_corner_evaluations':65536,
 'analytic_sqrt_bits':80,'analytic_atan_argument_bits':56,'analytic_atan_terms':20,'analytic_machin_terms':32}

class HybridRadiationBounds(RadiationBounds):
    schema='wfg.radiation.bounds.hybrid/1'
    def __init__(self,ignition_time_s,current_active,config,affine_transform,scenario_ids=None,support=None,
                 settings=None,evidence_class='RESEARCH_CONSTRUCTION'):
        settings={**DEFAULT_SETTINGS,**(settings or {})}
        for key in ('analytic_sparse_source_limit','max_analytic_corner_evaluations','analytic_sqrt_bits','analytic_atan_argument_bits','analytic_atan_terms','analytic_machin_terms'):
            if type(settings[key]) is not int or settings[key]<1:raise ValueError('positive integer analytic setting')
        if rational(settings['analytic_near_height_multiple'])<=0:raise ValueError('positive analytic distance factor')
        super().__init__(ignition_time_s,current_active,config,affine_transform,scenario_ids,support,settings,evidence_class)
        analytic_settings={**RATIONAL_SETTINGS,**{key:settings['analytic_'+key] for key in ('sqrt_bits','atan_argument_bits','atan_terms','machin_terms')},'max_corner_evaluations':settings['max_analytic_corner_evaluations']}
        self._analytic_kernel=RationalKernel(self._h if self._h>0 else F(1),analytic_settings,self._guard)
        self._potential=np.zeros(len(self._rectangles),bool)
        if self._remaining>0:self._potential[list(self._current)]=True
        for events in self._events:
            for cell,_ in events:self._potential[cell]=True
        self._potential.flags.writeable=False
        self._potential_count=int(self._potential.sum());self._analytic_source_bounds=0
        self._radial_tile_sources=0;self._analytical_selection_box_count=0

    def cache_info(self):
        out=super().cache_info()
        out.update({'analytic_corner_entries':len(self._analytic_kernel.corner_cache),
            'analytic_corner_evaluations_lifetime':self._analytic_kernel.corner_evaluations,
            'analytic_corner_cache_shallow_bytes':sys.getsizeof(self._analytic_kernel.corner_cache)+sum(sys.getsizeof(k)+sys.getsizeof(v) for k,v in self._analytic_kernel.corner_cache.items()),
            'analytic_byte_scope':'Python containers/keys/direct values; nested Fraction payloads excluded; process RSS includes them',
            'ever_active_source_count':self._potential_count})
        return out

    def _coefficients(self,box):
        key=(self.cache_identity,box)
        if key in self._cache:self._hits+=1;return self._cache[key]
        self._guard();self._misses+=1
        lo,hi,dx,dy=self._radial(self._source_lo,self._source_hi,self._areas,box)
        self._source_bounds+=len(self._rectangles)
        # Geometry-only policy. The gap lower bound can overselect analytic
        # work, but cannot invalidate either enclosure. Sparse realizations use
        # analytic bounds for every explicitly ever-active source.
        sparse=self._potential_count<=self.settings['analytic_sparse_source_limit']
        radius=rational(self.settings['analytic_near_height_multiple'])*self._h
        cutoff=outward_float(radius,True)
        analytic=np.flatnonzero(self._potential & (True if sparse else (np.maximum(dx,dy)<=cutoff)))
        tile_indices=np.flatnonzero(self._potential & (np.maximum(dx,dy)<float(self.settings['near_distance_m'])))
        tile_indices=np.setdiff1d(tile_indices,analytic,assume_unique=True)
        n=self.settings['source_tiles_per_axis']
        if n>1 and tile_indices.size:
            tiles=[];areas=[]
            for i in tile_indices:
                self._guard();r=self._rectangles[i];area=(r[1]-r[0])*(r[3]-r[2])/n/n
                for x in range(n):
                    for y in range(n):
                        if y%64==0:self._guard()
                        tiles.append((r[0]+(r[1]-r[0])*F(x,n),r[0]+(r[1]-r[0])*F(x+1,n),
                                      r[2]+(r[3]-r[2])*F(y,n),r[2]+(r[3]-r[2])*F(y+1,n)))
                        areas.append(interval(area))
            sl=np.array([[interval(v)[0] for v in r] for r in tiles]);sh=np.array([[interval(v)[1] for v in r] for r in tiles])
            tl,th,_,_=self._radial(sl,sh,np.array(areas),box)
            self._tile_bounds+=len(tiles);self._radial_tile_sources+=len(tile_indices)
            for j,i in enumerate(tile_indices):
                lo[i]=max(lo[i],positive_sum(tl[j*n*n:(j+1)*n*n],False))
                hi[i]=min(hi[i],positive_sum(th[j*n*n:(j+1)*n*n],True))
        if analytic.size:self._analytical_selection_box_count+=1
        for i in analytic:
            self._guard();a,b=self._analytic_kernel.source_receiver_box(self._rectangles[i],box)
            lower=outward_float(a*self._density,False);upper=outward_float(b*self._density,True)
            lo[i]=max(lo[i],lower);hi[i]=min(hi[i],upper);self._analytic_source_bounds+=1
        # Exactly absent source phases are known from complete immutable
        # realization, not inferred from missing observations/probabilities.
        lo[~self._potential]=0.;hi[~self._potential]=0.
        hi=np.minimum(hi,outward_float(self._density/2,True))
        if np.any(lo>hi):raise ArithmeticError('INCOMPATIBLE_SAME_LAW_ENCLOSURES')
        lo.flags.writeable=False;hi.flags.writeable=False;self._guard()
        # Commit only the completed compatible intersection: no radial-only
        # partial cache entry can bypass analytic work after a cap.
        self._cache[key]=(lo,hi);return lo,hi

    def trajectory_bound(self,legs,**kwargs):
        start=time.perf_counter();corners=self._analytic_kernel.corner_evaluations
        sources=self._analytic_source_bounds;tile_sources=self._radial_tile_sources;boxes=self._analytical_selection_box_count
        self._analytic_kernel.corner_evaluation_limit=corners+self.settings['max_analytic_corner_evaluations']
        result=super().trajectory_bound(legs,**kwargs)
        result.update({'schema':self.schema,'analytic_source_bounds':self._analytic_source_bounds-sources,
            'analytic_corner_evaluations':self._analytic_kernel.corner_evaluations-corners,
            'radial_tiled_sources':self._radial_tile_sources-tile_sources,
            'analytic_selected_receiver_boxes':self._analytical_selection_box_count-boxes,
            'hybrid_policy':{'close_gap_m':str(rational(self.settings['analytic_near_height_multiple'])*self._h),
                'sparse_realization':self._potential_count<=self.settings['analytic_sparse_source_limit'],
                'ever_active_source_count':self._potential_count,'no_distant_source_omission':True},
            'compatible_enclosure_intersection':True,'explicit_absence_is_not_missing_fill':True})
        result['proof_flags'].update({'same_law_rational_analytic_rectangle':True,'no_quadrature_acceptance':True})
        result['elapsed_s']=time.perf_counter()-start
        wall=kwargs.get('wall_s');wall=self.settings['wall_s'] if wall is None else wall
        external=kwargs.get('deadline');external=math.inf if external is None else external
        deadline=min(start+float(wall),float(external))
        if time.perf_counter()>=deadline:
            result.setdefault('checked_record_status',result['status']);result.update(status='UNRESOLVED',complete=False,cap='WALL_CAP_AFTER_HYBRID_RECORD')
        return result
