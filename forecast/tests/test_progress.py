"""Progress displays report work honestly and do not alter model execution."""
import io
import threading

import pytest

from wildfire.progress import Activity, ProgressBar


class Terminal(io.StringIO):
    def isatty(self):
        return True


@pytest.fixture
def clock(monkeypatch):
    now = [100.]
    monkeypatch.setattr("wildfire.progress.time.monotonic", lambda: now[0])
    return now


def test_bar_reports_absolute_count_eta_and_closes(clock):
    stream = io.StringIO()
    with ProgressBar(10, "Intervals", stream=stream, min_interval=0) as bar:
        clock[0] += 4
        bar.advance(2)
        clock[0] += 6
        bar.update(5)
    output = stream.getvalue()
    assert "2/10 (20.0%) elapsed 00:00:04 ETA 00:00:16" in output
    assert "5/10 (50.0%) elapsed 00:00:10 ETA 00:00:10 [complete]" in output
    assert bar.completed == 5
    assert "\r" not in output
    before = output
    bar.close()
    bar.advance()
    assert stream.getvalue() == before


def test_redirected_output_throttles_updates_but_always_finishes(clock):
    stream = io.StringIO()
    with ProgressBar(4, stream=stream) as bar:
        for _ in range(3):
            clock[0] += 1
            bar.advance()
        assert len(stream.getvalue().splitlines()) == 1
        clock[0] += 8
        bar.update(3)
        assert "3/4" in stream.getvalue()
        clock[0] += 1
        bar.advance()
    assert "4/4 (100.0%)" in stream.getvalue()
    assert stream.getvalue().endswith("[complete]\n")


def test_terminal_updates_and_nested_messages_remain_readable(clock):
    stream = Terminal()
    with ProgressBar(2, "Intervals", stream=stream, min_interval=0) as outer:
        with ProgressBar(4, "M548", stream=stream, min_interval=0) as inner:
            inner.advance()
            inner.write("Preparing inputs")
            inner.update(4)
        outer.advance()
        outer.set_description("Pooling metrics")
        outer.advance()
    output = stream.getvalue()
    assert "\r" in output
    assert "Preparing inputs\n" in output
    assert "M548" in output and "Pooling metrics" in output
    assert output.endswith("[complete]\n")


def test_context_failure_retains_partial_count(clock):
    stream = io.StringIO()
    with pytest.raises(RuntimeError, match="model failed"):
        with ProgressBar(5, stream=stream, min_interval=0) as bar:
            bar.advance(2)
            raise RuntimeError("model failed")
    assert "2/5 (40.0%)" in stream.getvalue()
    assert stream.getvalue().endswith("[failed]\n")


def test_keyboard_interruption_is_reported(clock):
    stream = io.StringIO()
    with pytest.raises(KeyboardInterrupt):
        with ProgressBar(1, stream=stream):
            raise KeyboardInterrupt
    assert stream.getvalue().endswith("[interrupted]\n")


def test_activity_displays_no_percent_or_eta_and_stops_thread():
    stream = io.StringIO()
    with Activity("FARSITE", stream=stream, min_interval=.05) as activity:
        assert activity._thread.is_alive()
        activity.set_description("FARSITE native engine")
    assert not activity._thread.is_alive()
    assert activity._stop.is_set()
    output = stream.getvalue()
    assert "FARSITE native engine [complete] elapsed" in output
    assert "%" not in output and "ETA" not in output
    before = output
    activity.close()
    assert stream.getvalue() == before


def test_activity_failure_stops_thread(clock):
    stream = io.StringIO()
    with pytest.raises(ValueError):
        with Activity("FARSITE", stream=stream) as activity:
            raise ValueError("bad input")
    assert not activity._thread.is_alive()
    assert stream.getvalue().endswith("[failed] elapsed 00:00:00\n")


def test_disabled_displays_have_no_output_or_thread():
    stream = io.StringIO()
    with ProgressBar(3, enabled=False, stream=stream) as bar:
        bar.advance()
        bar.write("Invisible")
    with Activity(enabled=False, stream=stream) as activity:
        activity.write("Invisible")
    assert stream.getvalue() == ""
    assert activity._thread is None


@pytest.mark.parametrize("kwargs", [{"total": True}, {"total": -1}, {"total": .5},
                                  {"total": 1, "min_interval": -1},
                                  {"total": 1, "min_interval": float("nan")}])
def test_invalid_progress_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        ProgressBar(**kwargs, enabled=False)


def test_invalid_updates_are_rejected_without_changing_count():
    bar = ProgressBar(2, enabled=False)
    for value in (True, -1, 3, .5):
        with pytest.raises(ValueError):
            bar.update(value)
    assert bar.completed == 0


def test_closed_stream_disables_display_without_failing_work():
    stream = io.StringIO()
    stream.close()
    with ProgressBar(1, stream=stream) as bar:
        bar.advance()
    assert not bar.enabled
    assert bar.completed == 1


def test_activity_heartbeat_obeys_sparse_log_interval(clock):
    stream = io.StringIO()
    activity = Activity("Native", stream=stream)
    activity._render()
    assert len(stream.getvalue().splitlines()) == 1
    clock[0] += 10
    activity._render()
    assert len(stream.getvalue().splitlines()) == 2
    activity.close()


def test_concurrent_display_messages_are_whole_lines():
    stream = io.StringIO()
    bar = ProgressBar(1, stream=stream)
    workers = [threading.Thread(target=bar.write, args=(f"Message {index}",)) for index in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    bar.close()
    lines = stream.getvalue().splitlines()
    assert {line for line in lines if line.startswith("Message")} == {f"Message {index}" for index in range(8)}
