"""Build the two local CPU libraries without installing binary artifacts."""
import argparse
from pathlib import Path
import shlex
import subprocess
import sys

DIRECTORY = Path(__file__).resolve().parent


def build(compiler):
    flags = ["-std=c++17", "-O3", "-fPIC"]
    flags += ["-dynamiclib"] if sys.platform == "darwin" else ["-shared"]
    for name in ("dose", "walk"):
        source = DIRECTORY / f"{name}.cpp"
        output = DIRECTORY / f"{name}.so"
        command = [*shlex.split(compiler), *flags, str(source), "-o", str(output)]
        subprocess.run(command, check=True)
        print(f"Built {output.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++", help="C++ compiler command")
    args = parser.parse_args()
    build(args.cxx)
