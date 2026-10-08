"""Independent numerical and routing gates; execute from any working directory."""
import copy
import hashlib
import json
import math
import sys
import unittest
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(D / "candidate"), str(D / "candidate/routing-package"), str(D / "candidate/mentor_runtime")]
from independent_reference import exhaustive, witness, integrate, radiation_quadrature
from routing.core import solve
from routing.validation import ValidationError, validate_hazard, validate_request
from forecast_bridge import convert, IntegrationError
from expected_heat_flux.model import AffineGrid, ExpectedHeatFluxModel, CombustionParameters
from expected_heat_flux.temporal import ignition_to_active_probability, initial_active_occupancy
from hazard_constructor import ConstructionConfig, construct_hazard, draw_ignitions, interval_enclosures, radiation_model, sensitivity_panel
from hourly import build_hazard, request_for_hazard, accept_constructed_update
from routing.session import RoutingSession

ROWS = []


def fixture():
    grid={"x0":0.,"y0":0.,"resolution":10.,"width":3,"height":2}
    nodes=[{"id":name,"x":x,"y":y,"waitable":wait} for name,x,y,wait in [("O",5,5,False),("A",15,5,True),("D",25,5,False),("B",15,15,False)]]
    specs=[("OA","O","A",2,[(0,0,.5),(1,.5,1)]),("AD","A","D",2,[(1,0,.5),(2,.5,1)]),("OB","O","B",3,[(0,0,.5),(4,.5,1)]),("BD","B","D",3,[(4,0,.5),(2,.5,1)])]
    graph={"revision":"independent-tiny-v1","crs":"EPSG:5179","grid":grid,"nodes":nodes,"edges":[{"id":eid,"u":u,"v":v,"travel_ticks":t,"segments":[{"cell":c,"start":a,"end":b} for c,a,b in parts]} for eid,u,v,t,parts in specs],"forbidden_turns":[],"mid_edge_reversal":False}
    hazard={"schema":"wfg.routing.edgegrid/1","version":1,"graph_revision":graph["revision"],"crs":graph["crs"],"grid":grid.copy(),"dt":1,"time_origin":"2022-03-04T03:00:00Z","issued_at":"2022-03-04T03:00:00Z","available_at":"2022-03-04T03:00:00Z","valid_from":0,"valid_until":12,"units":{"time":"s","flux":"kW/m2","dose":"kJ/m2"},"evidence_class":"LABELLED_FIXTURE","channels":["flame_contact","incident_heat_flux"],"unsupported_channels":[],"provenance":{"source":"independent handmade control","interpretation":"study fixture, not real fire"},"members":[{"id":"m0","breakpoints":[0,12],"flux":[[2.]*6],"flame":[[False]*6],"support":[[True]*6]}]}
    request={"position":{"node":"O"},"incoming_edge":None,"departure":0,"horizon":12,"destinations":[{"node":"D","dwell":2,"open_intervals":[[0,12]]}],"incurred":{"m0":0},"hazard_version":1,"as_of":hazard["time_origin"],"objective":"earliest_arrival","exposure_scope":"including_dwell","budgets":{"peak":10,"dose":{"m0":100}},"limits":{"wall_s":5,"max_labels":100000,"max_expansions":100000,"frontier_width":4096},"solver":"baseline"}
    return graph,hazard,request


def native():
    graph,_,_=fixture()
    md={"schema":"wfg.forecast.native-intervals/1","graph_revision":graph["revision"],"crs":graph["crs"],"flux_units":"W/m2","flux_semantics":"interval_upper_bound_incident_radiant_flux","flame_semantics":"contact_anywhere_during_interval","present_fire_included":True,"physical_scope":"independent fixture","evidence_class":"LABELLED_FIXTURE","shape":[2,3],"affine_transform":[10,0,0,0,-10,20],"time_origin":"2022-03-04T03:00:00Z","issued_at":"2022-03-04T03:00:00Z","available_at":"2022-03-04T03:00:00Z","breakpoints_s":[0,12],"version":1,"dt_s":1,"source":"independent review"}
    members=[{"id":"m0","flux_w_m2":np.array([[[1000,2000,3000],[4000,5000,6000]]],dtype=float),"flame_contact":np.zeros((1,2,3),bool),"support":np.ones((1,2,3),bool)}]
    return graph,md,members


def snapshot(q=None, valid=None, burned=None):
    q=np.zeros((2,3)) if q is None else np.asarray(q,dtype=float)
    valid=np.isfinite(q) if valid is None else np.asarray(valid,dtype=bool)
    burned=np.zeros(q.shape) if burned is None else np.asarray(burned,dtype=float)
    arrays={"new_burn_probability":q,"probability_valid":valid,"source_burned_area":burned,"source_burned_area_valid":np.ones(q.shape,bool),"affine_transform":np.array([10,0,0,0,-10,20.])}
    md={"shape":list(q.shape),"epsg":5179,"affine_transform":arrays["affine_transform"].tolist(),"cutoff_utc":"2022-03-04T03:00:00Z","metadata":{"forecast_interval_s":3600},"known_probability_cells":int(valid.sum()),"unknown_probability_cells":int((~valid).sum()),"finite_expected_flux_cells":0,"initial_active_burning_probability_supplied":False,"complete_expected_flux_available":False,"native_snapshot_sha256":"independent-synthetic-snapshot-v1"}
    return arrays,md


class IndependentConstruction(unittest.TestCase):
    def test_sampled_law_matches_analytic_occupancy(self):
        cfg=ConstructionConfig(scenario_count=100000,current_state="cold")
        q=np.array([[.4,.8]])
        times=draw_ignitions(q,cfg)
        occurred=np.isfinite(times)
        frequency=occurred.mean(axis=0)
        empirical=np.where(occurred,np.maximum(0,np.minimum(300,3600-times))/3600,0).mean(axis=0)
        expected=q*(300/3600-300**2/(2*3600**2))
        np.testing.assert_allclose(frequency,q,rtol=0,atol=.01)
        np.testing.assert_allclose(empirical,expected,rtol=0,atol=.0012)
        ROWS.append({"case":"sampled_analytic_law","samples":100000,"seed":cfg.seed,"event_frequency":frequency.tolist(),"empirical_hour_mean_occupancy":empirical.tolist(),"analytic_occupancy":expected.tolist()})

    def test_comonotone_occurrence_is_nested(self):
        cfg=ConstructionConfig(scenario_count=100000,current_state="cold",dependence="comonotone")
        times=draw_ignitions([[.4,.8]],cfg)
        occurred=np.isfinite(times)
        self.assertFalse(np.any(occurred[:,0,0] & ~occurred[:,0,1]))
        np.testing.assert_allclose(occurred.mean(axis=0),[[.4,.8]],rtol=0,atol=.01)

    def test_interior_maximum_no_endpoint_shortcut(self):
        transform=(10,0,0,0,10,0)
        model=ExpectedHeatFluxModel(grid=AffineGrid(transform),heat_release_rate_density_w_m2=60000,radiative_fraction=.3,emission_height_m=5)
        flame,flux=interval_enclosures(np.array([[[4.]]]),np.array([[False]]),0,[0,10],2,model)
        self.assertTrue(flame[0,0,0,0])
        # Activity is absent at both t=0 and t=10, positive on [4,6).
        expected=radiation_quadrature([[1]],transform,60000,.3,5)
        self.assertGreaterEqual(flux[0,0,0,0]+1e-7,expected[0,0])
        np.testing.assert_allclose(flux[0,0],expected,rtol=1e-7,atol=1e-7)

    def test_disjoint_sources_union_bounds_interior(self):
        transform=(10,0,0,0,10,0)
        model=ExpectedHeatFluxModel(grid=AffineGrid(transform),heat_release_rate_density_w_m2=60000,radiative_fraction=.3,emission_height_m=5)
        events=np.array([[[1.,7.]]]);current=np.zeros((1,2),bool)
        flame,flux=interval_enclosures(events,current,0,[0,10],2,model)
        self.assertTrue(flame.all())
        union=radiation_quadrature([[1,1]],transform,60000,.3,5)
        np.testing.assert_allclose(flux[0,0],union,rtol=1e-7,atol=1e-7)
        for actual in [[[1,0]],[[0,1]],[[0,0]]]:
            field=radiation_quadrature(actual,transform,60000,.3,5)
            self.assertTrue(np.all(field <= flux[0,0]+1e-7))
        self.assertTrue(np.all(flux[0,0] > radiation_quadrature([[1,0]],transform,60000,.3,5)))

    def test_current_endpoint_and_fractional_duration(self):
        cfg=ConstructionConfig()
        model=radiation_model([10,0,0,0,10,0],cfg)
        flame,_=interval_enclosures(np.full((1,1,1),np.inf),np.ones((1,1),bool),5,[0,5,10],300,model)
        self.assertEqual(flame.tolist(),[[[[True]],[[False]]]])

    def test_constructed_known_probability_and_current_are_disjoint(self):
        q=np.zeros((2,3));q[0,1]=1
        burned=np.zeros_like(q);burned[1,2]=1
        arrays,md=snapshot(q,burned=burned)
        got=construct_hazard(arrays,md,mode="research")
        self.assertEqual(got["status"],"CONSTRUCTED")
        self.assertTrue(np.isinf(got["arrays"]["ignition_time_s"][:,1,2]).all())
        self.assertTrue(got["arrays"]["current_active"][1,2])
        self.assertEqual(got["arrays"]["constructed_probability"][0,1],1)
        self.assertFalse(np.isnan(got["arrays"]["flux_w_m2"]).any())

    def test_unknown_assignment_separate_from_native(self):
        q=np.zeros((2,3));q[0,1]=np.nan
        arrays,md=snapshot(q);native_q=arrays["new_burn_probability"].copy()
        for unknown in [0,1]:
            got=construct_hazard(arrays,md,mode="research",config=ConstructionConfig(unknown_probability=unknown,current_state="cold"))
            self.assertEqual(got["arrays"]["constructed_probability"][0,1],unknown)
            self.assertEqual(got["metadata"]["unknown_source_assignment_cells"],1)
            self.assertEqual(got["metadata"]["evidence_class"],"RESEARCH_CONSTRUCTION")
        np.testing.assert_equal(arrays["new_burn_probability"],native_q)

    def test_unknown_current_active_is_declared_disjoint(self):
        arrays,md=snapshot(np.full((2,3),.4))
        arrays["source_burned_area_valid"][0,1]=False
        before={k:v.copy() for k,v in arrays.items()}
        cfg=ConstructionConfig(unknown_current_state="active")
        result=construct_hazard(arrays,md,mode="research",config=cfg)
        self.assertTrue(result["arrays"]["current_active"][0,1])
        self.assertEqual(result["arrays"]["constructed_probability"][0,1],0)
        self.assertTrue(np.isinf(result["arrays"]["ignition_time_s"][:,0,1]).all())
        self.assertEqual(result["metadata"]["assumptions"]["unknown_current_state"],"active")
        self.assertEqual(result["metadata"]["evidence_class"],"RESEARCH_CONSTRUCTION")
        for k,v in before.items():np.testing.assert_equal(arrays[k],v)

    def test_reproducible_construction(self):
        arrays,md=snapshot(np.full((2,3),.4))
        a=construct_hazard(arrays,md,mode="research");b=construct_hazard(arrays,md,mode="research")
        for key in a["arrays"]:
            if key in ("flux_w_m2","uniform_mean_flux_w_m2"):
                # Float64 FFT may differ by a few ULPs under identical draws.
                # Use the preregistered numerical tolerance; require bitwise
                # identity for scenario events, contacts, support and laws.
                np.testing.assert_allclose(a["arrays"][key],b["arrays"][key],rtol=0,atol=1e-7)
            else:
                np.testing.assert_equal(a["arrays"][key],b["arrays"][key])
        self.assertEqual(a["metadata"],b["metadata"])

    def test_uniform_mean_field_matches_independent_expected_heat(self):
        q=np.array([[.4,.1,.2],[0,.8,.6]])
        arrays,md=snapshot(q)
        cfg=ConstructionConfig(current_state="cold")
        got=construct_hazard(arrays,md,mode="research",config=cfg)
        occupancy=q*(300/3600-300**2/(2*3600**2))
        np.testing.assert_allclose(got["arrays"]["uniform_mean_active_occupancy"],occupancy,rtol=0,atol=1e-12)
        expected=radiation_quadrature(occupancy,md["affine_transform"],60000,.3,5)
        np.testing.assert_allclose(got["arrays"]["uniform_mean_flux_w_m2"],expected,rtol=1e-8,atol=1e-7)

    def test_strict_preserves_unsupported_launch(self):
        g,_,q=fixture();arrays,md=snapshot()
        h,constructed,native_md=build_hazard(g,arrays,md,mode="strict",parent_sha256="a"*64)
        self.assertEqual(constructed["status"],"UNSUPPORTED")
        self.assertFalse(constructed["arrays"]["support"].any())
        self.assertTrue(np.isnan(constructed["arrays"]["flux_w_m2"]).all())
        self.assertEqual(native_md["mode"],"strict")
        self.assertIsInstance(native_md["assumption_id"],str)
        req=request_for_hazard(q,h)
        self.assertEqual(solve(g,h,req)["status"],"UNSUPPORTED")

    def test_no_native_horizon_repetition(self):
        arrays,md=snapshot()
        with self.assertRaises(ValueError):construct_hazard(arrays,md,mode="research",config=ConstructionConfig(horizon_s=7200))

    def test_current_remaining_phase_energy_bound(self):
        with self.assertRaises(ValueError):ConstructionConfig(initial_remaining_s=900,burning_duration_s=300)
        # Every registered variant must obey the same phase allocation.
        for cfg in sensitivity_panel().values():
            self.assertLessEqual(cfg.initial_remaining_s,cfg.burning_duration_s)


class IndependentLifecycle(unittest.TestCase):
    def setup_session(self):
        g,_,q=fixture();arrays,md=snapshot();cfg=ConstructionConfig(current_state="cold")
        h,_,_=build_hazard(g,arrays,md,mode="research",config=cfg,parent_sha256="a"*64)
        session=RoutingSession(g,prepare=True,graph_ownership="snapshot")
        self.assertEqual(accept_constructed_update(session,h,h["available_at"])["status"],"ACCEPTED_UPDATE")
        req=request_for_hazard(q,h)
        first=session.plan(req);self.assertTrue(session.commit(first))
        return g,arrays,md,cfg,h,session,first

    def test_changed_future_ids_preserve_max_past_dose(self):
        g,arrays,md,cfg,h,session,first=self.setup_session()
        incurred={mid:float(i+1) for i,mid in enumerate(session.progress["incurred"])}
        self.assertEqual(session.set_progress({"node":"O"},None,10,incurred,[])["status"],"PROGRESS_ACCEPTED")
        newer,_,_=build_hazard(g,arrays,md,mode="research",config=cfg,version=2,parent_sha256="a"*64)
        self.assertTrue(set(incurred).isdisjoint({m["id"] for m in newer["members"]}))
        event=accept_constructed_update(session,newer,newer["available_at"])
        self.assertEqual(event["status"],"ACCEPTED_UPDATE")
        self.assertEqual(set(session.progress["incurred"].values()),{4.})
        self.assertFalse(event["history_transfer"]["physical_history_correspondence_claim"])
        self.assertFalse(session.commit(first))

    def test_changed_assumptions_new_future_mapping(self):
        g,arrays,md,cfg,h,session,_=self.setup_session()
        incurred={mid:5. for mid in session.progress["incurred"]}
        session.set_progress({"node":"O"},None,10,incurred,[])
        newer,_,_=build_hazard(g,arrays,md,mode="research",config=replace(cfg,fuel_load_kg_m2=20),version=2,parent_sha256="a"*64)
        self.assertNotEqual(h["provenance"]["native_metadata"]["assumption_id"],newer["provenance"]["native_metadata"]["assumption_id"])
        event=accept_constructed_update(session,newer,newer["available_at"])
        self.assertEqual(event["status"],"ACCEPTED_UPDATE")
        self.assertEqual(set(session.progress["incurred"].values()),{5.})
        self.assertTrue(event["history_transfer"]["future_assumptions_prospective"])

    def test_unmapped_changed_members_reject(self):
        g,arrays,md,cfg,h,session,_=self.setup_session()
        newer,_,_=build_hazard(g,arrays,md,mode="research",config=cfg,version=2,parent_sha256="a"*64)
        event=session.accept_update(newer,newer["available_at"])
        self.assertEqual(event["status"],"UNSUPPORTED")
        self.assertEqual(session.hazard["version"],1)

    def test_historical_gap_cannot_reset_history(self):
        g,arrays,md,cfg,h,session,_=self.setup_session()
        incurred={mid:5. for mid in session.progress["incurred"]}
        session.set_progress({"node":"O"},None,10,incurred,[])
        md["cutoff_utc"]="2022-03-04T06:00:00Z"
        newer,_,_=build_hazard(g,arrays,md,mode="research",config=cfg,version=2,parent_sha256="b"*64,origin=h["time_origin"])
        event=accept_constructed_update(session,newer,newer["available_at"])
        self.assertEqual(event["status"],"UNSUPPORTED")
        self.assertEqual(event["reason"],"HISTORY_GAP_REQUIRES_VERIFIED_PROGRESS")
        self.assertEqual(session.progress["incurred"],incurred)

    def test_gap_refusal_invalidates_pending_result_and_labels_retained(self):
        g,arrays,md,cfg,h,session,first=self.setup_session()
        prior=copy.deepcopy(session.progress)
        old_generation=session.generation
        md["cutoff_utc"]="2022-03-04T06:00:00Z"
        newer,_,_=build_hazard(g,arrays,md,mode="research",config=cfg,version=2,parent_sha256="b"*64,origin=h["time_origin"])
        event=accept_constructed_update(session,newer,newer["available_at"])
        self.assertEqual(event["status"],"UNSUPPORTED")
        self.assertEqual(session.progress,prior)
        self.assertGreater(session.generation,old_generation)
        self.assertFalse(session.commit(first))
        self.assertEqual(session.last_update["reason"],"HISTORY_GAP_REQUIRES_VERIFIED_PROGRESS")
        retained=session.retained_plan()
        self.assertEqual(retained.get("guidance_version_label"),"OLDER_ACCEPTED_VERSION")

    def test_stale_hazard_and_graph_reset(self):
        g,arrays,md,cfg,h,session,_=self.setup_session()
        self.assertEqual(accept_constructed_update(session,h,h["available_at"])["status"],"STALE_UPDATE")
        replacement=copy.deepcopy(g);replacement["revision"]+="-new"
        self.assertNotEqual(session.replace_graph(replacement)["status"],"RESET")
        event=session.replace_graph(replacement,reset=True)
        self.assertIsNone(session.hazard);self.assertIsNone(session.progress)


class IndependentMath(unittest.TestCase):
    def test_uniform_occupancy_analytic(self):
        for duration in [300,3600,7200]:
            D=3600;q=.4
            # Direct E[min(T,D-A)] integration has triangle loss at final T.
            expected=q*(duration/D-duration*duration/(2*D*D)) if duration<=D else q/2
            got=ignition_to_active_probability(q,duration,D)
            self.assertAlmostEqual(float(got.mean_active_probability),expected,places=12)
            self.assertAlmostEqual(float(got.endpoint_active_probability),q*min(duration/D,1),places=12)

    def test_current_occupancy_analytic_endpoint(self):
        for remaining in [0,300,3600,7200]:
            got=initial_active_occupancy(.6,remaining,3600)
            self.assertAlmostEqual(float(got.mean_active_probability),.6*min(remaining,3600)/3600,places=12)
            self.assertEqual(float(got.endpoint_active_probability),.6 if remaining>3600 else 0)

    def test_combustion_units(self):
        p=CombustionParameters(10,18e6,300,.1)
        self.assertEqual(float(p.heat_release_rate_density_w_m2),60000.)
        self.assertEqual(float(p.heat_release_rate_density_w_m2)*.3,18000.)
        # 1 kW/m2 for 10 seconds is exactly 10 kJ/m2.
        _,h,_=fixture();h["members"][0]["flux"]=[[1]*6]
        stats,codes=integrate(h,[(0,0,10)])
        self.assertFalse(codes);self.assertEqual(float(stats["m0"]["dose"]),10)

    def test_radiation_quadrature_independent(self):
        transform=(10,0,0,0,-10,20)
        active=np.array([[1,.4,0],[.2,0,.7]])
        density=np.array([[100,300,200],[10,50,20.]])
        model=ExpectedHeatFluxModel(grid=AffineGrid(transform),heat_release_rate_density_w_m2=density,radiative_fraction=.3,emission_height_m=5,atmospheric_transmissivity=.8)
        expected=radiation_quadrature(active,transform,density,.3,5,.8)
        np.testing.assert_allclose(model.predict(active).incident_heat_flux_w_m2,expected,rtol=1e-8,atol=1e-7)
        self.assertAlmostEqual(model.predict(active).expected_total_radiant_power_w,float((active*density*.3).sum()*100),places=10)

    def test_same_cell_rectangular_formula(self):
        # For square [-a,a] x [-b,b] at separation h, solid angle is
        # 4 atan(ab/(h sqrt(h^2+a^2+b^2))). Derivation uses area integral.
        h=5;a=b=5;source=18000
        expected=source/math.pi*math.atan(a*b/(h*math.sqrt(h*h+a*a+b*b)))
        model=ExpectedHeatFluxModel(grid=AffineGrid((10,0,0,0,10,0)),heat_release_rate_density_w_m2=60000,radiative_fraction=.3,emission_height_m=5)
        self.assertAlmostEqual(float(model.predict([[1]]).incident_heat_flux_w_m2[0,0])/expected,1,places=11)

    def test_expected_heat_linearity_not_second_probability(self):
        model=ExpectedHeatFluxModel(grid=AffineGrid((10,0,0,0,10,0)),heat_release_rate_density_w_m2=60000,radiative_fraction=.3,emission_height_m=5)
        q=.4;T=300;D=3600
        occupancy=q*(T/D-T*T/(2*D*D))
        full=float(model.predict([[1]]).incident_heat_flux_w_m2[0,0])
        self.assertAlmostEqual(float(model.predict([[occupancy]]).incident_heat_flux_w_m2[0,0]),full*occupancy,places=10)


class IndependentRouting(unittest.TestCase):
    def compare(self,name,g,h,q,expected_arrival,expected_feasible=True):
        reference=exhaustive(g,h,q)
        got=solve(g,h,q)
        ROWS.append({"case":name,"reference":reference,"candidate":got,"fixture":{"graph":g,"hazard":h,"request":q}})
        self.assertEqual(reference["arrival"],expected_arrival)
        self.assertEqual(got.get("arrival"),expected_arrival)
        self.assertEqual(got["status"] in ["CHECKED_ROUTE","CONDITIONAL_OPTIMUM"],expected_feasible)
        if expected_feasible:
            independent=witness(g,h,q,got["legs"],got["destination"])
            self.assertTrue(independent["ok"],independent)
            for mid,stat in independent["per_member"].items():
                self.assertAlmostEqual(stat["dose"],got["per_member"][mid]["dose"],places=9)
        return got

    def test_constant_short_trip_and_dwell(self):
        g,h,q=fixture();q["budgets"]["dose"]["m0"]=12
        got=self.compare("constant_flux_route_and_dwell",g,h,q,4)
        self.assertEqual(got["per_member"]["m0"]["dose"],12)

    def test_dose_rejects_at_just_below_exact_budget(self):
        g,h,q=fixture();q["budgets"]["dose"]["m0"]=11.99
        self.compare("dose_boundary_reject",g,h,q,None,False)

    def test_incurring_exposure_changes_feasibility(self):
        g,h,q=fixture();q["incurred"]["m0"]=3;q["budgets"]["dose"]["m0"]=14
        self.compare("incurred_dose",g,h,q,None,False)

    def test_flame_detour(self):
        g,h,q=fixture();h["members"][0]["flame"][0][1]=True
        self.compare("flame_detour",g,h,q,6)

    def test_forbidden_turn_detour(self):
        g,h,q=fixture();g["forbidden_turns"]=[["OA","AD"]]
        self.compare("forbidden_turn",g,h,q,6)

    def test_destination_requires_wait_before_admission(self):
        g,h,q=fixture();q["destinations"][0]["open_intervals"]=[[8,12]]
        self.compare("opening_wait",g,h,q,8)

    def test_dwell_horizon(self):
        g,h,q=fixture();q["horizon"]=5
        self.compare("horizon_includes_dwell",g,h,q,None,False)

    def test_route_only_dwell_still_flame_checked(self):
        g,h,q=fixture();q["exposure_scope"]="route_only";q["horizon"]=6
        m=h["members"][0];m["breakpoints"]=[0,5,12];m["flux"]=[[2]*6,[2]*6];m["flame"]=[[False]*6,[False,False,True,False,False,False]];m["support"]=[[True]*6,[True]*6]
        self.compare("route_only_flame_dwell",g,h,q,None,False)

    def test_peak_is_not_hourly_mean(self):
        g,h,q=fixture();m=h["members"][0];m["breakpoints"]=[0,1,12];m["flux"]=[[20]*6,[0]*6];m["flame"]=[[False]*6,[False]*6];m["support"]=[[True]*6,[True]*6];q["budgets"]["peak"]=10
        self.assertLess(20/12,q["budgets"]["peak"])
        self.compare("peak_vs_mean",g,h,q,None,False)

    def test_missing_support_unresolved(self):
        g,h,q=fixture();h["members"][0]["support"][0][0]=False
        got=self.compare("missing_support",g,h,q,None,False)
        self.assertEqual(got["status"],"UNSUPPORTED")


class IndependentAdmission(unittest.TestCase):
    def test_north_row_orientation_units(self):
        g,md,m=native();h=convert(g,md,m)
        self.assertEqual(h["members"][0]["flux"],[[4,5,6,1,2,3]])
        self.assertEqual(h["units"],{"time":"s","flux":"kW/m2","dose":"kJ/m2"})

    def test_nan_supported_rejected(self):
        g,md,m=native();m[0]["flux_w_m2"][0,0,0]=np.nan
        with self.assertRaises(IntegrationError): convert(g,md,m)

    def test_nan_unsupported_retains_mask(self):
        g,md,m=native();m[0]["flux_w_m2"][0,0,0]=np.nan;m[0]["support"][0,0,0]=False
        h=convert(g,md,m)
        self.assertFalse(h["members"][0]["support"][0][3]);self.assertEqual(h["members"][0]["flux"][0][3],0)

    def test_malformed_unit_shape_bool_mask_mean(self):
        for key,value in [("flux_units","kW/m2"),("flux_semantics","hourly_mean"),("breakpoints_s",[0,0]),("affine_transform",[10,0,1,0,-10,20]),("present_fire_included",False)]:
            with self.subTest(key=key):
                g,md,m=native();md[key]=value
                with self.assertRaises(IntegrationError): convert(g,md,m)
        for name,value in [("support",np.ones((1,2,3))), ("flame_contact",np.zeros((1,2,3))), ("flux_w_m2",np.zeros((2,2,3))), ("flux_w_m2",np.ma.array(np.ones((1,2,3)),mask=False))]:
            with self.subTest(name=name,value_type=str(type(value))):
                g,md,m=native();m[0][name]=value
                with self.assertRaises(IntegrationError): convert(g,md,m)

    def test_time_horizon_graph_revision_admission(self):
        g,h,q=fixture()
        for key,value in [("horizon",13),("hazard_version",2),("as_of","2022-03-04T04:00:00Z")]:
            with self.subTest(key=key):
                bad=copy.deepcopy(q);bad[key]=value
                with self.assertRaises(ValidationError): validate_request(g,h,bad)
        bad=copy.deepcopy(h);bad["graph_revision"]="wrong"
        with self.assertRaises(ValidationError): validate_hazard(g,bad)
        bad=copy.deepcopy(h);bad["available_at"]="2022-03-04T04:00:00Z"
        with self.assertRaises(ValidationError): validate_hazard(g,bad,q["as_of"])


class RecordingResult(unittest.TextTestResult):
    def startTest(self,test):
        super().startTest(test);self.started=datetime.now(timezone.utc)
    def addSuccess(self,test):
        super().addSuccess(test);ROWS.append({"test":test.id(),"status":"PASS","started":self.started.isoformat()})
    def addFailure(self,test,err):
        super().addFailure(test,err);ROWS.append({"test":test.id(),"status":"FAIL","traceback":self._exc_info_to_string(err,test),"started":self.started.isoformat()})
    def addError(self,test,err):
        super().addError(test,err);ROWS.append({"test":test.id(),"status":"ERROR","traceback":self._exc_info_to_string(err,test),"started":self.started.isoformat()})


if __name__ == "__main__":
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2,resultclass=RecordingResult).run(suite)
    report={"schema":"independent-review/1","timestamp":stamp,"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"passed":result.wasSuccessful(),"freeze_sha256":hashlib.sha256((D/"evidence/independent_freeze.json").read_bytes()).hexdigest(),"test_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"reference_source_sha256":hashlib.sha256((D/"tests/independent_reference.py").read_bytes()).hexdigest(),"rows":ROWS}
    destination=D/"evidence"/("independent_results_"+stamp+".json")
    destination.write_text(json.dumps(report,indent=2)+"\n")
    print("Report:",destination)
    sys.exit(0 if result.wasSuccessful() else 1)
