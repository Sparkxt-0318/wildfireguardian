import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("_native_panel", ROOT / "research/sipp-routing/run_native_panel.py")
panel = importlib.util.module_from_spec(spec); spec.loader.exec_module(panel)


def test_successful_child_exiting_between_polls_is_rejected_at_final_boundary():
    # Exit code zero and no earlier sampled stop do not authorize a late result.
    assert panel.completion_stop(30.000001, 100, 101, None) == "DEADLINE_AFTER_EXIT"
    assert panel.completion_stop(30.0, 100, 101, None) == "DEADLINE_AFTER_EXIT"
    assert panel.completion_stop(29.999999, 100, 101, None) is None


def test_peak_rss_visible_only_at_exit_still_rejects_the_result():
    assert panel.completion_stop(1, 100, 3073, None) == "RSS_LIMIT_AFTER_EXIT"
    assert panel.completion_stop(1, 100, 101, "DEADLINE") == "DEADLINE"
