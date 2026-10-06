# Mechanical performance benchmark

The benchmark driver and frozen protocol are ready for coordinator review in [benchmark.py](../benchmark.py) and [BENCHMARK_PROTOCOL.json](../evidence/BENCHMARK_PROTOCOL.json). No official timing run has been started. The coordinator must select the frozen source versions and run the driver in the shared exclusive lane.

The comparison retains all 17 frozen fixture cases across four methods: the established legacy vector baseline, integration baseline, matched A-star, and matched Dijkstra. Each case/method/mode combination has three rotated repetitions in fresh subprocesses. Cold mode measures the first public solve call. Warm mode makes one unmeasured call and measures a second call in the same process; it does not imply cross-process cache reuse.

Each child records the public solve call time, process wall time, `ru_maxrss` high-water, result status, reason, arrival, search metrics, and an independent post-hoc route-check outcome. A separate `routing.independent.exhaustive` pass supplies reference outcomes without timing them as part of any method. Missing legacy dependencies, cap outcomes, and child failures stay in their planned rows. Paired time and expansion deltas are emitted for every case, mode, repetition, and method pair, so regressions are not hidden by pooled averages.

No timing or expansion evidence is available yet. The driver uses no optimization variant; any variant requires coordinator selection and a new freeze before comparison. Status refinements and all method/reference disagreements require independent adjudication before interpretation.
