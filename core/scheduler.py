"""Simple in-process job scheduler."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, List, Optional


@dataclass
class ScheduledJob:
    job_id: str
    run_at: datetime
    callback: Callable[[], None]
    repeat: Optional[timedelta] = None
    cancelled: bool = False


class BackupScheduler:
    def __init__(self) -> None:
        self._jobs: List[ScheduledJob] = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scheduler")
        self._thread.start()

    def schedule(self, job_id: str, run_at: datetime, callback: Callable[[], None], repeat: Optional[timedelta] = None) -> ScheduledJob:
        sj = ScheduledJob(job_id=job_id, run_at=run_at, callback=callback, repeat=repeat)
        with self._lock:
            self._jobs.append(sj)
        return sj

    def cancel(self, job_id: str) -> None:
        with self._lock:
            for j in self._jobs:
                if j.job_id == job_id:
                    j.cancelled = True

    def _loop(self) -> None:
        while True:
            now = datetime.now()
            due = []
            with self._lock:
                for j in list(self._jobs):
                    if j.cancelled:
                        continue
                    if j.run_at <= now:
                        due.append(j)
                        if j.repeat:
                            j.run_at = now + j.repeat
                        else:
                            j.cancelled = True
            for j in due:
                try:
                    j.callback()
                except Exception:
                    pass
            time.sleep(1)