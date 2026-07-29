from __future__ import annotations
import os, re, threading
import cv2
import numpy as np

CLIP_SLOTS = 64
_SLOT_RE = re.compile(r'^(\d+)[_\-]?')

class VideoPlayer:
    def __init__(self, clips_dir: str):
        self._clips_dir = clips_dir
        self._caps: dict[int, cv2.VideoCapture] = {}
        self._fpss: dict[int, float] = {}
        self._frame_counts: dict[int, int] = {}
        self._clip_names: list[str | None] = [None] * CLIP_SLOTS
        self._active_slot: int | None = None
        self._brightness: float = 1.0
        self._lock = threading.Lock()
        self._open_clips()

    def _open_clips(self) -> None:
        try:
            files = sorted(os.listdir(self._clips_dir))
        except FileNotFoundError:
            return
        for fname in files:
            m = _SLOT_RE.match(fname)
            if not m:
                continue
            slot = int(m.group(1))
            if slot >= CLIP_SLOTS:
                continue
            path = os.path.join(self._clips_dir, fname)
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                continue
            self._caps[slot] = cap
            self._fpss[slot] = cap.get(cv2.CAP_PROP_FPS) or 24.0
            self._frame_counts[slot] = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
            self._clip_names[slot] = fname

    def scan_clips(self) -> list[str | None]:
        return self._clip_names[:]

    def trigger(self, slot: int, brightness: float = 1.0) -> None:
        with self._lock:
            if slot not in self._caps:
                return
            self._active_slot = slot
            self._brightness = brightness
            self._caps[slot].set(cv2.CAP_PROP_POS_FRAMES, 0)

    def stop(self, slot: int) -> None:
        with self._lock:
            if self._active_slot == slot:
                self._active_slot = None

    def get_frame(self, H: int, W: int, elapsed: float) -> np.ndarray | None:
        with self._lock:
            if self._active_slot is None:
                return None
            slot = self._active_slot
            cap = self._caps[slot]
            fps = self._fpss[slot]
            total = self._frame_counts[slot]
            target = int(elapsed * fps) % total
            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    return None
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (W, H), interpolation=cv2.INTER_LINEAR)
            if self._brightness < 0.999:
                frame = (frame.astype(np.float32) * self._brightness).clip(0,255).astype(np.uint8)
            return frame
