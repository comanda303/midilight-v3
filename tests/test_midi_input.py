from state import AppState
from bpm_analyzer import BPMAnalyzer
from midi_input import MidiDispatcher

class FakeVideoPlayer:
    def __init__(self):
        self.triggered = []
        self.stopped = []

    def trigger(self, slot, brightness=1.0):
        self.triggered.append((slot, brightness))

    def stop(self, slot):
        self.stopped.append(slot)

def _make():
    state = AppState()
    bpm = BPMAnalyzer()
    video = FakeVideoPlayer()
    d = MidiDispatcher(state, bpm, video)
    return state, bpm, d, video

def test_cc_master_brightness():
    state, _, d, _ = _make()
    state.assignments = {'master': {'type': 'cc', 'number': 0, 'channel': 1}}
    d.on_message(([0xB0, 0, 127], 0.0))
    assert abs(state.master - 1.0) < 0.01

def test_cc_fader():
    state, _, d, _ = _make()
    state.assignments = {'fader_1': {'type': 'cc', 'number': 24, 'channel': 1}}
    d.on_message(([0xB0, 24, 64], 0.0))
    assert abs(state.faders[0] - 64/127) < 0.01

def test_note_on_triggers_clip():
    state, _, d, video = _make()
    state.assignments = {}
    d.on_message(([0x90, 5, 100], 0.0))
    assert state.active_clip == 5
    assert video.triggered == [(5, 100/127.0)]

def test_note_on_velocity_scales_brightness_can_be_disabled():
    state = AppState()
    bpm = BPMAnalyzer()
    video = FakeVideoPlayer()
    d = MidiDispatcher(state, bpm, video, velocity_scales_brightness=False)
    d.on_message(([0x90, 5, 40], 0.0))
    assert video.triggered == [(5, 1.0)]

def test_note_off_stops_clip():
    state, _, d, video = _make()
    state.active_clip = 5
    d.on_message(([0x80, 5, 0], 0.0))
    assert state.active_clip is None
    assert video.stopped == [5]

def test_note_on_without_video_player_does_not_crash():
    state = AppState()
    bpm = BPMAnalyzer()
    d = MidiDispatcher(state, bpm)
    d.on_message(([0x90, 5, 100], 0.0))
    assert state.active_clip == 5

def test_preset_recall():
    state, _, d, _ = _make()
    d.on_message(([0x90, 64, 100], 0.0))
    assert state.active_preset == 0

def test_strobe_toggle_on():
    state, _, d, _ = _make()
    state.assignments = {'strobe_toggle': {'type': 'note', 'number': 88, 'channel': 1}}
    d.on_message(([0x90, 88, 100], 0.0))
    assert state.strobe_active is True

def test_strobe_toggle_off():
    state, _, d, _ = _make()
    state.strobe_active = True
    state.assignments = {'strobe_toggle': {'type': 'note', 'number': 88, 'channel': 1}}
    d.on_message(([0x80, 88, 0], 0.0))
    assert state.strobe_active is False

def test_midi_clock_pulse_forwarded():
    state, bpm, d, _ = _make()
    d.on_message(([0xF8], 0.0))
    assert bpm.clock_active is True

def test_wrong_channel_ignored():
    state, _, d, _ = _make()
    state.assignments = {'master': {'type': 'cc', 'number': 0, 'channel': 1}}
    d.on_message(([0xB1, 0, 127], 0.0))  # channel 2 — should be ignored
    assert state.master == 1.0  # unchanged from default

def test_note_assignment_wrong_channel_ignored():
    state, _, d, _ = _make()
    state.assignments = {'strobe_toggle': {'type': 'note', 'number': 88, 'channel': 1}}
    d.on_message(([0x91, 88, 100], 0.0))  # channel 2 note-on — should be ignored
    assert state.strobe_active is False

def test_learn_cc_uses_locked_assignment_setter():
    state, _, d, _ = _make()
    state.learn_target = 'blend'
    d.on_message(([0xB0, 7, 64], 0.0))
    assert state.assignments['blend'] == {'type': 'cc', 'number': 7, 'channel': 1}
    assert state.learn_target is None

def test_learn_note_uses_locked_assignment_setter():
    state, _, d, _ = _make()
    state.learn_target = 'strobe_toggle'
    d.on_message(([0x90, 99, 100], 0.0))
    assert state.assignments['strobe_toggle'] == {'type': 'note', 'number': 99, 'channel': 1}
    assert state.learn_target is None
