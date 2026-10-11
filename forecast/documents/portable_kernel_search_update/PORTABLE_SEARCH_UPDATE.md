# Portable kernel search update

This update adds a portable entry and hash-checked cache relocation. It does not
replace the existing training runner, model code, original cache, or results.

Place this ZIP in the project directory on the destination machine and extract:

    unzip -o portable_kernel_search_update.zip

Use the Python environment created for that machine. From the project directory:

    .venv/bin/python -m wildfire_burned_area_hourly.portable_search run --device auto --check-only
    .venv/bin/python -m wildfire_burned_area_hourly.portable_search run --device auto

With an activated environment, `python` works in place of `.venv/bin/python`.
On Windows, use `.venv\Scripts\python.exe` or an activated environment.

Defaults preserve peak rates 0.001, 0.003, 0.01, 0.03; constant and warmup_cosine;
warmup 32; minimum rate factor 0.01; 512 initial epochs; 4096 finalist epochs;
seed 7. Auto selects CUDA, then MPS, then CPU. To require CUDA, use --device cuda.
The public entry sets the MPS fallback before PyTorch imports; explicit environment
settings are retained. Python 3.12 and a compatible local PyTorch installation are
required. CUDA/MPS require the corresponding compatible hardware and runtime.

Copy the original prepared_all cache and the complete environmental_data directory
with the project. Defaults locate both relative to this checkout, so metadata may
still contain its original macOS root. Every original source hash is verified at
the new root; the three NPZ files are copied unchanged; only cloned metadata.data_root
changes. The source cache remains unchanged. No held-out outcomes are inspected by
relocation. If inputs are elsewhere, add --data-root /path/to/environmental_data and
--cache /path/to/original/prepared_all. That cache must retain the original four
verified file hashes. Do not disable checks or modify source hash entries.

The launcher prints its relocated cache and experiment output locations. Defaults
separate devices and physical cache paths, including when old result directories
are copied to a new machine. Repeating the same command at the same location resumes
the same run. A different training device starts a new run under the existing
same-device optimizer continuation contract. Explicit --portable-cache and --output
are available, but incompatible existing cache/protocol bindings are refused.

--check-only verifies availability, relocation and the proposed experiment setup.
It does not train or modify the intended experiment output. Its trial protocol is
temporary. Use smoke instead of run for a reduced end-to-end execution check.

Verification: 90 tests passed on macOS/CPU, including an actual small 46-candidate
search, six finalist continuations, 28 evaluated/saved models, report/metrics saving,
and repeat resume. Real-cache CLI preflight verified all 486 original source files
and all original NPZ hashes at a different physical data root. CUDA/MPS automatic
selection was tested with availability mocks; CUDA execution was not tested on this
Mac. The full 512/4096 epoch search was not launched by the update workflow.
