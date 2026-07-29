import json
from state import AppState
from preset_manager import PresetManager

def test_save_and_recall(tmp_path):
    state = AppState()
    pm = PresetManager(str(tmp_path / 'presets.json'), state)
    state.update(faders=[0.8]*12)
    pm.save(0)
    state.update(faders=[0.0]*12)
    pm.recall(0)
    pm.tick(10.0)
    assert abs(state.faders[0] - 0.8) < 0.01

def test_recall_empty_slot_is_noop(tmp_path):
    state = AppState()
    pm = PresetManager(str(tmp_path / 'presets.json'), state)
    state.update(faders=[0.3]*12)
    pm.recall(5)
    pm.tick(10.0)
    assert abs(state.faders[0] - 0.3) < 0.01

def test_preset_persists_to_disk(tmp_path):
    state = AppState()
    path = str(tmp_path / 'presets.json')
    pm = PresetManager(path, state)
    state.update(faders=[0.9]*12)
    pm.save(2)
    pm2 = PresetManager(path, AppState())
    pm2.recall(2)
    pm2.tick(10.0)
    assert abs(pm2._state.faders[0] - 0.9) < 0.01

def test_corrupt_presets_file_does_not_crash(tmp_path):
    path = tmp_path / 'presets.json'
    path.write_text('{"presets": [truncated')
    state = AppState()
    pm = PresetManager(str(path), state)  # must not raise
    assert pm._presets == [None] * 24

def test_interpolation_advances_smoothly(tmp_path):
    state = AppState()
    pm = PresetManager(str(tmp_path / 'p.json'), state)
    pm._transition_s = 1.0
    state.update(faders=[0.0]*12)
    pm.save(0)
    state.update(faders=[1.0]*12)
    pm.recall(0)
    pm.tick(0.5)
    assert 0.3 < state.faders[0] < 0.7
