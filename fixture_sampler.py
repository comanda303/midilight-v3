from __future__ import annotations
import numpy as np

class FixtureSampler:
    def __init__(self, fixtures: list[dict]):
        self._fixtures = fixtures

    def set_fixtures(self, fixtures: list[dict]) -> None:
        self._fixtures = fixtures

    def sample(self, canvas: np.ndarray) -> dict[int, bytes]:
        H, W = canvas.shape[:2]
        universe_bufs: dict[int, bytearray] = {}

        for f in self._fixtures:
            x, y = f['x'], f['y']
            length = f['length']
            orientation = f['orientation']
            universe = f['universe']
            start_ch = f['start_channel']

            if not (0 <= x < W and 0 <= y < H):
                continue

            if orientation == 'H':
                x_end = min(x + length, W)
                pixels = canvas[y, x:x_end]
            else:
                y_end = min(y + length, H)
                pixels = canvas[y:y_end, x]

            if universe not in universe_bufs:
                universe_bufs[universe] = bytearray(512)

            flat = pixels.flatten().tobytes()
            end_ch = start_ch + len(flat)
            if end_ch <= 512:
                universe_bufs[universe][start_ch:end_ch] = flat

        return {u: bytes(buf) for u, buf in universe_bufs.items()}
