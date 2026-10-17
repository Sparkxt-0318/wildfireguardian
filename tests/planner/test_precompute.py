"""planner/scripts/precompute.py resumability (no network): finished units are reused, forgotten (404) and
frozen (served from job.json after an API restart, never continued) jobs are resubmitted."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('precompute', ROOT / 'planner' / 'scripts' / 'precompute.py')
pre = importlib.util.module_from_spec(spec)
sys.modules['precompute'] = pre
spec.loader.exec_module(pre)


class FakeApi:
    """Minimal stand-in for the Route-Check API: jobs finish on the second poll unless frozen."""

    def __init__(self, frozen=(), live_work=False):
        self.jobs, self.posts, self.frozen, self.live_work, self.n = {}, [], set(frozen), live_work, 0
        for jid in self.frozen:
            self.jobs[jid] = {'job_id': jid, 'status': 'running', 'polls': 0}

    def get(self, path):
        if path == '/health':
            busy = self.live_work or any(j['status'] != 'done' and j['job_id'] not in self.frozen for j in self.jobs.values())
            return {'status': 'ok', 'queued_tasks': 0, 'jobs': {'running': 1} if busy else {'done': 1}}
        jid = path.rsplit('/', 1)[-1]
        if jid not in self.jobs:
            raise pre.ApiError(404, {'error': {'code': 'JOB_NOT_FOUND'}})
        j = self.jobs[jid]
        if jid not in self.frozen:
            j['polls'] += 1
            if j['polls'] >= 2:
                j['status'] = 'done'
                j['result'] = {'verdict': 'unresolved', 'reason_code': 'OTHER'}
        return dict(j)

    def post(self, path, body):
        self.n += 1
        jid = f'rc_new{self.n}'
        self.posts.append(body)
        self.jobs[jid] = {'job_id': jid, 'status': 'queued', 'polls': 0}
        return {'job_id': jid, 'status': 'queued'}


def unit(i):
    return {'key': f'rc_{i}', 'kind': 'route_check', 'body': {'i': i}}


def test_frozen_inflight_job_is_resubmitted(tmp_path):
    state = pre.State(tmp_path)
    state.set_inflight('rc_0', 'rc_old', 'route_check')
    api = FakeApi(frozen={'rc_old'})
    pre.run_units(api, state, [unit(0)], poll_s=0, timeout_s=30, label='t')
    assert api.posts == [{'i': 0}]                      # resubmitted once
    assert state.done('rc_0')['job']['status'] == 'done'
    assert 'rc_0' not in state.inflight


def test_live_inflight_job_is_polled_not_resubmitted(tmp_path):
    state = pre.State(tmp_path)
    api = FakeApi()
    api.jobs['rc_live'] = {'job_id': 'rc_live', 'status': 'running', 'polls': 0}
    state.set_inflight('rc_0', 'rc_live', 'route_check')
    pre.run_units(api, state, [unit(0)], poll_s=0, timeout_s=30, label='t')
    assert api.posts == []
    assert state.done('rc_0')['job']['job_id'] == 'rc_live'


def test_forgotten_job_404_is_resubmitted_and_finished_units_skipped(tmp_path):
    state = pre.State(tmp_path)
    state.save_done('rc_1', {'kind': 'route_check', 'job': {'job_id': 'x', 'status': 'done'}})
    state.set_inflight('rc_0', 'rc_gone', 'route_check')
    api = FakeApi()
    pre.run_units(api, state, [unit(0), unit(1)], poll_s=0, timeout_s=30, label='t')
    assert api.posts == [{'i': 0}]                      # unit 1 was already finished
    assert state.done('rc_0')['job']['status'] == 'done'


def test_frozen_detection_waits_while_api_reports_live_work():
    assert pre.is_stale({'status': 'running'}, live=False) is True
    assert pre.is_stale({'status': 'running'}, live=True) is False
    assert pre.is_stale({'status': 'done'}, live=False) is False
    assert pre.is_stale(None, live=False) is False
