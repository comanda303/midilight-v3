import numpy as np
from fixture_sampler import FixtureSampler

def _solid_canvas(H, W, r, g, b):
    c = np.zeros((H, W, 3), dtype=np.uint8)
    c[:, :] = [r, g, b]
    return c

def test_horizontal_strip_reads_correct_pixels():
    canvas = _solid_canvas(100, 200, 255, 0, 0)
    fixtures = [{'name': 'a', 'x': 0, 'y': 0, 'orientation': 'H',
                 'length': 4, 'universe': 0, 'start_channel': 0}]
    sampler = FixtureSampler(fixtures)
    result = sampler.sample(canvas)
    assert 0 in result
    dmx = result[0]
    assert dmx[0:3] == bytes([255, 0, 0])
    assert dmx[3:6] == bytes([255, 0, 0])

def test_vertical_strip_reads_correct_pixels():
    canvas = _solid_canvas(100, 200, 0, 255, 0)
    fixtures = [{'name': 'a', 'x': 10, 'y': 5, 'orientation': 'V',
                 'length': 3, 'universe': 0, 'start_channel': 0}]
    sampler = FixtureSampler(fixtures)
    result = sampler.sample(canvas)
    dmx = result[0]
    assert dmx[0:3] == bytes([0, 255, 0])
    assert dmx[3:6] == bytes([0, 255, 0])

def test_start_channel_offset():
    canvas = _solid_canvas(100, 200, 10, 20, 30)
    fixtures = [{'name': 'a', 'x': 0, 'y': 0, 'orientation': 'H',
                 'length': 1, 'universe': 0, 'start_channel': 6}]
    sampler = FixtureSampler(fixtures)
    result = sampler.sample(canvas)
    dmx = result[0]
    assert dmx[6:9] == bytes([10, 20, 30])
    assert dmx[0:3] == bytes([0, 0, 0])

def test_multiple_universes():
    canvas = _solid_canvas(100, 200, 1, 2, 3)
    fixtures = [
        {'name': 'a', 'x': 0, 'y': 0, 'orientation': 'H', 'length': 1, 'universe': 0, 'start_channel': 0},
        {'name': 'b', 'x': 0, 'y': 1, 'orientation': 'H', 'length': 1, 'universe': 1, 'start_channel': 0},
    ]
    sampler = FixtureSampler(fixtures)
    result = sampler.sample(canvas)
    assert 0 in result and 1 in result

def test_fixture_outside_canvas_is_skipped():
    canvas = _solid_canvas(100, 200, 1, 2, 3)
    fixtures = [
        {'name': 'off_y', 'x': 0, 'y': 100, 'orientation': 'H', 'length': 4, 'universe': 0, 'start_channel': 0},
        {'name': 'off_x', 'x': 200, 'y': 0, 'orientation': 'V', 'length': 4, 'universe': 0, 'start_channel': 0},
        {'name': 'neg', 'x': -1, 'y': 0, 'orientation': 'H', 'length': 4, 'universe': 0, 'start_channel': 0},
        {'name': 'ok', 'x': 0, 'y': 0, 'orientation': 'H', 'length': 1, 'universe': 1, 'start_channel': 0},
    ]
    sampler = FixtureSampler(fixtures)
    result = sampler.sample(canvas)  # must not raise
    assert result[1][0:3] == bytes([1, 2, 3])

def _gradient_canvas_x(H, W):
    # color at column x is [x, 0, 0] -- lets tests assert pixel order along x
    c = np.zeros((H, W, 3), dtype=np.uint8)
    for x in range(W):
        c[:, x] = [x, 0, 0]
    return c

def _gradient_canvas_y(H, W):
    # color at row y is [0, y, 0] -- lets tests assert pixel order along y
    c = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        c[y, :] = [0, y, 0]
    return c

def test_horizontal_reads_pixels_left_to_right():
    canvas = _gradient_canvas_x(10, 20)
    fixtures = [{'name': 'a', 'x': 2, 'y': 0, 'orientation': 'H',
                 'length': 3, 'universe': 0, 'start_channel': 0}]
    result = FixtureSampler(fixtures).sample(canvas)
    dmx = result[0]
    assert dmx[0:3] == bytes([2, 0, 0])
    assert dmx[3:6] == bytes([3, 0, 0])
    assert dmx[6:9] == bytes([4, 0, 0])

def test_horizontal_180_reads_pixels_right_to_left():
    canvas = _gradient_canvas_x(10, 20)
    fixtures = [{'name': 'a', 'x': 2, 'y': 0, 'orientation': 'H180',
                 'length': 3, 'universe': 0, 'start_channel': 0}]
    result = FixtureSampler(fixtures).sample(canvas)
    dmx = result[0]
    assert dmx[0:3] == bytes([4, 0, 0])
    assert dmx[3:6] == bytes([3, 0, 0])
    assert dmx[6:9] == bytes([2, 0, 0])

def test_vertical_reads_pixels_bottom_to_top():
    canvas = _gradient_canvas_y(10, 20)
    fixtures = [{'name': 'a', 'x': 0, 'y': 2, 'orientation': 'V',
                 'length': 3, 'universe': 0, 'start_channel': 0}]
    result = FixtureSampler(fixtures).sample(canvas)
    dmx = result[0]
    assert dmx[0:3] == bytes([0, 4, 0])
    assert dmx[3:6] == bytes([0, 3, 0])
    assert dmx[6:9] == bytes([0, 2, 0])

def test_vertical_180_reads_pixels_top_to_bottom():
    canvas = _gradient_canvas_y(10, 20)
    fixtures = [{'name': 'a', 'x': 0, 'y': 2, 'orientation': 'V180',
                 'length': 3, 'universe': 0, 'start_channel': 0}]
    result = FixtureSampler(fixtures).sample(canvas)
    dmx = result[0]
    assert dmx[0:3] == bytes([0, 2, 0])
    assert dmx[3:6] == bytes([0, 3, 0])
    assert dmx[6:9] == bytes([0, 4, 0])

def test_output_is_512_bytes():
    canvas = _solid_canvas(100, 200, 0, 0, 0)
    fixtures = [{'name': 'a', 'x': 0, 'y': 0, 'orientation': 'H',
                 'length': 1, 'universe': 0, 'start_channel': 0}]
    sampler = FixtureSampler(fixtures)
    result = sampler.sample(canvas)
    assert len(result[0]) == 512
