# Opt-in known-footprint contact mode

`wfg_sipp.known_footprint.KnownFootprintSource` and `plan_contact_route` implement
the reviewed cell-local contact proposal in
`research/sipp-routing/KNOWN_FOOTPRINT_CONTACT_PLAN.md`. The strict bridge and
ordinary SIPP entry point keep their existing all-domain support admission.
The new object is default-unsupported and cannot be indexed as a full-policy
hazard packet. The ordinary sweep entry point explicitly refuses this object.

Callers first pin the original export/record, graph/request and native metadata.
Supply the original selected full-native-grid trajectory rows and their saved
integer identities, raw cutoff activity/validity fields, affine and EPSG. Pass
the exact existing inclusive regional window, when present. The constructor
copies each raw array to an immutable bytes owner, records its digest and
checks the exact graph/source spatial and cutoff-clock binding at planning
and checking. It does not infer source file authenticity from a caller-supplied
identity dictionary. The campaign controller remains responsible for file pins
and selection provenance; no native campaign is included in this change.

```python
from wfg_sipp.known_footprint import KnownFootprintSource, plan_contact_route

source = KnownFootprintSource(
    selected_original_full_grid_arrays,
    trajectory_indices=original_indices,
    cutoff_utc=original_cutoff,
    epsg=original_epsg,
    source_horizon_s=original_source_horizon,
    burning_duration_s=original_settings["burning_duration_s"],
    seed=original_settings["seed"],
    timing=original_settings["timing"],
    initial_remaining_s=original_max_remaining_enclosure,
    window=original_integer_window_or_none,
    terminal_inclusive=True,
    source_identity=pinned_original_file_identities,
)
result = plan_contact_route(original_graph, original_request, source, method="sipp")
# method="sweep" uses the separately versioned support-restricted copied sweep.
```

For the reviewed Korean panel the fixed source construction is uniform timing,
seed 20261008, horizon 3600 seconds, scalar T = 3970.4642815249267 seconds and
the original source-bound max-remaining enclosure. These values and their
metadata hashes are extracted in KNOWN_FOOTPRINT_SOURCE_PRECONDITIONS.json.
The timing function replays the existing deterministic uniform construction
on the full native grid before taking a regional view. It uses original member
identities, so first-K prefixes, reordered selections and regional windows
cannot receive new jitter. This is represented sub-hour timing, not an observed
ignition time. Known burned cells with unknown initial age use the explicitly
recorded full-T pessimistic enclosure. No trajectories are generated or copied
to create additional members.

Timing compatibility is with unchanged bridge_v2 construction on that same
full native source, followed by the existing exact window restriction. The
established `integration/src/wfg_latest/packets.py::construct_regional` applies
this full-event-first rule at lines 47-71: it constructs the full event, takes
the exact event-array slice and injects that slice into window construction.
The new fixture compares full bridge_v2 construction and its exact window at
K = 4, 8, 16, 32 and checks every prefix against K = 32. It also verifies the
negative control: independently constructing a newly cropped source changes
the random-draw positions. No timing-equivalence claim is made for that other
domain convention. The earlier strict support censuses depend on raw masks,
so this distinction changes none of their frozen admission evidence. Reference
source hashes and these line ranges are recorded in the adapter receipt.

Spatial barriers are the union of original selected unknown masks and invalid
raw cutoff-state cells. A node must have known support for issue contact,
instantaneous turns, waiting and dwell. An edge must have known support at
every exact chord midpoint occupancy, grid-cut point and endpoint. A closed
all-known rectangle is a sufficient shortcut; otherwise the frozen Fraction
occupancy routine checks the chord. The original graph, ordering, travel
times, incoming-edge state and forbidden turns are retained. Unknown cells
are not represented as flame, and their raw values/masks are never filled.

The support flags feed both solvers identically. The new copied sweep adds
Boolean issue, EDGE, WAIT and destination guards to its unchanged reference
algorithm. SIPP adds whole-clock edge/wait barriers and removes unsupported
destination acceptance. Both share the same represented ContactModel interval
law on known cells. The original frozen sweep and geometry files retain their
hashes. Search is limited to the intersection of the original mission horizon
and every selected member's finite time support, including the full dwell.
The terminal point is allowed only when terminal_inclusive is explicitly true.
The raw value -1 is right-censored through that finite horizon, never global
non-ignition. No final interval is extrapolated.

`check_contact_route` receives the original graph/request and immutable raw
source. It checks structure with the separately copied independent checker,
recomputes that checker's exact geometry and every occupied raw mask cell,
and directly replays uniform timing from raw first-burn values and original
identities. It does not consume the search flags, derived event arrays or
cached contact intervals. It checks issue, all positive-measure closed spans,
all cut/end points, waits and full dwell. Dwell arithmetic uses exact represented
rationals, including at finite horizon equality. Forged support or empty flame
views therefore cannot mint a checked contact result.

Only a completed search followed by this independent check can return
`CHECKED_CONTACT_ROUTE_WITHIN_KNOWN_FOOTPRINT`. Its arrival optimum is limited
to the support-restricted contact problem. Exhaustion, disconnected support,
unsupported endpoints, cap or checker disagreement returns
`UNRESOLVED_RESTRICTED_SUPPORT`. Neither a positive nor a negative result
claims original-domain global optimality or global no-route.

The private search view has no member history identities (`ids=()`). The private
contact request omits thermal incurred histories and thermal budgets instead
of zeroing values or assigning old histories to new trajectory identities.
Position, incoming_edge, departure and as_of remain unchanged. Public
original_request is a verbatim value copy, including every original incurred
and budget field. The history_handling record explicitly says these thermal
fields were omitted, not rebound, and not checked. The source is not a thermal
packet. The result leaves peak, dose, risk and full-policy status unknown even
when the original incurred history already exceeds an original budget. This
entry point checks at-issue and future represented contact only.

Tiny tests and their command, counts, source hashes and custody checks are
recorded in research/sipp-routing/KNOWN_FOOTPRINT_ADAPTER_RECEIPT.json. These
tests include all-known equivalence to the unchanged reference. They do not
establish native temporal feasibility, performance, physical flames, vehicle
width, radiation, policy acceptance or scientific risk. The native paired
K study requires separate independent review and execution authorization.
