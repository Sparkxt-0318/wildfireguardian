# Methods

This describes what wfglink computes and how. Every parameter named here lives in `configs/default.yaml` (key in brackets); results and their provenance are in `results/NUMBERS.json`, never in this file.

## 1. Input and timing

- Files are decoded with PyAV and every frame keeps its true presentation time, so variable-frame-rate phone clips are timed correctly. `process --start-seconds/--max-seconds` selects a segment in clip time.
- Repeated frames (a constant-frame-rate re-encode repeats frames) are recognised by counting changed pixels at full resolution: a frame where at most [frames.duplicate_max_px] pixels changed by [frames.duplicate_dn] or more repeats the previous one and is skipped, so it never creates a zero displacement. A thumbnail difference is not used: a few small embers on a static night scene barely change a thumbnail.
- Live cameras run in a source chain (iPhone, USB webcam, labelled replay, synthetic). A source is unhealthy when it raises, delivers no frame for [capture.stale_s], or repeats its frame exactly for [capture.freeze_s]; it is retried with backoff and a better source takes over again only after [capture.switch_back_s] of continuous health.

## 2. Detection (`detect/candidates.py`)

1. Luma background by an approximate running median (each pixel moves [detect.background.step_dn] toward the current frame). An exact running median is available for file mode.
2. Optional matched filter: a Gaussian of [detect.prefilter_sigma_px] on the luma before background subtraction. Compressed video noise is heavy tailed (DCT ringing around single pixels); the filter raises the per-pixel SNR of blob-like embers and suppresses the ringing.
3. Positive residual, then a white top-hat of [detect.tophat_kernel_px] that removes structures wider than an ember (flames, halos).
4. Noise maps per tile ([detect.noise.tiles]) from the median absolute deviation of the residual, refreshed every [detect.noise.update_every] frames. Components grow above [detect.threshold.k_grow] sigma and must reach [detect.threshold.k_seed] sigma (and [detect.threshold.min_seed_dn]) somewhere.
5. Large bright regions (flames, headlights, glare) are found at quarter resolution by area and thickness and masked with a margin; long thin streaks of fast embers are kept.
6. Per component: intensity-weighted centroid and second moments of the signed residual in a window dilated by [detect.components.moment_dilate_px]; streak length L = sqrt(12 (l1 - l2)) from the eigenvalues, orientation mod 180 degrees. Saturation is flagged when at least [detect.saturation.flag_min_px] pixels have their brightest color channel at [detect.saturation.level_dn] or above (orange embers clip red long before luma). Color is a confidence score only.
7. File mode, optional ([detect.streaks.refine]): the moments are recomputed without a threshold inside a rectangle along the streak that reaches [detect.streaks.margin_sigma] PSF widths past its ends, because the faint ends of a long streak fall below the threshold and shorten it.

## 3. Tracking (`track/`)

Constant-velocity Kalman filter per track with the true time step; process noise [track.accel_sigma_px]. Assignment by the Hungarian method on the squared Mahalanobis distance gated at [track.gate_chi2], plus [track.angle_penalty_cost] when a streak's axis disagrees with the predicted motion by more than [track.angle_penalty_deg]. A new track's second detection is searched within max([track.birth_radius_px], [track.birth_length_factor] L) per frame; without an exposure estimate the length term is divided by [track.birth_duty_min], because a streak from a partial exposure is shorter than the frame-to-frame displacement. Confirmation after [track.confirm_hits] hits in [track.confirm_window] frames; coasting for at most [track.max_coast] frames. A track that moves slower than [track.static_speed_px_s] for [track.static_seconds] is a static light and is never counted.

## 4. Velocity (`measure/velocity.py`)

- Track velocity per point: local polynomial of degree [velocity.savgol_order] over [velocity.savgol_window] points on the actual timestamps (the Savitzky-Golay derivative for even spacing). On circular motion this filter has a known gain below 1, which the LED turntable analysis divides out using each track's own angular rate.
- Streak speed L / T_exp along the streak axis, signed by the track direction. Streaks are chosen by their predicted length T_exp |v_track| above [velocity.streak_min_length_px] with a measured length at least [velocity.streak_min_fraction] of it; choosing by measured length would keep short streaks whose length noise happened to be positive. Saturated points are excluded.
- Track-only, streak-only and fused speeds are reported separately; fusion (inverse-variance) is used only for tracks shorter than [velocity.fuse_max_points] points, with the exposure uncertainty carried as a shared error.

## 5. Exposure time (`measure/exposure.py`)

T_exp from metadata when known, otherwise a robust Deming regression through the origin of streak length on per-point track speed over [velocity.exposure.window_s], with points selected by predicted length (not measured length), outliers removed, and a bootstrap over tracks for the interval. When too few tracks have long enough streaks, the estimate is declined rather than reported. File mode runs twice: the first pass estimates T_exp, the second tracks with it (the tracker then knows how far a streak of that exposure travels per frame).

## 6. Gate counts and flux (`measure/gate.py`)

A line gate counts each track once per direction, with a hysteresis band of [gate.hysteresis_px] so jitter on the line cannot double count. Reported: count rate (crossings per second over the last [gate.rate_window_s]), Cumulative Particle Count (gate) gross and net with Garwood intervals, and Particle Number Flux (projected, 2D): crossings per second per unit gate length in the picture, with an interval from the union of the Garwood and moving-block bootstrap intervals. The names mirror NIST's, but NIST's quantities are per square meter through a 3D surface, so ours are analogous, not comparable. Counts include only embers that glow and are seen, so they are lower bounds.

## 7. Ember velocity field (`measure/field.py`)

A grid of [field.grid] cells. One sample per track per cell (the mean of its per-point velocities there), outliers per component beyond [field.mad_k] robust standard deviations (never within [field.mad_floor_px_s]), the cell median, and the normalised median test against the 8 neighbours ([field.normalized_median_threshold], [field.normalized_median_eps_px_s]). Cells with fewer than [field.min_tracks_show] tracks are hidden, cells with up to [field.min_tracks_ci] - 1 are shown hatched without an interval, and larger cells get a bootstrap interval. The horizontal component is the wind proxy; the vertical component includes settling and is biased downward. The field is labelled "Ember-derived air velocity (estimate)".

## 8. Scale (`measure/calibration.py`)

Pixels by default. An ember's meters per pixel follow only from an assumed distance range [Z_min, Z_max] and the focal length f in pixels (m/px = Z / f); speeds are then reported as an interval at that range. Road markings give the camera's height and pitch through a ground-plane pose fit with a Monte Carlo interval (click noise, focal length, road scale), for the road geometry only: they never scale airborne embers.

## 9. Booth mode (`screen/`, `ui/`)

`booth-prep` overlays a 4x4 ArUco marker and a Gray-coded 16-bit frame index with parity in each corner of the clip and holds each source frame for [booth.hold_factor] video frames (0.5x playback for 2). The live pipeline rectifies the filmed screen with the markers, reads the four codes, analyses only clean frames (all codes agree, no gray cell), uses source timestamps from the sidecar for velocities, skips repeated indices and restarts tracking when the clip loops. Streak speed and exposure estimation are off in booth mode because the camera adds its own smear.

## 10. Validation (`validate/`, `synth/`)

Synthetic clips with ground truth (`synth/`): divergence-free flows, embers with quadratic drag and terminal velocities, flicker, pixel-integrated rendering with motion blur, scene distractors, camera noise and gamma, H.264. Three suites: core (tuning only), mismatch (never tuned; headline numbers) and coverage (interval coverage of counts). Metrics: detection F1 over visible embers, completeness against ember SNR, false detections per megapixel per frame, CLEAR MOT, track and streak speed errors, direction error, exposure error, gate count and flux errors against all visible and against bright embers only, and field RMSE against the true ember and air fields. Real-world checks: an LED turntable of known speed (iPhone and dashcam), a dashcam night drive as a hard negative, and plausibility checks on real clips.
