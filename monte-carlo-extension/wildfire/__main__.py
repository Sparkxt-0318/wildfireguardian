"""Run a wildfire workflow: python -m wildfire COMMAND [OPTIONS]."""
import argparse
from importlib import import_module
import sys

# One command interface keeps workflow functions in their files by job.
COMMANDS = {
    "load": ("examples", "load_main", "Inspect an aligned tensor sequence"),
    "model-example": ("examples", "model_main", "Inspect an unfitted convolution example"),
    "example": ("examples", "api_main", "Predict with a saved model"),
    "heat": ("examples", "heat_main", "Predict incident radiant heat"),
    "flames": ("examples", "flames_main", "Export active-flame scenarios"),
    "radiation": ("examples", "radiation_main", "Run a synthetic radiation example"),
    "prepare": ("prepare", "prepare_main", "Prepare next-hour training patches"),
    "resplit": ("prepare", "resplit_main", "Derive weighted rows with a fixed test partition"),
    "filter-contact": ("prepare", "contact_main", "Restrict a cache to burned-neighbor contact"),
    "subset-country": ("prepare", "country_main", "Select a country's cached partitions"),
    "train": ("train", "train_main", "Fit the exponential probability model"),
    "mix-bayesian": ("train", "bayesian_main", "Average independently fitted kernels by Bayes' rule"),
    "verify": ("train", "verify_training_main", "Verify a saved exponential run"),
    "evaluate": ("evaluate", "kernels_main", "Compare kernels on a common cohort"),
    "evaluate-cumulative": ("cumulative_report", "main", "Evaluate every selected model at an explicit cumulative horizon"),
    "compare": ("evaluate", "baseline_main", "Compare models and random forests"),
    "add-kl": ("evaluate", "add_kl", "Add KL metrics to a saved comparison"),
    "add-distances": ("evaluate", "add_distances", "Add statistical distances to a saved comparison"),
    "add-classification": ("evaluate", "add_classification", "Add classification metrics to a saved comparison"),
    "report": ("report", "training_main", "Report a saved exponential run"),
    "report-kernels": ("report", "comparison_main", "Report a kernel comparison"),
    "report-metrics": ("report", "evaluation_main", "Build a comprehensive evaluation report"),
    "search": ("search", "Search.main", "Search nonnegative kernel models"),
    "search-scheduled": ("search", "ScheduledSearch.main", "Search learning-rate schedules"),
    "search-mixed": ("search", "MixedSearch.main", "Search mixed kernels"),
    "search-multiscale": ("search", "MultiscaleSearch.main", "Search neural multiscale kernels"),
    "search-portable": ("search", "portable_main", "Run the portable search"),
    "search-precision": ("search", "precision_main", "Run the portable search with precision checks"),
    "recover-cache": ("cache", "recover_main", "Restore a verified local cache archive"),
    "relocate-cache": ("cache", "relocate_main", "Relocate a verified training cache"),
    "environment": ("environment", "environment_main", "Acquire or validate environmental rasters"),
    "biome": ("environment", "biome_main", "Acquire aligned biome classes"),
    "audit-data": ("environment", "audit_main", "Audit environmental source quality"),
    "enrich-data": ("environment", "enrich_main", "Enrich environmental layers"),
    "preview-data": ("environment", "preview_main", "Draw environmental previews"),
    "inventory-data": ("environment", "inventory_main", "Refresh biome inventory records"),
    "bitmaps": ("bundle", "bitmaps_main", "Export raster bitmaps and coordinates"),
    "build-bundle": ("bundle", "build_main", "Reconstruct the hourly data bundle"),
    "check-data": ("checks", "data_main", "Validate the real tensor dataset"),
    "check-model": ("checks", "model_main", "Validate the model on real inputs"),
}
ALIASES = {"kernel-search": "search"}
ARGUMENT_FREE = {"biome", "build-bundle", "inventory-data", "audit-data", "preview-data", "check-data"}


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Commands:\n" + "\n".join(f"  {key:20} {value[2]}" for key, value in COMMANDS.items())
        + "\n\nUse COMMAND --help for that workflow's options.",
    )
    parser.add_argument("command", choices=tuple(COMMANDS) + tuple(ALIASES), metavar="COMMAND")
    selected = parser.parse_args(arguments[:1]).command
    selected = ALIASES.get(selected, selected)
    if selected in ARGUMENT_FREE:
        # Parse before importing or invoking acquisition/reconstruction tools.
        argparse.ArgumentParser(prog=f"{parser.prog} {selected}", description=COMMANDS[selected][2]).parse_args(arguments[1:])
    if selected in {"search-portable", "search-precision"}:
        import os
        os.environ.setdefault("MPLBACKEND", "Agg")
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
        if selected == "search-precision":
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    module_name, callable_name, _ = COMMANDS[selected]
    module = import_module("." + module_name, package="wildfire")
    function = module
    for attribute in callable_name.split("."):
        function = getattr(function, attribute)
    if selected in {"add-kl", "add-distances", "add-classification"}:
        from pathlib import Path
        supplement = argparse.ArgumentParser(prog=f"{parser.prog} {selected}", description=COMMANDS[selected][2])
        supplement.add_argument("run_directory", type=Path)
        options = supplement.parse_args(arguments[1:])
        return function(options.run_directory)
    original_argv = sys.argv
    try:
        sys.argv = [f"{parser.prog} {selected}", *arguments[1:]]
        result = function()
        # Console-script entry points pass this return value to sys.exit.
        # The evaluator's result dictionary is for Python callers, not an exit
        # status or an additional dump of the complete comparison report.
        return None if selected == "evaluate-cumulative" else result
    finally:
        sys.argv = original_argv


def heat_main():
    return main(["heat", *sys.argv[1:]])


if __name__ == "__main__":
    main()
