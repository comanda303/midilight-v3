from __future__ import annotations
import numpy as np
from state import STROBE_DIVISIONS

def blend(gen: np.ndarray, video: np.ndarray | None, ratio: float) -> np.ndarray:
    if video is None or ratio <= 0.0:
        return gen
    if ratio >= 1.0:
        return video
    g = gen.astype(np.float32)
    v = video.astype(np.float32)
    return ((g * (1.0 - ratio)) + (v * ratio)).clip(0, 255).astype(np.uint8)

def apply_strobe(frame: np.ndarray, t: float, bpm: float,
                 rate_index: int, depth: float, duty: float = 0.5) -> np.ndarray:
    if depth <= 0.0:
        return frame
    division = STROBE_DIVISIONS[max(0, min(rate_index, len(STROBE_DIVISIONS) - 1))]
    beat_dur = 60.0 / bpm
    period = beat_dur * (4.0 / division)
    phase = (t % period) / period
    if phase < duty:
        return frame
    multiplier = 1.0 - depth
    return (frame.astype(np.float32) * multiplier).clip(0, 255).astype(np.uint8)

def apply_master(frame: np.ndarray, master: float) -> np.ndarray:
    if master >= 0.999:
        return frame
    return (frame.astype(np.float32) * master).clip(0, 255).astype(np.uint8)
