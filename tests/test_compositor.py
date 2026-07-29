import numpy as np
from compositor import blend, apply_strobe, apply_master

def _frame(r, g, b, H=4, W=8):
    f = np.zeros((H, W, 3), dtype=np.uint8)
    f[:] = [r, g, b]
    return f

def test_blend_ratio_0_returns_generator():
    gen = _frame(255, 0, 0)
    vid = _frame(0, 255, 0)
    result = blend(gen, vid, 0.0)
    assert np.all(result[:, :, 0] == 255)
    assert np.all(result[:, :, 1] == 0)

def test_blend_ratio_1_returns_video():
    gen = _frame(255, 0, 0)
    vid = _frame(0, 255, 0)
    result = blend(gen, vid, 1.0)
    assert np.all(result[:, :, 0] == 0)
    assert np.all(result[:, :, 1] == 255)

def test_blend_no_video_ignores_ratio():
    gen = _frame(100, 100, 100)
    result = blend(gen, None, 1.0)
    assert np.all(result == gen)

def test_blend_midpoint():
    gen = _frame(200, 0, 0)
    vid = _frame(0, 200, 0)
    result = blend(gen, vid, 0.5)
    assert 90 < result[0, 0, 0] < 110
    assert 90 < result[0, 0, 1] < 110

def test_strobe_on_phase_is_unchanged():
    frame = _frame(200, 100, 50)
    result = apply_strobe(frame, 0.0, 120.0, 2, 1.0)
    assert np.all(result == frame)

def test_strobe_off_phase_darkens():
    frame = _frame(200, 100, 50)
    bpm = 120.0
    period = (60.0 / bpm) * (4.0 / 4)  # 1/4 note = 0.5s
    t_off = period * 0.75  # 75% into cycle = off phase
    result = apply_strobe(frame, t_off, bpm, 2, 1.0)
    assert result[0, 0, 0] < frame[0, 0, 0]

def test_strobe_depth_0_never_blacks_out():
    frame = _frame(200, 100, 50)
    bpm = 120.0
    period = (60.0 / bpm) * (4.0 / 4)
    t_off = period * 0.75
    result = apply_strobe(frame, t_off, bpm, 2, 0.0)
    assert np.allclose(result.astype(float), frame.astype(float), atol=2)

def test_strobe_out_of_range_rate_index_does_not_crash():
    frame = _frame(200, 100, 50)
    # index beyond STROBE_DIVISIONS (e.g. from an unvalidated WS message)
    result = apply_strobe(frame, 0.0, 120.0, 99, 1.0)
    assert result.shape == frame.shape
    result = apply_strobe(frame, 0.0, 120.0, -3, 1.0)
    assert result.shape == frame.shape

def test_apply_master_scales_brightness():
    frame = _frame(200, 100, 50)
    result = apply_master(frame, 0.5)
    assert abs(int(result[0, 0, 0]) - 100) <= 1
