from __future__ import annotations
import threading
from collections import deque

PULSES_PER_BEAT = 24

class BPMAnalyzer:
    def __init__(self, history: int = 24):
        self._lock = threading.Lock()
        self._pulse_times: deque[float] = deque(maxlen=history + 1)
        self._pulse_count = 0
        self._bpm = 120.0
        self._beat_pending = False
        self._got_pulse = False

    def on_clock_pulse(self, t: float | None = None) -> None:
        import time as _time
        if t is None:
            t = _time.monotonic()
        with self._lock:
            # A gap >0.5s between pulses (< 5 BPM) means the clock was
            # stopped; drop stale history so it doesn't corrupt the average.
            if self._pulse_times and t - self._pulse_times[-1] > 0.5:
                self._pulse_times.clear()
            self._pulse_times.append(t)
            self._got_pulse = True
            self._pulse_count += 1

            if len(self._pulse_times) >= 2:
                intervals = [
                    self._pulse_times[i+1] - self._pulse_times[i]
                    for i in range(len(self._pulse_times) - 1)
                    if self._pulse_times[i+1] > self._pulse_times[i]
                ]
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    self._bpm = 60.0 / (avg_interval * PULSES_PER_BEAT)

            if self._pulse_count % PULSES_PER_BEAT == 0:
                self._beat_pending = True

    def consume_beat(self) -> bool:
        with self._lock:
            if self._beat_pending:
                self._beat_pending = False
                return True
            return False

    @property
    def bpm(self) -> float:
        with self._lock:
            return self._bpm

    @property
    def clock_active(self) -> bool:
        with self._lock:
            return self._got_pulse
