"""Tests for the background job runner (src/jobs.py)."""

import time

import pytest

from src.jobs import JobManager, TERMINAL


def _wait_for(job, statuses=TERMINAL, timeout=5.0):
    """Poll until the job reaches one of `statuses`, or time out."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if job.status in statuses:
            return True
        time.sleep(0.02)
    return False


def test_successful_job_records_result():
    mgr = JobManager()
    job = mgr.submit("test", "adds numbers", lambda j: 2 + 2)

    assert _wait_for(job), f"job never finished (status={job.status})"
    assert job.status == "succeeded"
    assert job.result == 4
    assert job.error is None
    assert job.finished_at is not None


def test_failing_job_records_error_not_result():
    mgr = JobManager()

    def boom(_job):
        raise ValueError("no good")

    job = mgr.submit("test", "raises", boom)

    assert _wait_for(job)
    assert job.status == "failed"
    assert job.result is None
    assert "ValueError" in job.error and "no good" in job.error


def test_cancel_marks_job_cancelled_when_worker_cooperates():
    """
    Cancellation is cooperative: the worker watches job._cancel and returns.
    A worker that stops early must not be reported as a success.
    """
    mgr = JobManager()

    def cooperative(job):
        for _ in range(500):
            if job._cancel.is_set():
                return "stopped early"
            time.sleep(0.01)
        return "ran to completion"

    job = mgr.submit("test", "cancellable", cooperative)
    # Give the thread a moment to actually start before cancelling.
    time.sleep(0.05)
    assert mgr.cancel(job.job_id) is True

    assert _wait_for(job)
    assert job.status == "cancelled"


def test_cancel_returns_false_for_finished_or_unknown_job():
    mgr = JobManager()
    job = mgr.submit("test", "quick", lambda j: 1)
    assert _wait_for(job)

    assert mgr.cancel(job.job_id) is False   # already finished
    assert mgr.cancel("does-not-exist") is False


def test_list_returns_newest_first():
    mgr = JobManager()
    for i in range(3):
        mgr.submit("test", f"job-{i}", lambda j: None)
        time.sleep(1.05)  # created_at has second resolution

    labels = [j.label for j in mgr.list()]
    assert labels == ["job-2", "job-1", "job-0"]


def test_completed_jobs_are_evicted_past_the_cap():
    """Finished jobs must not accumulate without bound."""
    mgr = JobManager(max_completed=3)
    jobs = [mgr.submit("test", f"j{i}", lambda j: i) for i in range(8)]
    for job in jobs:
        assert _wait_for(job)

    # Eviction runs as each job finishes, so allow the last few to settle.
    time.sleep(0.2)
    assert len(mgr.list()) <= 3


def test_to_dict_can_omit_the_result_payload():
    mgr = JobManager()
    job = mgr.submit("test", "big result", lambda j: list(range(1000)))
    assert _wait_for(job)

    assert "result" in job.to_dict()
    assert "result" not in job.to_dict(include_result=False)
