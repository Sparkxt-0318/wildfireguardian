# Note: arrival fields in perimeters/<id>/states.npz

`arrival_hours` and `arrival_std_hours` are all NaN, and `arrival_t0_utc` is an empty string, in every committed `states.npz`. This is intended. `build_nirops_event.py` (L139–141) and `nirops_access/build_nirops_event_v2.py` (L148–150) write these placeholders so that the file has the keys of the `prepare_perimeters` npz format.

The arrival map lives in `data/environment/regions/<id>/arrival_time_hours.tif`: float32, nodata -1, hours since the `t0_utc` tag. For a value-level check, compare `sha256(read(1).astype('<f4').tobytes())`. The tif's file bytes can differ between builds even when the pixels are equal (Hannah's spot-rebuild of 3 incidents: pixel arrays equal, file bytes differ).
