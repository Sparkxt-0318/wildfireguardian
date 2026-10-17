"""Tiny pool tasks for the job-manager tests (imported by spawn workers)."""


def raise_system_exit(spec):
    raise SystemExit("PRELAUNCH_INPUT_HASH_MISMATCH test")


def echo(spec):
    return {"status": "done", "echo": spec}


def die(spec):
    import os
    os._exit(3)                 # a worker killed mid-task (e.g. by the OOM killer)


def scripted(spec):
    """route_check stand-in: die, report an unconfirmed cleanup, or echo, as the spec says."""
    import os
    action = spec.get("action")
    if action == "die":
        os._exit(3)
    if action == "taint":
        return {"status": "done", "tainted": True, "echo": spec}
    return {"status": "done", "echo": spec}


def sleep_then_echo(spec):
    import time
    time.sleep(spec.get("sleep_s", 2.0))
    return {"status": "done", "echo": spec}
