"""Portable CPU/MPS/CUDA kernel search entry point.

This lightweight entry configures the MPS fallback before importing PyTorch.
The same command can then select the available backend and relocate a copied
cache without editing its original metadata or the frozen training sources.
"""
from __future__ import annotations

import os


def main():
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    from .probability_model.kernel_search_portable import main as run_search

    run_search()


if __name__ == "__main__":
    main()
