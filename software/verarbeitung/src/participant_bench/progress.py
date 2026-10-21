"""Immediate, readable local status output, including long-running activities."""

import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class Progress:
    def __init__(self, log_path: Path | None = None, *, interval_seconds: float = 10, enabled: bool = True):
        if interval_seconds <= 0:
            raise ValueError("Statusintervall muss positiv sein")
        self.log_path = log_path
        self.interval_seconds = interval_seconds
        self.enabled = enabled
        self.started = time.perf_counter()
        self.lock = threading.Lock()

    def log(self, message: str) -> None:
        if not self.enabled:
            return
        with self.lock:
            timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            elapsed = time.perf_counter() - self.started
            message = message.replace("\r", " ").replace("\n", " ")
            line = f"[{timestamp} | +{elapsed:.1f}s] {message}"
            print(line, flush=True)
            if self.log_path:
                with self.log_path.open("a", encoding="utf-8") as stream:
                    stream.write(line + "\n")

    @contextmanager
    def activity(self, label: str):
        if not self.enabled:
            yield
            return
        started = time.perf_counter()
        stop = threading.Event()
        self.log(label + " ...")

        def heartbeat():
            while not stop.wait(self.interval_seconds):
                self.log(f"{label}: läuft weiter, seit {time.perf_counter() - started:.0f}s")

        thread = threading.Thread(target=heartbeat, name="participant-bench-progress", daemon=True)
        thread.start()
        try:
            yield
        except BaseException as exc:
            stop.set()
            thread.join()
            self.log(f"{label}: abgebrochen nach {time.perf_counter() - started:.1f}s ({type(exc).__name__}: {exc})")
            raise
        else:
            stop.set()
            thread.join()
            self.log(f"{label}: fertig nach {time.perf_counter() - started:.1f}s")
