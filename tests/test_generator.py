import numpy as np
from generator import Generator, _ALGOS, _algo_fire

def test_render_returns_correct_shape():
    g = Generator()
    frame = g.render(100, 200, [0.5]*12, 0.0, 0.0)
    assert frame.shape == (100, 200, 3)
    assert frame.dtype == np.uint8

def test_render_all_algorithms():
    g = Generator()
    for algo_idx in range(len(_ALGOS)):
        faders = [0.5]*12
        faders[0] = algo_idx / len(_ALGOS)
        frame = g.render(20, 40, faders, 1.0, 0.0)
        assert frame.shape == (20, 40, 3)

def test_beat_changes_output():
    g = Generator()
    faders = [0.4] + [0.5]*11  # beat_react fader = 0.4
    frame_no_beat = g.render(20, 40, faders, 0.0, 0.0)
    frame_beat = g.render(20, 40, faders, 0.0, 1.0)
    assert not np.array_equal(frame_no_beat, frame_beat)

def test_time_changes_output():
    g = Generator()
    f1 = g.render(20, 40, [0.5]*12, 0.0, 0.0)
    f2 = g.render(20, 40, [0.5]*12, 1.0, 0.0)
    assert not np.array_equal(f1, f2)

def test_symmetry_handles_odd_dimensions():
    # regression: mirroring crashed with a broadcast error when W or H was odd
    g = Generator()
    faders = [0.5]*12
    faders[9] = 0.9  # symmetry fader -> both horizontal and vertical mirror
    frame = g.render(101, 201, faders, 0.0, 0.0)
    assert frame.shape == (101, 201, 3)

def test_algo_count_matches_algos_list():
    g = Generator()
    assert g.algo_count() == len(_ALGOS)

def test_algo_count_is_sixteen_after_expansion():
    assert len(_ALGOS) == 16

def test_render_index_returns_correct_shape():
    g = Generator()
    frame = g.render_index(0, 20, 40, [0.5]*12, 0.0, 0.0, {})
    assert frame.shape == (20, 40, 3)
    assert frame.dtype == np.uint8

def test_render_index_matches_render_for_same_algo():
    g = Generator()
    fire_idx = _ALGOS.index(_algo_fire)
    faders = [fire_idx / len(_ALGOS) + 0.01] + [0.5]*11
    np.random.seed(42)
    via_render = g.render(20, 40, faders, 1.0, 0.0)
    g2 = Generator()
    np.random.seed(42)
    via_index = g2.render_index(fire_idx, 20, 40, faders, 1.0, 0.0, g2._buf)
    assert np.array_equal(via_render, via_index)

def test_render_index_uses_isolated_buf():
    g = Generator()
    fire_idx = _ALGOS.index(_algo_fire)
    buf_a, buf_b = {}, {}
    g.render_index(fire_idx, 10, 10, [0.5]*12, 0.0, 0.0, buf_a)
    g.render_index(fire_idx, 20, 20, [0.5]*12, 0.0, 0.0, buf_b)
    assert buf_a['fire'].shape == (10, 10)
    assert buf_b['fire'].shape == (20, 20)
