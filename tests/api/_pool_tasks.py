"""Tiny pool tasks for the job-manager tests (imported by spawn workers)."""


def raise_system_exit(spec):
    raise SystemExit("PRELAUNCH_INPUT_HASH_MISMATCH test")


def echo(spec):
    return {"status": "done", "echo": spec}


def die(spec):
    import os
    os._exit(3)                 # a worker killed mid-task (e.g. by the OOM killer)
