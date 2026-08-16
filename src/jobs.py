"""Background job runner for long operations.

Evolve, grid search and fork-eval each run many full backtests, which can
take minutes — far longer than an HTTP request should hold open. These
endpoints hand the work to a JobManager and return a job id immediately;
the client polls for progress and collects the result when it lands.

Jobs run in daemon threads and live in memory only: a server restart drops
them. That is deliberate — a half-finished parameter search is not worth
persisting, and the results that matter are already written to the sessions
and evaluations directories by the underlying functions.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


log = logging.getLogger(__name__)

# Terminal states are the ones a poller can stop on.
TERMINAL = {"succeeded", "failed", "cancelled"}


@dataclass
class Job:
    job_id: str
    kind: str
    label: str
    status: str = "running"          # running | succeeded | failed | cancelled
    created_at: str = ""
    finished_at: Optional[str] = None
    progress: Optional[str] = None   # free-text note from the worker
    result: Any = None
    error: Optional[str] = None
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self, include_result: bool = True) -> dict:
        d = {
            "job_id": self.job_id,
            "kind": self.kind,
            "label": self.label,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "progress": self.progress,
            "error": self.error,
        }
        if include_result:
            d["result"] = self.result
        return d


class JobManager:
    """Thread-backed job registry. One instance per server process."""

    def __init__(self, max_completed: int = 50):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_completed = max_completed

    # -- lifecycle ------------------------------------------------------

    def submit(self, kind: str, label: str, fn: Callable[..., Any]) -> Job:
        """
        Run fn in a background thread.

        fn is called with a single `job` argument so it can report progress
        and check for cancellation; functions that need neither can ignore it.
        """
        job = Job(
            job_id=uuid.uuid4().hex[:12],
            kind=kind,
            label=label,
            created_at=dt.datetime.now().isoformat(timespec="seconds"),
        )
        with self._lock:
            self._jobs[job.job_id] = job

        def _run():
            try:
                result = fn(job)
                # A worker that honoured a cancel request should not be
                # reported as a success.
                if job._cancel.is_set():
                    job.status = "cancelled"
                else:
                    job.result = result
                    job.status = "succeeded"
            except Exception as e:
                job.status = "failed"
                job.error = f"{type(e).__name__}: {e}"
                # exc_info so the traceback lands in the server log, not stderr.
                log.exception("job %s (%s) failed", job.job_id, job.kind)
            finally:
                job.finished_at = dt.datetime.now().isoformat(timespec="seconds")
                self._evict_old()

        threading.Thread(target=_run, daemon=True).start()
        return job

    def cancel(self, job_id: str) -> bool:
        """
        Ask a job to stop. Cooperative — the worker decides when to notice,
        so the job stays "running" until it does.
        """
        job = self.get(job_id)
        if not job or job.status in TERMINAL:
            return False
        job._cancel.set()
        job.progress = "cancelling…"
        return True

    # -- access ---------------------------------------------------------

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        # Newest first — the UI shows recent activity at the top.
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def _evict_old(self) -> None:
        """Keep finished jobs from growing without bound."""
        with self._lock:
            done = sorted(
                (j for j in self._jobs.values() if j.status in TERMINAL),
                key=lambda j: j.finished_at or "",
            )
            for job in done[: max(0, len(done) - self._max_completed)]:
                self._jobs.pop(job.job_id, None)
