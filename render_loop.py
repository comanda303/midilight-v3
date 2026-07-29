from __future__ import annotations
import threading
import time
import numpy as np
from state import AppState
from bpm_analyzer import BPMAnalyzer
from generator import Generator
from video_player import VideoPlayer
from fixture_sampler import FixtureSampler
from artnet_output import ArtNetSender
from preset_manager import PresetManager
from compositor import blend, apply_strobe, apply_master

FPS = 30
THUMB_H, THUMB_W = 24, 48
THUMB_CYCLE_SECONDS = 5.0

class RenderLoop:
    def __init__(self, state: AppState, generator: Generator,
                 video_player: VideoPlayer, fixture_sampler: FixtureSampler,
                 artnet_sender: ArtNetSender, bpm_analyzer: BPMAnalyzer,
                 preset_manager: PresetManager,
                 canvas_size: tuple[int, int]):
        self._state = state
        self._gen = generator
        self._video = video_player
        self._sampler = fixture_sampler
        self._artnet = artnet_sender
        self._bpm = bpm_analyzer
        self._presets = preset_manager
        self._H, self._W = canvas_size
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._clip_elapsed = 0.0
        self._preview_jpeg: bytes | None = None
        self._preview_lock = threading.Lock()
        self._preview_counter = 0
        self._thumb_jpegs: dict[int, bytes] = {}
        self._thumb_lock = threading.Lock()
        self._thumb_bufs: dict[int, dict] = {}
        self._thumb_counter = 0

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def get_preview_jpeg(self) -> bytes | None:
        with self._preview_lock:
            return self._preview_jpeg

    def get_thumbnail_jpeg(self, idx: int) -> bytes | None:
        with self._thumb_lock:
            return self._thumb_jpegs.get(idx)

    def _render_thumbnail(self, idx: int, faders: list[float], t: float, beat: float) -> None:
        import cv2
        buf = self._thumb_bufs.setdefault(idx, {})
        frame = self._gen.render_index(idx, THUMB_H, THUMB_W, faders, t, beat, buf)
        rgb = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        _, jpeg = cv2.imencode('.jpg', rgb, [cv2.IMWRITE_JPEG_QUALITY, 70])
        with self._thumb_lock:
            self._thumb_jpegs[idx] = jpeg.tobytes()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        target_dt = 1.0 / FPS
        t = 0.0
        last = time.monotonic()

        while not self._stop_event.is_set():
            now = time.monotonic()
            dt = now - last
            last = now

            beat = 1.0 if self._state.consume_beat() else 0.0
            self._presets.tick(dt)

            snap = self._state.snapshot()
            faders = snap['faders']
            H, W = self._H, self._W

            gen_frame = self._gen.render(H, W, faders, t, beat)

            if snap['active_clip'] is not None:
                self._clip_elapsed += dt
                vid_frame = self._video.get_frame(H, W, self._clip_elapsed)
            else:
                self._clip_elapsed = 0.0
                vid_frame = None

            frame = blend(gen_frame, vid_frame, snap['blend'])

            if snap['strobe_active']:
                frame = apply_strobe(frame, t, snap['bpm'],
                                     snap['strobe_rate_index'], snap['strobe_depth'],
                                     snap['strobe_duty'])

            frame = apply_master(frame, snap['master'])

            universe_data = self._sampler.sample(frame)
            for universe, dmx_bytes in universe_data.items():
                self._artnet.send(universe, dmx_bytes)

            self._preview_counter += 1
            if self._preview_counter % 3 == 0:  # ~10fps preview
                import cv2
                small = cv2.resize(frame, (400, 400 * H // W),
                                   interpolation=cv2.INTER_NEAREST)
                rgb = cv2.cvtColor(small, cv2.COLOR_RGB2BGR)
                _, buf = cv2.imencode('.jpg', rgb, [cv2.IMWRITE_JPEG_QUALITY, 75])
                with self._preview_lock:
                    self._preview_jpeg = buf.tobytes()

            n_algos = self._gen.algo_count()
            cycle_frames = int(THUMB_CYCLE_SECONDS * FPS)
            slot_size = max(1, cycle_frames // n_algos)
            if self._thumb_counter % slot_size == 0:
                algo_idx = (self._thumb_counter // slot_size) % n_algos
                self._render_thumbnail(algo_idx, faders, t, beat)
            self._thumb_counter += 1

            t += dt
            elapsed = time.monotonic() - now
            sleep = target_dt - elapsed
            if sleep > 0:
                time.sleep(sleep)
