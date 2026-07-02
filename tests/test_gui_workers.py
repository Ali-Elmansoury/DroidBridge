# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.gui.workers.Worker (Phase 6.1)."""

from droidbridge.gui.workers import Worker


class TestWorker:
    def test_runs_fn_and_emits_finished_with_result(self, qtbot):
        worker = Worker(lambda: 42)

        with qtbot.waitSignal(worker.finished, timeout=2000) as blocker:
            worker.start()

        worker.wait()
        assert blocker.args == [42]

    def test_passes_args_and_kwargs_to_fn(self, qtbot):
        worker = Worker(lambda a, b, c=0: a + b + c, 1, 2, c=3)

        with qtbot.waitSignal(worker.finished, timeout=2000) as blocker:
            worker.start()

        worker.wait()
        assert blocker.args == [6]

    def test_exception_emits_error_signal(self, qtbot):
        def boom():
            raise ValueError("boom")

        worker = Worker(boom)

        with qtbot.waitSignal(worker.error, timeout=2000) as blocker:
            worker.start()

        worker.wait()
        assert isinstance(blocker.args[0], ValueError)
        assert str(blocker.args[0]) == "boom"


class TestWorkerProgress:
    def test_report_progress_emits_progress_then_finished(self, qtbot):
        def fn(progress_callback=None):
            progress_callback("x")
            progress_callback("y")
            return "done"

        worker = Worker(fn, report_progress=True)

        progress_events = []
        worker.progress.connect(progress_events.append)

        with qtbot.waitSignal(worker.finished, timeout=2000) as blocker:
            worker.start()

        worker.wait()
        assert progress_events == ["x", "y"]
        assert blocker.args == ["done"]

    def test_report_progress_false_does_not_inject_callback(self, qtbot):
        worker = Worker(lambda: 42, report_progress=False)

        with qtbot.waitSignal(worker.finished, timeout=2000) as blocker:
            worker.start()

        worker.wait()
        assert blocker.args == [42]
