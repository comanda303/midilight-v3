from __future__ import annotations
import threading
from dataclasses import dataclass, field
from typing import Optional

FADER_NAMES = [
    'algorithm', 'beat_react', 'rhythm_density', 'speed',
    'hue', 'saturation', 'color_spread', 'scale',
    'direction', 'symmetry', 'contrast', 'blur_glow',
]

@dataclass
class AppState:
    faders: list[float] = field(default_factory=lambda: [0.5] * 12)
    master: float = 1.0
    blend: float = 0.0
    strobe_rate_index: int = 2
    strobe_depth: float = 1.0
    strobe_duty: float = 0.5
    strobe_active: bool = False
    active_clip: Optional[int] = None
    active_preset: Optional[int] = None
    bpm: float = 120.0
    midi_clock_active: bool = False
    beat: bool = False
    assignments: dict = field(default_factory=dict)
    learn_target: Optional[str] = None

    def __post_init__(self):
        self._lock = threading.Lock()

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def set_assignment(self, name: str, entry: dict) -> None:
        with self._lock:
            self.assignments[name] = entry

    def set_fader(self, index: int, value: float) -> None:
        with self._lock:
            faders = self.faders[:]
            faders[index] = value
            self.faders = faders

    def snapshot(self) -> dict:
        with self._lock:
            return {
                'faders': self.faders[:],
                'master': self.master,
                'blend': self.blend,
                'strobe_rate_index': self.strobe_rate_index,
                'strobe_depth': self.strobe_depth,
                'strobe_duty': self.strobe_duty,
                'strobe_active': self.strobe_active,
                'active_clip': self.active_clip,
                'active_preset': self.active_preset,
                'bpm': self.bpm,
                'midi_clock_active': self.midi_clock_active,
                'assignments': {k: dict(v) for k, v in self.assignments.items()},
                'learn_target': self.learn_target,
            }

    def consume_beat(self) -> bool:
        with self._lock:
            if self.beat:
                self.beat = False
                return True
            return False

STROBE_DIVISIONS = [1, 2, 4, 8, 16, 32]
