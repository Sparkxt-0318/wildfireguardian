"""Analytic and containment regressions for the model-bound improvement."""
from fractions import Fraction
import math
import numpy as np
from test_law import W
from wfg_flamefront.geometric_bounds import quad_bound
from wfg_flamefront.solidflame import polygon_view_factor
from wfg_flamefront.verified_view import _Arithmetic,_atan_unit,_pi


GRID=(20.,0.,0.,0.,20.,0.)
TAU=np.array([[0.,1.],[0.,1.]])
MEMBER={"ignition_time_s":TAU}


def test_far_field_closed_form_without_cancellation():
    d=1e14
    vertices=np.array([[d,-1,-1],[d,1,-1],[d,1,1],[d,-1,1]])
    q=polygon_view_factor(vertices,[0.,0.,0.])
    expected=4/(math.pi*d*d)
    assert math.isclose(q,expected,rel_tol=2e-15)


def test_retained_public_counterexample_is_enclosed():
    point=[350354922136235.44,-25174391049238.09]
    fuel={"wind_xy":(2.,1.)}
    q=W.flux_at_points([point],[.1],MEMBER,GRID,fuel)[0,0]
    lower,upper=W.flux_enclosure([point[0],point[0],point[1],point[1]],[.1,.1],MEMBER,GRID,fuel)
    assert 0<q<1e-24
    assert lower<=q<=upper<1e-23


def test_upper_is_distance_dependent_and_spatially_monotone():
    near=W.flux_enclosure((100.,110.,-30.,-20.),(.1,.8),MEMBER,GRID)[1]
    far=W.flux_enclosure((1000.,1010.,-30.,-20.),(.1,.8),MEMBER,GRID)[1]
    small=W.flux_enclosure((103.,107.,-27.,-23.),(.2,.4),MEMBER,GRID)[1]
    assert far<near/10
    assert small<=near<400


def test_exact_area_distance_proof_quantities_and_fallback():
    factor,proof=quad_bound(0,0,TAU,GRID,{},(1000.,1010.,-30.,-20.))
    assert proof["cone_proved"]
    assert factor==min(Fraction(1),proof["area_upper"]/(3*proof["distance2_lower"]))
    assert 0<factor<1
    factor,proof=quad_bound(0,0,TAU,GRID,{},(50.,50.,20.,20.))
    assert not proof["cone_proved"]
    assert factor==1


def test_moving_tilted_emitters_and_contour_event_boundaries():
    box=(100.,110.,-30.,-20.)
    for wind in ((0.,0.),(2.,1.),(-5.,3.)):
        fuel={"wind_xy":wind}
        big=W.flux_enclosure(box,(0.,12.52),MEMBER,GRID,fuel)
        for time in (0.,.1,.5,1.,11.52,11.6,12.,12.52):
            q=W.flux_at_points([[100.,-30.],[105.,-25.],[110.,-20.]],[time],MEMBER,GRID,fuel)
            assert np.all(q>=big[0]) and np.all(q<=big[1])
            small=W.flux_enclosure((102.,108.,-28.,-22.),(time,time),MEMBER,GRID,fuel)
            assert small[1]<=big[1]


def test_rotated_sheared_grid_containment():
    grid=(20.,3.,1e6,2.,-20.,2e6)
    fuel={"wind_xy":(3.,-1.)}
    box=(1001000.,1001010.,1999980.,1999990.)
    bound=W.flux_enclosure(box,(.1,.9),MEMBER,grid,fuel)
    q=W.flux_at_points([[1001005.,1999985.]],[.1,.4,.9],MEMBER,grid,fuel)
    assert np.all(q>=bound[0]) and np.all(q<=bound[1])


def test_large_common_translation_does_not_change_point_flux():
    shift=2.**40
    fuel={"wind_xy":(2.,1.)}
    expected=W.flux_at_points([[100.,-25.]],[.5],MEMBER,GRID,fuel)
    translated=(20.,0.,shift,0.,20.,shift)
    actual=W.flux_at_points([[shift+100.,shift-25.]],[.5],MEMBER,translated,fuel)
    np.testing.assert_array_equal(actual,expected)


def test_atan_and_pi_directed_intervals_have_proved_series_tails():
    a=_Arithmetic(64)
    pi=_pi(a)
    # Independent long decimal reference lies strictly inside the certified
    # interval after coarsening to a shorter Decimal precision.
    b=_Arithmetic(20);wide=_pi(b)
    assert wide.lo<pi.lo<pi.hi<wide.hi
    angle=_atan_unit(a,a(Fraction(1,5)))
    reference=sum(((-1)**n*Fraction(1,5)**(2*n+1)/(2*n+1) for n in range(60)),Fraction(0))
    tail=Fraction(1,5)**121/121
    assert Fraction(angle.lo)<=reference<=reference+tail<=Fraction(angle.hi)


def test_extreme_time_overflow_refuses_both_operators():
    member={"ignition_time_s":np.full((2,2),1e308),"residence_s":1.}
    for operation in (lambda:W.flux_at_points([[100.,100.]],[-1e308],member,GRID),lambda:W.flux_enclosure((90.,110.,90.,110.),(-1e308,-1e308),member,GRID)):
        try:operation()
        except W.UnsupportedGeometry:pass
        else:raise AssertionError("unsupported contour arithmetic was accepted")
