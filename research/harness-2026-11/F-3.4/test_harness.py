"""Unit checks for the F-3.4 harness (stdlib only): cd research/harness-2026-11/F-3.4 && python3 -m unittest test_harness -v"""
import importlib.util, sys, types, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class SummarizeTest(unittest.TestCase):
    def row(self):
        timers = {'routing.validation.validate_hazard': {'total_s': 0.2}, 'routing.validation.validate_request': {'total_s': 0.01},
                  'clock_scope.check_clock_scope': {'total_s': 0.0}, 'adaptive_checker.adaptive_bound': {'total_s': 0.5}}
        return {'complete_wall_s': 10.0, 'worker_import_start_from_outer_s': 0.05,
                'phase_timers': {'interpreter_first_statement_from_outer_s': 0.02, 'timers': timers},
                'checkpoints_from_outer_s': {'IMPORTED': 0.07, 'INPUTS_BOUND': 0.3, 'ADMITTED': 1.5, 'ROAD_CHECK_RETURNED': 9.0},
                'worker_stages_s': {'normal_admission_clock_s': 1.0, 'bound_model_construction_s': 0.3, 'whole_road_check_Z_s': 5.0,
                                    'publication_contract_s': 0.4, 'earliest_arrival_bound_s': 0.1},
                'preparation': {'total_s': 0.7}, 'rda_stages': [{'stage': 'Z', 'elapsed_s': 1.2}],
                'whole_road': {'timing_s': {'source_preparation_and_binding': 0.3, 'mission_validation': 0.2, 'contact_check': 1.0,
                                            'radiation_preparation': 0.1, 'radiation_check': 2.5}},
                'publication_boundary': {'elapsed_from_outer_after_result_publication_s': 9.6}}

    def test_exclusive_phases_sum_to_wall(self):
        S = load('summarize')
        p = S.phases(self.row())
        self.assertAlmostEqual(sum(p.values()), 10.0, places=9)
        self.assertAlmostEqual(p['graph_preparation'], 1.0 - 0.2 - 0.01)
        self.assertAlmostEqual(p['check_adaptive_fallback'], 0.5)
        self.assertAlmostEqual(p['check_other'], 5.0 - (0.5 + 1.0 + 0.1 + 2.5 + 0.5))
        self.assertAlmostEqual(p['search'], 1.3)
        self.assertEqual(set(p), {k for k, _ in S.PHASES})

    def test_groups_partition_phases(self):
        S = load('summarize')
        flat = [k for ks in S.groups().values() for k in ks]
        self.assertEqual(sorted(flat), sorted(k for k, _ in S.PHASES))


class TimerTest(unittest.TestCase):
    def test_wrap_preserves_result_and_counts(self):
        W = load('phase_worker')
        mod = types.ModuleType('m'); mod.f = lambda x: x + 1
        class C:
            def g(self, y): return 2 * y
            @staticmethod
            def h(z): return -z
        mod.C = C
        W._patch(mod, ['f', 'C.g', 'C.h', 'missing'])
        self.assertEqual(mod.f(1), 2); self.assertEqual(C().g(3), 6); self.assertEqual(C.h(4), -4)
        self.assertEqual(W.TIMERS['m.f']['calls'], 1); self.assertEqual(W.TIMERS['m.C.g']['calls'], 1)
        W._patch(mod, ['f']); mod.f(0)
        self.assertEqual(W.TIMERS['m.f']['calls'], 2)   # not double-wrapped


if __name__ == '__main__':
    unittest.main()
