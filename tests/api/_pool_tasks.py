"""Tiny pool tasks for the job-manager tests (imported by spawn workers)."""


def raise_system_exit(spec):
    raise SystemExit("PRELAUNCH_INPUT_HASH_MISMATCH test")


def echo(spec):
    return {"status": "done", "echo": spec}
