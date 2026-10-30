"""Analytic cases, topology and randomized enclosure regression."""
from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import wfg_flamefront as W
from wfg_flamefront.solidflame import polygon_view_factor,finite_panel_view_factor,infinite_wall_view_factor
from wfg_flamefront.intensity import fireline_intensity,flame_length,flame_geometry


class ViewFactors(unittest.TestCase):
    def test_square_closed_form(self):
        a,b,d=2.,2.,3.
        vertices=np.array([[d,-a,-b],[d,a,-b],[d,a,b],[d,-a,b]])
        expected=2/math.pi*(a/math.hypot(a,d)*math.atan(b/math.hypot(a,d))+b/math.hypot(b,d)*math.atan(a/math.hypot(b,d)))
        self.assertAlmostEqual(polygon_view_factor(vertices,[0,0,0],"worst_case"),expected,places=14)
        self.assertAlmostEqual(polygon_view_factor(vertices,[0,0,0],[1,0,0]),expected,places=14)

    def test_far_field(self):
        d=1000.
        vertices=np.array([[d,-1,-1],[d,1,-1],[d,1,1],[d,-1,1]])
        got=polygon_view_factor(vertices,[0,0,0],"worst_case")
        expected=4/(math.pi*d*d)
        self.assertLess(abs(got/expected-1),2e-6)

    def test_wall_limit(self):
        got=finite_panel_view_factor(1e6,10.,20.)
        self.assertAlmostEqual(got,infinite_wall_view_factor(10.,20.),places=9)

    def test_normal_away(self):
        vertices=np.array([[2,-1,-1],[2,1,-1],[2,1,1],[2,-1,1]])
        self.assertEqual(polygon_view_factor(vertices,[0,0,0],[-1,0,0]),0)

    def test_worst_encloses_orientations(self):
        rng=np.random.default_rng(20261030)
        vertices=np.array([[5,-2,0],[5,2,0],[5,2,7],[5,-2,7]])
        worst=polygon_view_factor(vertices,[0,0,0],"worst_case")
        for _ in range(100):
            self.assertLessEqual(polygon_view_factor(vertices,[0,0,0],rng.normal(size=3)),worst+1e-12)


class FrontGeometry(unittest.TestCase):
    def test_planar_front(self):
        grid=W.AffineGrid((10,0,0,0,10,0))
        tau=np.tile((np.arange(5)+.5)*10/2,(5,1))
        front=W.front_segments(tau,12,grid,2)
        leading=[s for s in front if s.kind=="leading"]
        self.assertTrue(leading)
        for s in leading:
            self.assertAlmostEqual(s.rate_m_s,2)
            np.testing.assert_allclose(s.direction_xy,[1,0],atol=1e-14)
            self.assertAlmostEqual(s.start_xy[0],24)
            self.assertAlmostEqual(s.end_xy[0],24)

    def test_circular_front_closed(self):
        rows,cols=np.indices((21,21));tau=np.hypot(rows-10,cols-10)
        segments=[s for s in W.front_segments(tau,5.25,(1,0,0,0,1,0),1) if s.kind=="leading"]
        self.assertGreater(len(segments),20)
        endpoints={}
        for s in segments:
            for p in (s.start_xy,s.end_xy):
                key=tuple(round(v,8) for v in p);endpoints[key]=endpoints.get(key,0)+1
                self.assertLess(abs(math.hypot(p[0]-10.5,p[1]-10.5)-5.25),.03)
        self.assertTrue(all(count==2 for count in endpoints.values()))

    def test_isolated_cell_closed(self):
        tau=np.ones((3,3))*10;tau[1,1]=0
        segments=[s for s in W.front_segments(tau,5,(1,0,0,0,1,0),1) if s.kind=="leading"]
        self.assertEqual(len(segments),4)
        vertices={p for s in segments for p in (s.start_xy,s.end_xy)}
        self.assertEqual(len(vertices),4)

    def test_unknown_recorded_and_refused(self):
        tau=np.arange(9,dtype=float).reshape(3,3);tau[0,0]=np.nan
        front=W.front_segments(tau,4,(1,0,0,0,1,0),1)
        self.assertIn((0,0),front.unsupported_cells)
        with self.assertRaises(W.UnsupportedGeometry):W.flux_at_points([[1,1]],[4],{"ignition_time_s":tau},(1,0,0,0,1,0))

    def test_zero_gradient_refused(self):
        tau=np.zeros((3,3))
        with self.assertRaises(W.UnsupportedGeometry):W.flux_at_points([[1,1]],[1],{"ignition_time_s":tau},(1,0,0,0,1,0))

    def test_present_fire_enclosure_refused(self):
        member={"ignition_time_s":np.zeros((3,3)),"present_fire_representation":"SCALAR_MAX_REMAINING_ENCLOSURE"}
        with self.assertRaises(W.UnsupportedGeometry):W.flux_at_points([[1,1]],[1],member,(1,0,0,0,1,0))

    def test_known_no_ignition_is_zero(self):
        member={"ignition_time_s":np.full((3,3),np.inf)}
        np.testing.assert_array_equal(W.flux_at_points([[1,1]],[1],member,(1,0,0,0,1,0)),[[0.]])
        self.assertEqual(W.flux_enclosure((0,1,0,1),(0,5),member,(1,0,0,0,1,0)),(0.,0.))

    def test_shear_planar(self):
        grid=W.AffineGrid((2,1,10,0,3,20));rows,cols=np.indices((4,4))
        tau=(2*(cols+.5)+(rows+.5)+10)/.5
        segments=[s for s in W.front_segments(tau,28,grid,1) if s.kind=="leading"]
        self.assertTrue(segments)
        for segment in segments:
            self.assertAlmostEqual(segment.rate_m_s,.5)
            np.testing.assert_allclose(segment.direction_xy,[1,0],atol=1e-14)


class EnclosuresAndDose(unittest.TestCase):
    def test_thousand_boxes_and_nested_intervals(self):
        rng=np.random.default_rng(20261030);tau=np.tile(np.arange(3)*10.,(3,1))
        member={"ignition_time_s":tau};grid=(10,0,0,0,10,0)
        for _ in range(1000):
            x,y=rng.uniform(-20,40,2);dx,dy=rng.uniform(.01,20,2);t=rng.uniform(-1,31);dt=rng.uniform(.01,8)
            box=(x,x+dx,y,y+dy);interval=(t,t+dt)
            lo,hi=W.flux_enclosure(box,interval,member,grid)
            point=(rng.uniform(x,x+dx),rng.uniform(y,y+dy));time=rng.uniform(t,t+dt)
            q=W.flux_at_points([point],[time],member,grid)[0,0]
            self.assertGreaterEqual(q,lo);self.assertLessEqual(q,hi)
            small=(x+dx*.25,x+dx*.75,y+dy*.25,y+dy*.75)
            l2,h2=W.flux_enclosure(small,(t+dt*.25,t+dt*.75),member,grid)
            self.assertGreaterEqual(l2,lo);self.assertLessEqual(h2,hi)

    def test_dose_constant(self):
        self.assertAlmostEqual(W.dose([10,10],[0,60],"tdu"),60*10**(4/3),places=10)
        self.assertEqual(W.dose([10,10],[0,60]),600)

    def test_dose_ramp(self):
        self.assertAlmostEqual(W.dose([0,10],[0,60],"tdu"),60*3/7*10**(4/3),places=10)
        self.assertEqual(W.dose([0,10],[0,60]),300)

    def test_dose_near_constant(self):
        self.assertAlmostEqual(W.dose([10,10+1e-12],[0,60],"tdu")/(60*10**(4/3)),1,places=11)

    def test_unknown_mask_not_zero(self):
        tau=np.arange(9,dtype=float).reshape(3,3);mask=np.zeros((3,3),bool);mask[1,1]=True
        with self.assertRaises(W.UnsupportedGeometry):W.flux_at_points([[1,1]],[4],{"ignition_time_s":tau,"unknown_mask":mask},(1,0,0,0,1,0))

    def test_provenance_copy(self):
        p=W.provenance();p["constants"].clear();self.assertTrue(W.provenance()["constants"])

    def test_intensity(self):
        self.assertEqual(fireline_intensity(.5),9304)
        h,a,s=flame_geometry(float(flame_length(9304)),(0,0));self.assertEqual(a,0);self.assertEqual(s,(0,0))
        self.assertGreater(h,0)

    def test_full_journey_gate_stays_closed(self):
        import importlib.util
        path=Path(__file__).resolve().parents[1]/"adapters/journey_check.py"
        spec=importlib.util.spec_from_file_location("gated_journey_check",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with self.assertRaises(NotImplementedError):module.evaluate_decision({},radiation_law="v2")
        with self.assertRaises(ValueError):module.evaluate_decision({},radiation_law="v1")
        expected={"status":"unresolved"}
        self.assertIs(module.evaluate_decision({},v1_evaluator=lambda decision:expected),expected)


if __name__=="__main__":unittest.main()
