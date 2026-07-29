import time, threading
import numpy as np
from unittest.mock import MagicMock, patch
from state import AppState
from bpm_analyzer import BPMAnalyzer
from generator import Generator
from render_loop import RenderLoop

def _make_loop(canvas=(100, 200)):
    state = AppState()
    bpm = BPMAnalyzer()
    gen = Generator()
    video = MagicMock()
    video.get_frame.return_value = None
    sampler = MagicMock()
    sampler.sample.return_value = {0: bytes(512)}
    artnet = MagicMock()
    preset_mgr = MagicMock()
    loop = RenderLoop(state, gen, video, sampler, artnet, bpm, preset_mgr, canvas)
    return loop, state, artnet, sampler

def test_start_and_stop():
    loop, _, _, _ = _make_loop()
    loop.start()
    time.sleep(0.1)
    loop.stop()

def test_artnet_called_after_start():
    loop, _, artnet, _ = _make_loop()
    loop.start()
    time.sleep(0.1)
    loop.stop()
    assert artnet.send.call_count > 0

def test_sampler_called_with_correct_canvas_shape():
    loop, state, _, sampler = _make_loop(canvas=(50, 80))
    loop.start()
    time.sleep(0.1)
    loop.stop()
    args = sampler.sample.call_args[0][0]
    assert args.shape == (50, 80, 3)

def test_beat_flag_consumed_each_frame():
    loop, state, _, _ = _make_loop()
    state.update(beat=True)
    loop.start()
    time.sleep(0.05)
    loop.stop()
    assert state.beat is False

def test_thumbnail_jpeg_populates_quickly():
    loop, _, _, _ = _make_loop()
    loop.start()
    time.sleep(0.2)
    loop.stop()
    assert loop.get_thumbnail_jpeg(0) is not None

def test_thumbnail_jpeg_missing_index_returns_none():
    loop, _, _, _ = _make_loop()
    assert loop.get_thumbnail_jpeg(999) is None
