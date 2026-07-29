from __future__ import annotations
import json
from state import AppState

PRESET_SLOTS = 24

class PresetManager:
    def __init__(self, path: str, state: AppState, transition_ms: int = 200):
        self._path = path
        self._state = state
        self._transition_s = transition_ms / 1000.0
        self._presets: list[list[float] | None] = [None] * PRESET_SLOTS
        self._target: list[float] | None = None
        self._source: list[float] | None = None
        self._elapsed = 0.0
        self._interpolating = False
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path) as f:
                data = json.load(f)
                self._presets = data.get('presets', [None] * PRESET_SLOTS)
                while len(self._presets) < PRESET_SLOTS:
                    self._presets.append(None)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_to_disk(self) -> None:
        with open(self._path, 'w') as f:
            json.dump({'presets': self._presets}, f)

    def save(self, slot: int) -> None:
        if 0 <= slot < PRESET_SLOTS:
            self._presets[slot] = self._state.faders[:]
            self._save_to_disk()

    def recall(self, slot: int) -> None:
        if 0 <= slot < PRESET_SLOTS and self._presets[slot] is not None:
            self._source = self._state.faders[:]
            self._target = self._presets[slot][:]
            self._elapsed = 0.0
            self._interpolating = True

    def tick(self, dt: float) -> None:
        if not self._interpolating or self._target is None:
            return
        self._elapsed += dt
        progress = min(self._elapsed / max(self._transition_s, 0.001), 1.0)
        new_faders = [
            self._source[i] + (self._target[i] - self._source[i]) * progress
            for i in range(12)
        ]
        self._state.update(faders=new_faders)
        if progress >= 1.0:
            self._interpolating = False
