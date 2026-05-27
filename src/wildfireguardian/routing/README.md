# `routing` — personalised evacuation routing

**Status**: scaffold only.

**Purpose**: compute a safe and feasible evacuation route from a user's
location to the nearest viable shelter, given the time-varying fire
perimeter and smoke field.

**Inputs**: an OSM road network for the affected region, the user's
starting point and a user profile (age band, mobility, vehicle / on-foot),
the time-resolved fire perimeter from the spread model, and the time-resolved
smoke field from the dispersion model.

**Outputs**: a polyline route, an estimated travel time, and a worst-case
PM2.5 exposure along the route. A "no safe route exists" sentinel is also
possible.

**Algorithmic basis**: time-dependent Dijkstra on the OSM graph with edge
weights = travel time × smoke penalty + ∞ penalty for edges that intersect
the fire perimeter at the projected arrival time. Walking-speed profiles for
elderly users follow Bohannon & Williams Andrews (2011) preferred-pace
norms, age-banded.
