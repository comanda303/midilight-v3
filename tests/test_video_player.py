import os, cv2, numpy as np, tempfile, pytest
from video_player import VideoPlayer

@pytest.fixture
def clips_dir(tmp_path):
    path = str(tmp_path / '00_test.avi')
    out = cv2.VideoWriter(path, 0, 24, (4, 4))  # 0 = uncompressed, always available
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    frame[:, :] = [0, 0, 255]  # red in BGR
    out.write(frame)
    out.write(frame)
    out.release()
    return str(tmp_path)

def test_scan_clips_finds_slot_0(clips_dir):
    vp = VideoPlayer(clips_dir)
    clips = vp.scan_clips()
    assert clips[0] is not None
    assert clips[1] is None

def test_get_frame_before_trigger_returns_none(clips_dir):
    vp = VideoPlayer(clips_dir)
    assert vp.get_frame(10, 20, 0.0) is None

def test_get_frame_after_trigger_returns_array(clips_dir):
    vp = VideoPlayer(clips_dir)
    vp.trigger(0)
    frame = vp.get_frame(10, 20, 0.0)
    assert frame is not None
    assert frame.shape == (10, 20, 3)
    assert frame.dtype == np.uint8

def test_stop_returns_none(clips_dir):
    vp = VideoPlayer(clips_dir)
    vp.trigger(0)
    vp.stop(0)
    assert vp.get_frame(10, 20, 0.0) is None

def test_trigger_empty_slot_is_noop(clips_dir):
    vp = VideoPlayer(clips_dir)
    vp.trigger(1)  # slot 1 is empty
    assert vp.get_frame(10, 20, 0.0) is None
