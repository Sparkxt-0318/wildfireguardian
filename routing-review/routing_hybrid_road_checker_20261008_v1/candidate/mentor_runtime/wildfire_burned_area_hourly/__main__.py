"""Run a workspace workflow: ``python -m wildfire_burned_area_hourly COMMAND``."""

import argparse
from importlib import import_module
import sys


COMMANDS = {
    "load": ("pytorch_loader.example", "Inspect an aligned tensor sequence"),
    "prepare": ("probability_model.prepare_training", "Prepare next-hour training patches"),
    "filter-contact": ("probability_model.filter_contact", "Restrict a cache to burned-neighbor contact"),
    "subset-country": ("probability_model.subset_country", "Select a country's cached partitions"),
    "train": ("probability_model.train", "Fit the exponential probability model"),
    "train-direct": ("probability_model.direct_convolution.train", "Fit the signed direct-convolution model"),
    "evaluate": ("probability_model.evaluate_kernels", "Compare exponential kernels on a common cohort"),
    "evaluate-direct": ("probability_model.direct_convolution.evaluate", "Compare both model families"),
    "report": ("probability_model.report_training", "Report a saved exponential run"),
    "report-kernels": ("probability_model.broader_comparison", "Report an exponential kernel comparison"),
    "report-direct": ("probability_model.direct_convolution.report", "Report a direct-convolution comparison"),
    "verify": ("probability_model.verify_training", "Verify a saved exponential run"),
    "verify-direct": ("probability_model.direct_convolution.verify", "Verify saved direct-convolution runs"),
    "environment": ("environmental_data.acquire_environment", "Acquire or validate environmental rasters"),
    "biome": ("environmental_data.acquire_biome", "Acquire aligned biome classes"),
    "bitmaps": ("scripts.convert_to_bitmaps", "Export raster bitmaps and coordinate sidecars"),
    "build-bundle": ("scripts.build_bundle", "Reconstruct the hourly data bundle"),
}


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Commands:\n" + "\n".join(
            f"  {command:18} {description}" for command, (_, description) in COMMANDS.items()
        ) + "\n\nUse COMMAND --help for that workflow's original options.",
    )
    parser.add_argument("command", choices=COMMANDS, metavar="COMMAND")
    selected = parser.parse_args(arguments[:1]).command
    module = import_module("." + COMMANDS[selected][0], package="wildfire_burned_area_hourly")
    # These original scripts take no arguments. Handle help and reject options
    # before running them, so COMMAND --help cannot start an acquisition/build.
    if selected in ("biome", "build-bundle"):
        argparse.ArgumentParser(
            prog=f"{parser.prog} {selected}", description=module.__doc__,
        ).parse_args(arguments[1:])
    original_argv = sys.argv
    try:
        sys.argv = [f"{parser.prog} {selected}", *arguments[1:]]
        return module.main()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    main()
