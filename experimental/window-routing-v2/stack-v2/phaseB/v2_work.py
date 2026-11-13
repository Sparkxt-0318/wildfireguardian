"""Kit v2 Step 3 (STEP3_ACCEPTANCE.md): deterministic work budgets, prompt wall checks, and the stage watchdog.

Budget(units_cap, deadline): tick(n) adds n units and raises StageCap('WORK_BUDGET') once units exceed units_cap, or
StageCap(wall_reason) once perf_counter() >= deadline. Units are counts of algorithmic items, never time, so for the
same inputs the unit count at which a work budget stops is identical on any machine.

watchdog(stage, threshold_s): a SIGALRM timer for one stage call; on expiry it raises WatchdogFired in the main
thread. Best-effort: a long C call delays delivery until it returns. Asynchronous: the caller must fail
closed afterwards (no later stage uses state the stage was mutating).
"""
import signal, time
from contextlib import contextmanager


class StageCap(BaseException):   # Thomas 19:16 B3.1: no `except Exception` on the bound-model path may swallow it
    def __init__(self, reason, units=None):
        super().__init__(reason)
        self.reason = reason; self.units = units


class WatchdogFired(BaseException):
    """Thomas 19:16 B5.1: BaseException, distinct from StageCap; caught only by the worker's stage driver."""
    def __init__(self, stage, threshold_s):
        super().__init__('STAGE_CAP_WATCHDOG')
        self.stage = stage; self.threshold_s = threshold_s


class Budget:
    """group_caps (Step 3 correction, Iris 20:02): separate caps per group of kinds, e.g. {'setup': N, 'sweep': M};
    a kind belongs to the group named by its prefix before '_' ('setup_edge' -> 'setup'). Exceeding a group cap raises
    StageCap('WORK_BUDGET_' + GROUP). The first tick time of each group is recorded (setup wall = first sweep tick)."""
    def __init__(self, units_cap=None, deadline=None, wall_reason='WALL_CLOCK', group_caps=None):
        self.units_cap = units_cap; self.deadline = deadline; self.wall_reason = wall_reason
        self.group_caps = dict(group_caps or {}); self.group_units = {}; self.first_tick_s = {}
        self.t0 = time.perf_counter()
        self.units = 0; self.stopped = None; self.by_kind = {}

    def tick(self, n=1, kind=None):
        self.units += n
        if kind is not None:
            self.by_kind[kind] = self.by_kind.get(kind, 0) + n
            g = kind.split('_', 1)[0]
            if g not in self.first_tick_s:
                self.first_tick_s[g] = time.perf_counter() - self.t0
            self.group_units[g] = self.group_units.get(g, 0) + n
            cap = self.group_caps.get(g)
            if cap is not None and self.group_units[g] > cap:
                self.stopped = 'WORK_BUDGET_' + g.upper()
                raise StageCap(self.stopped, self.units)
        if self.units_cap is not None and self.units > self.units_cap:
            self.stopped = 'WORK_BUDGET'
            raise StageCap('WORK_BUDGET', self.units)
        if self.deadline is not None and time.perf_counter() >= self.deadline:
            self.stopped = self.wall_reason
            raise StageCap(self.wall_reason, self.units)

    def record(self):
        return {'units': self.units, 'units_cap': self.units_cap, 'stopped': self.stopped, 'by_kind': dict(self.by_kind),
                'group_units': dict(self.group_units), 'group_caps': dict(self.group_caps),
                'first_tick_s': dict(self.first_tick_s)}


def watchdog_threshold(cap_s):
    """PLAN Step 3: a stage exceeding its cap by more than a factor 1.5 (or 10 s, whichever is larger) is killed."""
    return max(1.5 * cap_s, cap_s + 10.0)


@contextmanager
def watchdog(stage, threshold_s):
    def fire(signum, frame):
        raise WatchdogFired(stage, threshold_s)   # the handler only raises (no IO)
    if signal.getitimer(signal.ITIMER_REAL)[0] > 0:   # Thomas B5.4: never more than one armed alarm
        raise RuntimeError('WATCHDOG_ALREADY_ARMED')
    old = signal.signal(signal.SIGALRM, fire)
    signal.setitimer(signal.ITIMER_REAL, max(1e-3, float(threshold_s)))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
