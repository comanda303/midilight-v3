# MIDI ArtNet Lightshow Controller — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standalone Python app that receives MIDI from Ableton Live and drives an ArtNet LED matrix with a browser-based control surface.

**Architecture:** A 30fps render loop blends a real-time generator and a video player, applies strobe/gate, samples fixture positions from the output canvas, and sends ArtNet UDP packets. A FastAPI WebSocket server serves the browser UI and syncs state bidirectionally. MIDI input runs in a separate thread and writes to a shared AppState.

**Tech Stack:** Python 3.12, numpy, opencv-python, python-rtmidi, FastAPI, uvicorn, PyYAML, raw UDP sockets.

## Global Constraints

- Python 3.12+; type hints on all public functions
- numpy arrays for all pixel buffers: shape `(H, W, 3)`, dtype `uint8`
- ArtNet target: Art-DMX (OpCode 0x5000), 512 bytes per universe
- Virtual MIDI port name: `"LightShow"` (configurable in config.yaml)
- Default MIDI channel: 1
- Render loop: 30 fps (~33 ms per frame)
- All file paths relative to project root unless noted
- Tests use pytest; run with `pytest tests/ -v`

---

## File Map

```
midi-lightshow/
├── main.py
├── state.py
├── config.py
├── midi_input.py
├── bpm_analyzer.py
├── generator.py
├── video_player.py
├── compositor.py
├── artnet_output.py
├── fixture_sampler.py
├── preset_manager.py
├── render_loop.py
├── web_server.py
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── clips/            (drop video files here)
├── fixtures.json
├── config.yaml
├── presets.json
├── requirements.txt
└── tests/
    ├── test_state.py
    ├── test_bpm_analyzer.py
    ├── test_config.py
    ├── test_artnet_output.py
    ├── test_fixture_sampler.py
    ├── test_generator.py
    ├── test_video_player.py
    ├── test_compositor.py
    └── test_preset_manager.py
```

---

### Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `clips/.gitkeep`
- Create: `fixtures.json`
- Create: `config.yaml`

**Interfaces:**
- Produces: installable environment, default config files, runnable `pytest`

- [ ] **Step 1: Create requirements.txt**

```
numpy>=2.0
opencv-python>=4.9
python-rtmidi>=1.5
fastapi>=0.100
uvicorn[standard]>=0.23
PyYAML>=6.0
websockets>=12.0
```

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 3: Create pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 4: Create clips/.gitkeep**

```bash
mkdir -p clips && touch clips/.gitkeep
```

- [ ] **Step 5: Create default fixtures.json**

```json
{
  "canvas": { "width": 200, "height": 100 },
  "fixtures": []
}
```

- [ ] **Step 6: Create default config.yaml**

```yaml
midi:
  port_name: "LightShow"
  channel: 1
  assignments:
    master:       {type: cc,   number: 0,  channel: 1}
    blend:        {type: cc,   number: 1,  channel: 1}
    strobe_rate:  {type: cc,   number: 2,  channel: 1}
    strobe_depth: {type: cc,   number: 3,  channel: 1}
    fader_1:      {type: cc,   number: 24, channel: 1}
    fader_2:      {type: cc,   number: 25, channel: 1}
    fader_3:      {type: cc,   number: 26, channel: 1}
    fader_4:      {type: cc,   number: 27, channel: 1}
    fader_5:      {type: cc,   number: 28, channel: 1}
    fader_6:      {type: cc,   number: 29, channel: 1}
    fader_7:      {type: cc,   number: 30, channel: 1}
    fader_8:      {type: cc,   number: 31, channel: 1}
    fader_9:      {type: cc,   number: 32, channel: 1}
    fader_10:     {type: cc,   number: 33, channel: 1}
    fader_11:     {type: cc,   number: 34, channel: 1}
    fader_12:     {type: cc,   number: 35, channel: 1}
    strobe_toggle: {type: note, number: 88, channel: 1}
artnet:
  ip: "10.0.0.23"
  port: 6454
app:
  preset_transition_ms: 200
  clip_crossfade_ms: 0
  velocity_scales_brightness: true
```

- [ ] **Step 7: Create tests/ directory and empty __init__.py**

```bash
mkdir -p tests && touch tests/__init__.py
```

- [ ] **Step 8: Verify pytest runs (no tests yet)**

```bash
pytest tests/ -v
```

Expected: `no tests ran`

- [ ] **Step 9: Commit**

```bash
git add requirements.txt pytest.ini clips/.gitkeep fixtures.json config.yaml tests/
git commit -m "feat: project scaffold"
```

---

### Task 2: AppState

**Files:**
- Create: `state.py`
- Create: `tests/test_state.py`

**Interfaces:**
- Produces:
  - `AppState` class with `update(**kwargs)`, `snapshot() -> dict`, `consume_beat() -> bool`
  - `FADER_NAMES: list[str]` (12 names, index matches fader position)

- [ ] **Step 1: Write failing test**

```python
# tests/test_state.py
import threading
from state import AppState, FADER_NAMES

def test_default_faders():
    s = AppState()
    assert len(s.faders) == 12
    assert all(v == 0.5 for v in s.faders)

def test_update_fader():
    s = AppState()
    s.update(faders=[0.0] * 12)
    assert s.faders[0] == 0.0

def test_snapshot_is_copy():
    s = AppState()
    snap = s.snapshot()
    snap['faders'][0] = 99.0
    assert s.faders[0] == 0.5

def test_consume_beat():
    s = AppState()
    assert s.consume_beat() is False
    s.update(beat=True)
    assert s.consume_beat() is True
    assert s.consume_beat() is False  # consumed

def test_thread_safe_update():
    s = AppState()
    errors = []
    def writer():
        for _ in range(1000):
            try:
                s.update(master=0.9)
            except Exception as e:
                errors.append(e)
    threads = [threading.Thread(target=writer) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert errors == []

def test_fader_names_length():
    assert len(FADER_NAMES) == 12
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'state'`

- [ ] **Step 3: Implement state.py**

```python
# state.py
from __future__ import annotations
import threading
from dataclasses import dataclass, field
from typing import Optional

FADER_NAMES = [
    'algorithm', 'beat_react', 'rhythm_density', 'speed',
    'hue', 'saturation', 'color_spread', 'scale',
    'direction', 'symmetry', 'contrast', 'blur_glow',
]

@dataclass
class AppState:
    faders: list[float] = field(default_factory=lambda: [0.5] * 12)
    master: float = 1.0
    blend: float = 0.0        # 0.0 = generator only, 1.0 = video only
    strobe_rate_index: int = 2  # index into STROBE_DIVISIONS
    strobe_depth: float = 1.0
    strobe_active: bool = False
    active_clip: Optional[int] = None
    active_preset: Optional[int] = None
    bpm: float = 120.0
    midi_clock_active: bool = False
    beat: bool = False
    assignments: dict = field(default_factory=dict)
    learn_target: Optional[str] = None

    def __post_init__(self):
        self._lock = threading.Lock()

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                'faders': self.faders[:],
                'master': self.master,
                'blend': self.blend,
                'strobe_rate_index': self.strobe_rate_index,
                'strobe_depth': self.strobe_depth,
                'strobe_active': self.strobe_active,
                'active_clip': self.active_clip,
                'active_preset': self.active_preset,
                'bpm': self.bpm,
                'midi_clock_active': self.midi_clock_active,
                'assignments': {k: dict(v) for k, v in self.assignments.items()},
                'learn_target': self.learn_target,
            }

    def consume_beat(self) -> bool:
        with self._lock:
            if self.beat:
                self.beat = False
                return True
            return False

STROBE_DIVISIONS = [1, 2, 4, 8, 16, 32]  # denominators: 1/1, 1/2, 1/4 ...
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_state.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add state.py tests/test_state.py
git commit -m "feat: AppState with thread-safe update/snapshot/consume_beat"
```

---

### Task 3: Config & Fixtures Loader

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `load_config(path: str) -> dict`
  - `save_config(config: dict, path: str) -> None`
  - `load_fixtures(path: str) -> dict`  — `{"canvas": {"width": int, "height": int}, "fixtures": list}`
  - `save_fixtures(data: dict, path: str) -> None`
  - `default_config() -> dict`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import json, os, tempfile
import pytest
from config import load_config, save_config, load_fixtures, save_fixtures, default_config

def test_default_config_has_required_keys():
    cfg = default_config()
    assert 'midi' in cfg
    assert 'artnet' in cfg
    assert 'app' in cfg
    assert cfg['midi']['channel'] == 1
    assert cfg['artnet']['port'] == 6454

def test_save_and_load_config(tmp_path):
    cfg = default_config()
    cfg['artnet']['ip'] = '1.2.3.4'
    path = str(tmp_path / 'config.yaml')
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded['artnet']['ip'] == '1.2.3.4'

def test_load_config_missing_file_returns_default(tmp_path):
    path = str(tmp_path / 'nonexistent.yaml')
    cfg = load_config(path)
    assert cfg['midi']['channel'] == 1

def test_save_and_load_fixtures(tmp_path):
    data = {
        'canvas': {'width': 300, 'height': 150},
        'fixtures': [{'name': 'strip_01', 'x': 0, 'y': 10,
                      'orientation': 'H', 'length': 40,
                      'universe': 0, 'start_channel': 0}]
    }
    path = str(tmp_path / 'fixtures.json')
    save_fixtures(data, path)
    loaded = load_fixtures(path)
    assert loaded['canvas']['width'] == 300
    assert loaded['fixtures'][0]['name'] == 'strip_01'

def test_load_fixtures_missing_file_returns_empty(tmp_path):
    path = str(tmp_path / 'nope.json')
    data = load_fixtures(path)
    assert data['fixtures'] == []
    assert 'canvas' in data
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 3: Implement config.py**

```python
# config.py
from __future__ import annotations
import json
import yaml

def default_config() -> dict:
    return {
        'midi': {
            'port_name': 'LightShow',
            'channel': 1,
            'assignments': {
                'master':        {'type': 'cc',   'number': 0,  'channel': 1},
                'blend':         {'type': 'cc',   'number': 1,  'channel': 1},
                'strobe_rate':   {'type': 'cc',   'number': 2,  'channel': 1},
                'strobe_depth':  {'type': 'cc',   'number': 3,  'channel': 1},
                **{f'fader_{i+1}': {'type': 'cc', 'number': 24 + i, 'channel': 1}
                   for i in range(12)},
                'strobe_toggle': {'type': 'note', 'number': 88, 'channel': 1},
            },
        },
        'artnet': {'ip': '10.0.0.23', 'port': 6454},
        'app': {
            'preset_transition_ms': 200,
            'clip_crossfade_ms': 0,
            'velocity_scales_brightness': True,
        },
    }

def load_config(path: str) -> dict:
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return default_config()

def save_config(config: dict, path: str) -> None:
    with open(path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

def load_fixtures(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {'canvas': {'width': 200, 'height': 100}, 'fixtures': []}

def save_fixtures(data: dict, path: str) -> None:
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config and fixtures loader"
```

---

### Task 4: BPM Analyzer

**Files:**
- Create: `bpm_analyzer.py`
- Create: `tests/test_bpm_analyzer.py`

**Interfaces:**
- Produces:
  - `BPMAnalyzer` with `on_clock_pulse() -> None`, `consume_beat() -> bool`, `bpm: float`, `clock_active: bool`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_bpm_analyzer.py
import time
from bpm_analyzer import BPMAnalyzer

def test_bpm_calculation():
    analyzer = BPMAnalyzer()
    # 120 BPM = 2 beats/sec = 48 pulses/sec → interval = 1/48 sec
    interval = 1.0 / 48.0
    t = 0.0
    for _ in range(50):
        analyzer.on_clock_pulse(t)
        t += interval
    assert 115 < analyzer.bpm < 125

def test_beat_fires_every_24_pulses():
    analyzer = BPMAnalyzer()
    beats = 0
    for i in range(72):  # 3 beats worth
        analyzer.on_clock_pulse(float(i) / 48.0)
        if analyzer.consume_beat():
            beats += 1
    assert beats == 3

def test_consume_beat_resets_flag():
    analyzer = BPMAnalyzer()
    for i in range(24):
        analyzer.on_clock_pulse(float(i) / 48.0)
    assert analyzer.consume_beat() is True
    assert analyzer.consume_beat() is False

def test_clock_active_after_pulses():
    analyzer = BPMAnalyzer()
    assert analyzer.clock_active is False
    analyzer.on_clock_pulse(0.0)
    assert analyzer.clock_active is True

def test_default_bpm():
    analyzer = BPMAnalyzer()
    assert analyzer.bpm == 120.0
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_bpm_analyzer.py -v
```

- [ ] **Step 3: Implement bpm_analyzer.py**

```python
# bpm_analyzer.py
from __future__ import annotations
import threading
from collections import deque

PULSES_PER_BEAT = 24

class BPMAnalyzer:
    def __init__(self, history: int = 24):
        self._lock = threading.Lock()
        self._pulse_times: deque[float] = deque(maxlen=history + 1)
        self._pulse_count = 0
        self._bpm = 120.0
        self._beat_pending = False
        self._got_pulse = False

    def on_clock_pulse(self, t: float | None = None) -> None:
        import time as _time
        if t is None:
            t = _time.monotonic()
        with self._lock:
            self._pulse_times.append(t)
            self._got_pulse = True
            self._pulse_count += 1

            if len(self._pulse_times) >= 2:
                intervals = [
                    self._pulse_times[i+1] - self._pulse_times[i]
                    for i in range(len(self._pulse_times) - 1)
                    if self._pulse_times[i+1] > self._pulse_times[i]
                ]
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    self._bpm = 60.0 / (avg_interval * PULSES_PER_BEAT)

            if self._pulse_count % PULSES_PER_BEAT == 0:
                self._beat_pending = True

    def consume_beat(self) -> bool:
        with self._lock:
            if self._beat_pending:
                self._beat_pending = False
                return True
            return False

    @property
    def bpm(self) -> float:
        with self._lock:
            return self._bpm

    @property
    def clock_active(self) -> bool:
        with self._lock:
            return self._got_pulse
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_bpm_analyzer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add bpm_analyzer.py tests/test_bpm_analyzer.py
git commit -m "feat: BPM analyzer from MIDI clock pulses"
```

---

### Task 5: MIDI Input

**Files:**
- Create: `midi_input.py`
- Create: `tests/test_midi_input.py`

**Interfaces:**
- Consumes: `AppState`, `BPMAnalyzer`
- Produces:
  - `MidiDispatcher(state, bpm_analyzer)` with `on_message(message: list[int], data=None) -> None`
  - `open_virtual_port(dispatcher, port_name: str)` — returns rtmidi handle (call in main.py)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_midi_input.py
from state import AppState
from bpm_analyzer import BPMAnalyzer
from midi_input import MidiDispatcher

def _make():
    state = AppState()
    bpm = BPMAnalyzer()
    d = MidiDispatcher(state, bpm)
    return state, bpm, d

def test_cc_master_brightness():
    state, _, d = _make()
    state.assignments = {'master': {'type': 'cc', 'number': 0, 'channel': 1}}
    d.on_message([0xB0, 0, 127])  # CC0 = 127
    assert abs(state.master - 1.0) < 0.01

def test_cc_fader():
    state, _, d = _make()
    state.assignments = {'fader_1': {'type': 'cc', 'number': 24, 'channel': 1}}
    d.on_message([0xB0, 24, 64])  # CC24 = 64 → ~0.504
    assert abs(state.faders[0] - 64/127) < 0.01

def test_note_on_triggers_clip():
    state, _, d = _make()
    state.assignments = {}
    d.on_message([0x90, 5, 100])  # note 5 on → clip 5
    assert state.active_clip == 5

def test_note_off_stops_clip():
    state, _, d = _make()
    state.active_clip = 5
    d.on_message([0x80, 5, 0])  # note 5 off
    assert state.active_clip is None

def test_preset_recall():
    state, _, d = _make()
    d.on_message([0x90, 64, 100])  # note 64 → preset 0
    assert state.active_preset == 0

def test_strobe_toggle_on():
    state, _, d = _make()
    state.assignments = {'strobe_toggle': {'type': 'note', 'number': 88, 'channel': 1}}
    d.on_message([0x90, 88, 100])
    assert state.strobe_active is True

def test_strobe_toggle_off():
    state, _, d = _make()
    state.strobe_active = True
    state.assignments = {'strobe_toggle': {'type': 'note', 'number': 88, 'channel': 1}}
    d.on_message([0x80, 88, 0])
    assert state.strobe_active is False

def test_midi_clock_pulse_forwarded():
    state, bpm, d = _make()
    d.on_message([0xF8])
    assert bpm.clock_active is True

def test_wrong_channel_ignored():
    state, _, d = _make()
    state.assignments = {'master': {'type': 'cc', 'number': 0, 'channel': 1}}
    d.on_message([0xB1, 0, 127])  # channel 2 — should be ignored
    assert state.master == 1.0  # unchanged from default
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_midi_input.py -v
```

- [ ] **Step 3: Implement midi_input.py**

```python
# midi_input.py
from __future__ import annotations
from state import AppState, STROBE_DIVISIONS
from bpm_analyzer import BPMAnalyzer

NOTE_CLIP_MIN, NOTE_CLIP_MAX = 0, 63
NOTE_PRESET_MIN, NOTE_PRESET_MAX = 64, 87
MIDI_CLOCK = 0xF8

class MidiDispatcher:
    def __init__(self, state: AppState, bpm_analyzer: BPMAnalyzer):
        self.state = state
        self.bpm = bpm_analyzer

    def on_message(self, message: list[int], data=None) -> None:
        if not message:
            return
        status = message[0]

        if status == MIDI_CLOCK:
            self.bpm.on_clock_pulse()
            self.state.update(bpm=self.bpm.bpm, midi_clock_active=True)
            return

        msg_type = status & 0xF0
        channel = (status & 0x0F) + 1
        cfg_channel = self.state.assignments.get('master', {}).get('channel', 1)

        if msg_type == 0xB0:  # CC
            if len(message) < 3:
                return
            cc_num, cc_val = message[1], message[2]
            self._handle_cc(cc_num, cc_val, channel)

        elif msg_type == 0x90 and len(message) >= 3 and message[2] > 0:  # note on
            note, vel = message[1], message[2]
            self._handle_note_on(note, vel, channel)

        elif msg_type == 0x80 or (msg_type == 0x90 and len(message) >= 3 and message[2] == 0):
            note = message[1]
            self._handle_note_off(note, channel)

    def _handle_cc(self, cc_num: int, cc_val: int, channel: int) -> None:
        val = cc_val / 127.0
        assignments = self.state.assignments

        for name, asgn in assignments.items():
            if asgn.get('type') != 'cc':
                continue
            if asgn.get('number') != cc_num:
                continue
            if asgn.get('channel', 1) != channel:
                continue

            if name == 'master':
                self.state.update(master=val)
            elif name == 'blend':
                self.state.update(blend=val)
            elif name == 'strobe_rate':
                idx = min(int(val * len(STROBE_DIVISIONS)), len(STROBE_DIVISIONS) - 1)
                self.state.update(strobe_rate_index=idx)
            elif name == 'strobe_depth':
                self.state.update(strobe_depth=val)
            elif name.startswith('fader_'):
                idx = int(name.split('_')[1]) - 1
                faders = self.state.faders[:]
                faders[idx] = val
                self.state.update(faders=faders)

        # Learn mode
        if self.state.learn_target:
            self.state.assignments[self.state.learn_target] = {
                'type': 'cc', 'number': cc_num, 'channel': channel}
            self.state.update(learn_target=None)

    def _handle_note_on(self, note: int, velocity: int, channel: int) -> None:
        brightness = (velocity / 127.0) if self.state.assignments.get(
            'master', {}).get('type') else 1.0

        if NOTE_CLIP_MIN <= note <= NOTE_CLIP_MAX:
            self.state.update(active_clip=note)
            return

        if NOTE_PRESET_MIN <= note <= NOTE_PRESET_MAX:
            preset_idx = note - NOTE_PRESET_MIN
            self.state.update(active_preset=preset_idx)
            return

        for name, asgn in self.state.assignments.items():
            if asgn.get('type') == 'note' and asgn.get('number') == note:
                if name == 'strobe_toggle':
                    self.state.update(strobe_active=True)

        if self.state.learn_target:
            self.state.assignments[self.state.learn_target] = {
                'type': 'note', 'number': note, 'channel': channel}
            self.state.update(learn_target=None)

    def _handle_note_off(self, note: int, channel: int) -> None:
        if NOTE_CLIP_MIN <= note <= NOTE_CLIP_MAX:
            if self.state.active_clip == note:
                self.state.update(active_clip=None)
            return

        for name, asgn in self.state.assignments.items():
            if asgn.get('type') == 'note' and asgn.get('number') == note:
                if name == 'strobe_toggle':
                    self.state.update(strobe_active=False)


def open_virtual_port(dispatcher: MidiDispatcher, port_name: str):
    import rtmidi
    midi_in = rtmidi.MidiIn()
    midi_in.open_virtual_port(port_name)
    midi_in.set_callback(dispatcher.on_message)
    midi_in.ignore_types(sysex=True, timing=False, active_sense=True)
    return midi_in
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_midi_input.py -v
```

- [ ] **Step 5: Commit**

```bash
git add midi_input.py tests/test_midi_input.py
git commit -m "feat: MIDI dispatcher handles CC, notes, clock, learn mode"
```

---

### Task 6: ArtNet Output

**Files:**
- Create: `artnet_output.py`
- Create: `tests/test_artnet_output.py`

**Interfaces:**
- Produces:
  - `build_artnet_packet(universe: int, data: bytes) -> bytes`
  - `ArtNetSender(ip: str, port: int = 6454)` with `send(universe: int, data: bytes) -> None`, `close() -> None`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_artnet_output.py
import struct
from artnet_output import build_artnet_packet, ArtNetSender

def test_packet_header():
    pkt = build_artnet_packet(0, bytes(512))
    assert pkt[:8] == b'Art-Net\x00'

def test_packet_opcode():
    pkt = build_artnet_packet(0, bytes(512))
    opcode = struct.unpack_from('<H', pkt, 8)[0]
    assert opcode == 0x5000

def test_packet_universe():
    pkt = build_artnet_packet(3, bytes(512))
    sub_uni = pkt[14]
    assert sub_uni == 3

def test_packet_length_field():
    data = bytes(100)
    pkt = build_artnet_packet(0, data)
    length = struct.unpack_from('>H', pkt, 16)[0]
    assert length == 100

def test_packet_data():
    data = bytes([0xAB] * 10)
    pkt = build_artnet_packet(0, data)
    assert pkt[18:28] == data

def test_packet_odd_length_padded():
    data = bytes(5)
    pkt = build_artnet_packet(0, data)
    assert len(pkt) == 18 + 6  # padded to even

def test_artnet_sender_instantiation():
    sender = ArtNetSender('127.0.0.1', 6454)
    sender.close()
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_artnet_output.py -v
```

- [ ] **Step 3: Implement artnet_output.py**

```python
# artnet_output.py
from __future__ import annotations
import socket
import struct

def build_artnet_packet(universe: int, data: bytes) -> bytes:
    if len(data) % 2 != 0:
        data = data + b'\x00'
    return (
        b'Art-Net\x00'
        + struct.pack('<H', 0x5000)              # OpDmx
        + struct.pack('>H', 14)                  # ProtVer
        + b'\x00'                                # Sequence (disabled)
        + b'\x00'                                # Physical
        + struct.pack('B', universe & 0xFF)      # SubUni
        + struct.pack('B', (universe >> 8) & 0x7F)  # Net
        + struct.pack('>H', len(data))           # Length
        + data
    )

class ArtNetSender:
    def __init__(self, ip: str, port: int = 6454):
        self._ip = ip
        self._port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, universe: int, data: bytes) -> None:
        pkt = build_artnet_packet(universe, data)
        self._sock.sendto(pkt, (self._ip, self._port))

    def close(self) -> None:
        self._sock.close()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_artnet_output.py -v
```

- [ ] **Step 5: Commit**

```bash
git add artnet_output.py tests/test_artnet_output.py
git commit -m "feat: ArtNet Art-DMX packet builder and UDP sender"
```

---

### Task 7: Fixture Sampler

**Files:**
- Create: `fixture_sampler.py`
- Create: `tests/test_fixture_sampler.py`

**Interfaces:**
- Consumes: `fixtures.json` format (list of fixture dicts)
- Produces:
  - `FixtureSampler(fixtures: list[dict])` with `sample(canvas: np.ndarray) -> dict[int, bytes]`
    - canvas: `(H, W, 3)` uint8
    - returns: `{universe: dmx_bytes}` where dmx_bytes is 512 bytes

- [ ] **Step 1: Write failing tests**

```python
# tests/test_fixture_sampler.py
import numpy as np
from fixture_sampler import FixtureSampler

def _solid_canvas(H, W, r, g, b):
    c = np.zeros((H, W, 3), dtype=np.uint8)
    c[:, :] = [r, g, b]
    return c

def test_horizontal_strip_reads_correct_pixels():
    canvas = _solid_canvas(100, 200, 255, 0, 0)  # all red
    fixtures = [{'name': 'a', 'x': 0, 'y': 0, 'orientation': 'H',
                 'length': 4, 'universe': 0, 'start_channel': 0}]
    sampler = FixtureSampler(fixtures)
    result = sampler.sample(canvas)
    assert 0 in result
    dmx = result[0]
    # 4 RGB pixels = 12 bytes, starting at ch 0
    assert dmx[0:3] == bytes([255, 0, 0])
    assert dmx[3:6] == bytes([255, 0, 0])

def test_vertical_strip_reads_correct_pixels():
    canvas = _solid_canvas(100, 200, 0, 255, 0)  # all green
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
    assert dmx[0:3] == bytes([0, 0, 0])  # before start channel

def test_multiple_universes():
    canvas = _solid_canvas(100, 200, 1, 2, 3)
    fixtures = [
        {'name': 'a', 'x': 0, 'y': 0, 'orientation': 'H', 'length': 1, 'universe': 0, 'start_channel': 0},
        {'name': 'b', 'x': 0, 'y': 1, 'orientation': 'H', 'length': 1, 'universe': 1, 'start_channel': 0},
    ]
    sampler = FixtureSampler(fixtures)
    result = sampler.sample(canvas)
    assert 0 in result and 1 in result

def test_output_is_512_bytes():
    canvas = _solid_canvas(100, 200, 0, 0, 0)
    fixtures = [{'name': 'a', 'x': 0, 'y': 0, 'orientation': 'H',
                 'length': 1, 'universe': 0, 'start_channel': 0}]
    sampler = FixtureSampler(fixtures)
    result = sampler.sample(canvas)
    assert len(result[0]) == 512
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_fixture_sampler.py -v
```

- [ ] **Step 3: Implement fixture_sampler.py**

```python
# fixture_sampler.py
from __future__ import annotations
import numpy as np

class FixtureSampler:
    def __init__(self, fixtures: list[dict]):
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

            if orientation == 'H':
                x_end = min(x + length, W)
                pixels = canvas[y, x:x_end]          # (length, 3)
            else:
                y_end = min(y + length, H)
                pixels = canvas[y:y_end, x]           # (length, 3)

            if universe not in universe_bufs:
                universe_bufs[universe] = bytearray(512)

            flat = pixels.flatten()
            end_ch = start_ch + len(flat)
            if end_ch <= 512:
                universe_bufs[universe][start_ch:end_ch] = flat

        return {u: bytes(buf) for u, buf in universe_bufs.items()}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_fixture_sampler.py -v
```

- [ ] **Step 5: Commit**

```bash
git add fixture_sampler.py tests/test_fixture_sampler.py
git commit -m "feat: fixture sampler reads canvas pixels to ArtNet universe buffers"
```

---

### Task 8: Generator

**Files:**
- Create: `generator.py`
- Create: `tests/test_generator.py`

**Interfaces:**
- Consumes: `AppState.faders`, `AppState.snapshot()`
- Produces:
  - `Generator()` with `render(H: int, W: int, faders: list[float], t: float, beat: float) -> np.ndarray`
    - `beat`: 0.0 normally, 1.0 on a beat frame
    - Returns `(H, W, 3)` uint8

- [ ] **Step 1: Write failing tests**

```python
# tests/test_generator.py
import numpy as np
from generator import Generator

def test_render_returns_correct_shape():
    g = Generator()
    frame = g.render(100, 200, [0.5]*12, 0.0, 0.0)
    assert frame.shape == (100, 200, 3)
    assert frame.dtype == np.uint8

def test_render_all_algorithms():
    g = Generator()
    for algo_idx in range(6):
        faders = [0.5]*12
        faders[0] = algo_idx / 5.0
        frame = g.render(20, 40, faders, 1.0, 0.0)
        assert frame.shape == (20, 40, 3)

def test_beat_changes_output():
    g = Generator()
    faders = [0.4] + [0.5]*11  # beat_react fader = 0.4
    frame_no_beat = g.render(20, 40, faders, 0.0, 0.0)
    frame_beat = g.render(20, 40, faders, 0.0, 1.0)
    # beat should change at least some pixels
    assert not np.array_equal(frame_no_beat, frame_beat)

def test_time_changes_output():
    g = Generator()
    f1 = g.render(20, 40, [0.5]*12, 0.0, 0.0)
    f2 = g.render(20, 40, [0.5]*12, 1.0, 0.0)
    assert not np.array_equal(f1, f2)
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_generator.py -v
```

- [ ] **Step 3: Implement generator.py**

```python
# generator.py
from __future__ import annotations
import numpy as np

def _hsv_to_rgb(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    """h, s, v: (H,W) float32 arrays 0-1. Returns (H,W,3) uint8."""
    h = h % 1.0
    i = (h * 6).astype(np.int32)
    f = h * 6 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i6 = i % 6
    r = np.select([i6==0,i6==1,i6==2,i6==3,i6==4,i6==5], [v,q,p,p,t,v])
    g = np.select([i6==0,i6==1,i6==2,i6==3,i6==4,i6==5], [t,v,v,q,p,p])
    b = np.select([i6==0,i6==1,i6==2,i6==3,i6==4,i6==5], [p,p,t,v,v,q])
    return (np.stack([r, g, b], axis=-1) * 255).clip(0, 255).astype(np.uint8)

def _apply_symmetry(frame: np.ndarray, sym: float) -> np.ndarray:
    H, W = frame.shape[:2]
    if sym < 0.33:
        return frame
    left = frame[:, :W//2].copy()
    frame[:, W//2:] = left[:, ::-1]
    if sym >= 0.66:
        top = frame[:H//2, :].copy()
        frame[H//2:, :] = top[::-1, :]
    return frame

def _apply_blur(frame: np.ndarray, amount: float) -> np.ndarray:
    if amount < 0.02:
        return frame
    import cv2
    k = max(1, int(amount * 10)) * 2 + 1
    return cv2.GaussianBlur(frame, (k, k), 0)

def _algo_plasma(H, W, p, t, beat):
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    Y /= H; X /= W
    spd = 0.3 + p['speed'] * 2.0
    scl = 2.0 + p['scale'] * 8.0
    v = (np.sin(X * scl * 2*np.pi + t * spd)
       + np.sin(Y * scl * 2*np.pi + t * spd * 0.7)
       + np.sin((X + Y) * scl * np.pi + t * spd * 1.2)
       + np.sin(np.sqrt(np.clip((X-0.5)**2+(Y-0.5)**2,0,None)) * scl * 2*np.pi))
    v = (v / 4.0 + 0.5)
    v = np.clip(v + beat * p['beat_react'] * 0.4, 0, 1)
    hue = np.clip(p['hue'] + (v - 0.5) * p['color_spread'], 0, 1)
    sat = np.full_like(v, p['saturation'])
    v_out = np.clip((v - 0.5) * (1 + p['contrast'] * 3) + 0.5, 0, 1)
    return _hsv_to_rgb(hue, sat, v_out)

def _algo_fire(H, W, p, t, beat, buf):
    if 'fire' not in buf or buf['fire'].shape != (H, W):
        buf['fire'] = np.zeros((H, W), dtype=np.float32)
    fb = buf['fire']
    density = 0.3 + p['rhythm_density'] * 0.7
    spd = 0.05 + p['speed'] * 0.3
    ignite = np.random.random(W) < density
    fb[-1] = np.where(ignite, 1.0, np.maximum(fb[-1] - 0.1, 0))
    fb[-1] = np.minimum(1.0, fb[-1] + beat * p['beat_react'] * 0.8)
    spread = (np.roll(fb, -1, axis=1) + np.roll(fb, 1, axis=1) + fb) / 3.0
    fb[:-1] = np.clip(fb[:-1] + (spread[1:] - fb[:-1]) * spd - 0.02, 0, 1)
    r = np.clip(fb * 3.0, 0, 1)
    g = np.clip(fb * 3.0 - 1.0, 0, 1)
    b = np.clip(fb * 3.0 - 2.0, 0, 1)
    rgb = (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)
    hue_shift = p['hue']
    if hue_shift > 0.01:
        rgb = np.roll(rgb, int(hue_shift * 2), axis=-1)
    return rgb

def _algo_noise(H, W, p, t, beat):
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    Y /= H; X /= W
    spd = 0.2 + p['speed'] * 1.5
    scl = 1.0 + p['scale'] * 5.0
    octaves = max(1, int(1 + p['rhythm_density'] * 4))
    angle = p['direction'] * 2 * np.pi
    dx, dy = np.cos(angle), np.sin(angle)
    v = np.zeros((H, W), dtype=np.float32)
    amp, freq = 1.0, scl
    for _ in range(octaves):
        v += amp * np.sin((X*dx + Y*dy) * freq * 2*np.pi + t*spd)
        v += amp * np.sin((X*dy - Y*dx) * freq * np.pi + t*spd*1.3)
        amp *= 0.5; freq *= 2.0
    v = np.clip((v + 2) / 4 + beat * p['beat_react'] * 0.3, 0, 1)
    hue = np.clip(p['hue'] + (v-0.5)*p['color_spread'], 0, 1)
    sat = np.full_like(v, p['saturation'])
    v_out = np.clip((v-0.5)*(1+p['contrast']*3)+0.5, 0, 1)
    return _hsv_to_rgb(hue, sat, v_out)

def _algo_bars(H, W, p, t, beat):
    spd = 0.5 + p['speed'] * 4.0
    density = max(1, int(1 + p['rhythm_density'] * 15))
    x_pos = np.linspace(0, np.pi * 2 * density, W, dtype=np.float32)
    y_pos = np.linspace(0, np.pi * 2 * density, H, dtype=np.float32)
    hbars = (np.sin(x_pos + t * spd) * 0.5 + 0.5).reshape(1, W).repeat(H, axis=0)
    vbars = (np.sin(y_pos + t * spd * 1.3) * 0.5 + 0.5).reshape(H, 1).repeat(W, axis=1)
    d = p['direction']
    v = hbars * (1-d) + vbars * d
    v = np.clip(v + beat * p['beat_react'] * 0.5, 0, 1)
    hue = np.full((H, W), p['hue'], dtype=np.float32)
    sat = np.full((H, W), p['saturation'], dtype=np.float32)
    v_out = np.clip((v-0.5)*(1+p['contrast']*3)+0.5, 0, 1)
    return _hsv_to_rgb(hue, sat, v_out.astype(np.float32))

def _algo_radial(H, W, p, t, beat):
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((X - W/2)/W)**2 + ((Y - H/2)/H)**2)
    spd = 0.5 + p['speed'] * 3.0
    density = 1 + p['rhythm_density'] * 8
    v = np.sin(r * density * 2*np.pi - t * spd) * 0.5 + 0.5
    v = np.clip(v + beat * p['beat_react'] * (1-r), 0, 1)
    hue = np.clip(p['hue'] + r * p['color_spread'], 0, 1).astype(np.float32)
    sat = np.full((H, W), p['saturation'], dtype=np.float32)
    v_out = np.clip((v-0.5)*(1+p['contrast']*3)+0.5, 0, 1).astype(np.float32)
    return _hsv_to_rgb(hue, sat, v_out)

def _algo_stars(H, W, p, t, beat, buf):
    N = 300
    if 'stars' not in buf:
        buf['stars'] = np.random.rand(N, 3).astype(np.float32)
    stars = buf['stars']
    speed = 0.002 + p['speed'] * 0.05
    stars[:, 2] -= speed + beat * p['beat_react'] * 0.08
    reset = stars[:, 2] <= 0
    if reset.any():
        stars[reset, :2] = np.random.rand(int(reset.sum()), 2)
        stars[reset, 2] = 1.0
    z = np.maximum(stars[:, 2], 0.001)
    sx = (((stars[:, 0] - 0.5) / z + 0.5) * W).astype(np.float32)
    sy = (((stars[:, 1] - 0.5) / z + 0.5) * H).astype(np.float32)
    bri = ((1.0 - z) * p['saturation'] * 255).clip(0, 255).astype(np.uint8)
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    mask = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
    ix = sx[mask].astype(int)
    iy = sy[mask].astype(int)
    b = bri[mask]
    h6 = int((p['hue'] % 1.0) * 6) % 6
    mults = [(1,.5,0),(.7,1,0),(0,1,.5),(0,.7,1),(.5,0,1),(1,0,.7)]
    rm, gm, bm = mults[h6]
    canvas[iy, ix, 0] = (b * rm).astype(np.uint8)
    canvas[iy, ix, 1] = (b * gm).astype(np.uint8)
    canvas[iy, ix, 2] = (b * bm).astype(np.uint8)
    return canvas

_ALGOS = [_algo_plasma, _algo_fire, _algo_noise, _algo_bars, _algo_radial, _algo_stars]

class Generator:
    def __init__(self):
        self._buf: dict = {}

    def render(self, H: int, W: int, faders: list[float], t: float, beat: float) -> np.ndarray:
        algo_idx = min(int(faders[0] * len(_ALGOS)), len(_ALGOS) - 1)
        p = {
            'beat_react':     faders[1],
            'rhythm_density': faders[2],
            'speed':          faders[3],
            'hue':            faders[4],
            'saturation':     faders[5],
            'color_spread':   faders[6],
            'scale':          faders[7],
            'direction':      faders[8],
            'symmetry':       faders[9],
            'contrast':       faders[10],
            'blur_glow':      faders[11],
        }
        algo = _ALGOS[algo_idx]
        if algo in (_algo_fire, _algo_stars):
            frame = algo(H, W, p, t, beat, self._buf)
        else:
            frame = algo(H, W, p, t, beat)
        frame = _apply_symmetry(frame, p['symmetry'])
        frame = _apply_blur(frame, p['blur_glow'])
        return frame
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_generator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add generator.py tests/test_generator.py
git commit -m "feat: generator with 6 algorithms and 12 fader parameters"
```

---

### Task 9: Video Player

**Files:**
- Create: `video_player.py`
- Create: `tests/test_video_player.py`
- Create: `tests/fixtures/tiny.gif` (generated in test setup)

**Interfaces:**
- Produces:
  - `VideoPlayer(clips_dir: str)` with:
    - `scan_clips() -> list[str | None]` — 64 slots, None if empty
    - `trigger(slot: int, brightness: float = 1.0) -> None`
    - `stop(slot: int) -> None`
    - `get_frame(H: int, W: int, elapsed: float) -> np.ndarray | None`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_video_player.py
import os, cv2, numpy as np, tempfile, pytest
from video_player import VideoPlayer

@pytest.fixture
def clips_dir(tmp_path):
    # Create a tiny 2-frame 4x4 red video as AVI
    path = str(tmp_path / '00_test.avi')
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'MJPG'), 24, (4, 4))
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
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_video_player.py -v
```

- [ ] **Step 3: Implement video_player.py**

```python
# video_player.py
from __future__ import annotations
import os, re, threading
import cv2
import numpy as np

CLIP_SLOTS = 64
_SLOT_RE = re.compile(r'^(\d+)[_\-]?')

class VideoPlayer:
    def __init__(self, clips_dir: str):
        self._clips_dir = clips_dir
        self._caps: dict[int, cv2.VideoCapture] = {}
        self._fpss: dict[int, float] = {}
        self._frame_counts: dict[int, int] = {}
        self._clip_names: list[str | None] = [None] * CLIP_SLOTS
        self._active_slot: int | None = None
        self._brightness: float = 1.0
        self._start_elapsed: float = 0.0
        self._lock = threading.Lock()
        self._open_clips()

    def _open_clips(self) -> None:
        try:
            files = sorted(os.listdir(self._clips_dir))
        except FileNotFoundError:
            return
        for fname in files:
            m = _SLOT_RE.match(fname)
            if not m:
                continue
            slot = int(m.group(1))
            if slot >= CLIP_SLOTS:
                continue
            path = os.path.join(self._clips_dir, fname)
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                continue
            self._caps[slot] = cap
            self._fpss[slot] = cap.get(cv2.CAP_PROP_FPS) or 24.0
            self._frame_counts[slot] = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
            self._clip_names[slot] = fname

    def scan_clips(self) -> list[str | None]:
        return self._clip_names[:]

    def trigger(self, slot: int, brightness: float = 1.0) -> None:
        with self._lock:
            if slot not in self._caps:
                return
            self._active_slot = slot
            self._brightness = brightness
            self._caps[slot].set(cv2.CAP_PROP_POS_FRAMES, 0)

    def stop(self, slot: int) -> None:
        with self._lock:
            if self._active_slot == slot:
                self._active_slot = None

    def get_frame(self, H: int, W: int, elapsed: float) -> np.ndarray | None:
        with self._lock:
            if self._active_slot is None:
                return None
            slot = self._active_slot
            cap = self._caps[slot]
            fps = self._fpss[slot]
            total = self._frame_counts[slot]
            target = int(elapsed * fps) % total
            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    return None
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (W, H), interpolation=cv2.INTER_LINEAR)
            if self._brightness < 0.999:
                frame = (frame.astype(np.float32) * self._brightness).clip(0,255).astype(np.uint8)
            return frame
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_video_player.py -v
```

- [ ] **Step 5: Commit**

```bash
git add video_player.py tests/test_video_player.py
git commit -m "feat: video player with OpenCV frame decode and slot system"
```

---

### Task 10: Compositor & Strobe/Gate

**Files:**
- Create: `compositor.py`
- Create: `tests/test_compositor.py`

**Interfaces:**
- Consumes: numpy frames `(H, W, 3)` uint8
- Produces:
  - `blend(gen: np.ndarray, video: np.ndarray | None, ratio: float) -> np.ndarray`
    - ratio 0.0 = generator only, 1.0 = video only
  - `apply_strobe(frame: np.ndarray, t: float, bpm: float, rate_index: int, depth: float) -> np.ndarray`
  - `apply_master(frame: np.ndarray, master: float) -> np.ndarray`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_compositor.py
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
    # At t=0 with BPM=120 and 1/4 division, should be in on-phase
    result = apply_strobe(frame, 0.0, 120.0, 2, 1.0)
    assert np.all(result == frame)

def test_strobe_off_phase_darkens():
    frame = _frame(200, 100, 50)
    # At t = half period in, should be in off-phase
    bpm = 120.0
    period = (60.0 / bpm) * (4.0 / 4)  # 1/4 note = 0.5s period
    t_off = period * 0.75  # 75% into cycle = off phase
    result = apply_strobe(frame, t_off, bpm, 2, 1.0)
    assert result[0, 0, 0] < frame[0, 0, 0]

def test_strobe_depth_0_never_blacks_out():
    frame = _frame(200, 100, 50)
    bpm = 120.0
    period = (60.0 / bpm) * (4.0 / 4)
    t_off = period * 0.75
    result = apply_strobe(frame, t_off, bpm, 2, 0.0)
    # depth=0: multiplier at off phase = 1.0 - 0.0 = 1.0 → unchanged
    assert np.allclose(result.astype(float), frame.astype(float), atol=2)

def test_apply_master_scales_brightness():
    frame = _frame(200, 100, 50)
    result = apply_master(frame, 0.5)
    assert abs(int(result[0, 0, 0]) - 100) <= 1
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_compositor.py -v
```

- [ ] **Step 3: Implement compositor.py**

```python
# compositor.py
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
                 rate_index: int, depth: float) -> np.ndarray:
    if depth <= 0.0:
        return frame
    division = STROBE_DIVISIONS[rate_index]
    beat_dur = 60.0 / bpm                       # seconds per quarter note
    period = beat_dur * (4.0 / division)        # full strobe cycle
    phase = (t % period) / period               # 0.0 – 1.0
    if phase < 0.5:                             # on phase
        return frame
    multiplier = 1.0 - depth                    # off phase
    return (frame.astype(np.float32) * multiplier).clip(0, 255).astype(np.uint8)

def apply_master(frame: np.ndarray, master: float) -> np.ndarray:
    if master >= 0.999:
        return frame
    return (frame.astype(np.float32) * master).clip(0, 255).astype(np.uint8)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_compositor.py -v
```

- [ ] **Step 5: Commit**

```bash
git add compositor.py tests/test_compositor.py
git commit -m "feat: compositor with layer blend, strobe/gate, and master brightness"
```

---

### Task 11: Preset Manager

**Files:**
- Create: `preset_manager.py`
- Create: `tests/test_preset_manager.py`

**Interfaces:**
- Consumes: `AppState`
- Produces:
  - `PresetManager(path: str, state: AppState)` with:
    - `save(slot: int) -> None`
    - `recall(slot: int) -> None`
    - `tick(dt: float) -> None` — advance fader interpolation

- [ ] **Step 1: Write failing tests**

```python
# tests/test_preset_manager.py
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
    # After tick with large dt, interpolation should reach target
    pm.tick(10.0)
    assert abs(state.faders[0] - 0.8) < 0.01

def test_recall_empty_slot_is_noop(tmp_path):
    state = AppState()
    pm = PresetManager(str(tmp_path / 'presets.json'), state)
    state.update(faders=[0.3]*12)
    pm.recall(5)  # slot 5 never saved
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

def test_interpolation_advances_smoothly(tmp_path):
    state = AppState()
    pm = PresetManager(str(tmp_path / 'p.json'), state)
    pm._transition_s = 1.0
    state.update(faders=[0.0]*12)
    pm.save(0)
    state.update(faders=[1.0]*12)
    pm.recall(0)
    pm.tick(0.5)   # half way
    assert 0.3 < state.faders[0] < 0.7
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_preset_manager.py -v
```

- [ ] **Step 3: Implement preset_manager.py**

```python
# preset_manager.py
from __future__ import annotations
import json
from state import AppState

PRESET_SLOTS = 24

class PresetManager:
    def __init__(self, path: str, state: AppState, transition_ms: int = 200):
        self._path = path
        self._state = state
        self._transition_s = transition_ms / 1000.0
        self._presets: list[list[float] | None] = [None] * PRESET_SLOTS
        self._target: list[float] | None = None
        self._source: list[float] | None = None
        self._elapsed = 0.0
        self._interpolating = False
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path) as f:
                data = json.load(f)
                self._presets = data.get('presets', [None] * PRESET_SLOTS)
                while len(self._presets) < PRESET_SLOTS:
                    self._presets.append(None)
        except FileNotFoundError:
            pass

    def _save_to_disk(self) -> None:
        with open(self._path, 'w') as f:
            json.dump({'presets': self._presets}, f)

    def save(self, slot: int) -> None:
        if 0 <= slot < PRESET_SLOTS:
            self._presets[slot] = self._state.faders[:]
            self._save_to_disk()

    def recall(self, slot: int) -> None:
        if 0 <= slot < PRESET_SLOTS and self._presets[slot] is not None:
            self._source = self._state.faders[:]
            self._target = self._presets[slot][:]
            self._elapsed = 0.0
            self._interpolating = True

    def tick(self, dt: float) -> None:
        if not self._interpolating or self._target is None:
            return
        self._elapsed += dt
        progress = min(self._elapsed / max(self._transition_s, 0.001), 1.0)
        new_faders = [
            self._source[i] + (self._target[i] - self._source[i]) * progress
            for i in range(12)
        ]
        self._state.update(faders=new_faders)
        if progress >= 1.0:
            self._interpolating = False
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_preset_manager.py -v
```

- [ ] **Step 5: Commit**

```bash
git add preset_manager.py tests/test_preset_manager.py
git commit -m "feat: preset manager with 24 slots and smooth interpolation"
```

---

### Task 12: Render Loop

**Files:**
- Create: `render_loop.py`
- Create: `tests/test_render_loop.py`

**Interfaces:**
- Consumes: all engine components
- Produces:
  - `RenderLoop(state, generator, video_player, fixture_sampler, artnet_sender, bpm_analyzer, preset_manager, canvas_size)` with `start() -> None`, `stop() -> None`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_render_loop.py
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
    assert state.beat is False  # consumed
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_render_loop.py -v
```

- [ ] **Step 3: Implement render_loop.py**

```python
# render_loop.py
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
        self._frame_start = 0.0

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

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
                                     snap['strobe_rate_index'], snap['strobe_depth'])

            frame = apply_master(frame, snap['master'])

            universe_data = self._sampler.sample(frame)
            for universe, dmx_bytes in universe_data.items():
                self._artnet.send(universe, dmx_bytes)

            t += dt
            elapsed = time.monotonic() - now
            sleep = target_dt - elapsed
            if sleep > 0:
                time.sleep(sleep)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_render_loop.py -v
```

- [ ] **Step 5: Run all tests to confirm nothing broken**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add render_loop.py tests/test_render_loop.py
git commit -m "feat: 30fps render loop wiring generator, video, compositor, ArtNet"
```

---

### Task 13: Web Server & WebSocket API

**Files:**
- Create: `web_server.py`
- Create: `static/` directory (populated in Tasks 14-16)

**Interfaces:**
- Consumes: `AppState`, `PresetManager`, `VideoPlayer`
- Produces:
  - `create_app(state, preset_manager, video_player, fixtures_path, config_path) -> FastAPI`
  - WebSocket at `/ws` — bidirectional JSON messages
  - Static files at `/`

**WebSocket protocol:**

Server → Client (on connect and on state change):
```json
{"type":"state","faders":[...],"master":1.0,"blend":0.0,"strobe_rate_index":2,
 "strobe_depth":1.0,"strobe_active":false,"active_clip":null,"active_preset":null,
 "bpm":120.0,"midi_clock_active":false,"assignments":{...},"clips":[...]}
```

Client → Server messages:
```json
{"type":"set_fader","index":0,"value":0.75}
{"type":"set_master","value":0.9}
{"type":"set_blend","value":0.5}
{"type":"set_strobe_rate","index":2}
{"type":"set_strobe_depth","value":0.8}
{"type":"set_bpm","value":120.0}
{"type":"save_preset","slot":0}
{"type":"save_fixtures","canvas":{"width":200,"height":100},"fixtures":[...]}
{"type":"save_assignments","assignments":{...}}
{"type":"learn_start","target":"master"}
{"type":"learn_stop"}
```

- [ ] **Step 1: Create static/ directory**

```bash
mkdir -p static
```

- [ ] **Step 2: Implement web_server.py**

```python
# web_server.py
from __future__ import annotations
import asyncio, json, os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from state import AppState
from preset_manager import PresetManager
from video_player import VideoPlayer
from config import save_fixtures, save_config, load_config

class ConnectionManager:
    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)

    def disconnect(self, ws: WebSocket):
        self._clients.remove(ws)

    async def broadcast(self, msg: dict):
        data = json.dumps(msg)
        for client in list(self._clients):
            try:
                await client.send_text(data)
            except Exception:
                self._clients.remove(client)

def create_app(state: AppState, preset_manager: PresetManager,
               video_player: VideoPlayer,
               fixtures_path: str, config_path: str) -> FastAPI:
    app = FastAPI()
    manager = ConnectionManager()

    def _full_state_msg() -> dict:
        snap = state.snapshot()
        snap['type'] = 'state'
        snap['clips'] = video_player.scan_clips()
        return snap

    @app.websocket('/ws')
    async def ws_endpoint(ws: WebSocket):
        await manager.connect(ws)
        await ws.send_text(json.dumps(_full_state_msg()))
        try:
            while True:
                text = await ws.receive_text()
                msg = json.loads(text)
                mtype = msg.get('type')

                if mtype == 'set_fader':
                    faders = state.faders[:]
                    faders[msg['index']] = float(msg['value'])
                    state.update(faders=faders)

                elif mtype == 'set_master':
                    state.update(master=float(msg['value']))

                elif mtype == 'set_blend':
                    state.update(blend=float(msg['value']))

                elif mtype == 'set_strobe_rate':
                    state.update(strobe_rate_index=int(msg['index']))

                elif mtype == 'set_strobe_depth':
                    state.update(strobe_depth=float(msg['value']))

                elif mtype == 'set_bpm':
                    state.update(bpm=float(msg['value']))

                elif mtype == 'save_preset':
                    preset_manager.save(int(msg['slot']))

                elif mtype == 'save_fixtures':
                    save_fixtures({'canvas': msg['canvas'],
                                   'fixtures': msg['fixtures']}, fixtures_path)

                elif mtype == 'save_assignments':
                    state.update(assignments=msg['assignments'])
                    cfg = load_config(config_path)
                    cfg['midi']['assignments'] = msg['assignments']
                    save_config(cfg, config_path)

                elif mtype == 'learn_start':
                    state.update(learn_target=msg['target'])

                elif mtype == 'learn_stop':
                    state.update(learn_target=None)

                await manager.broadcast(_full_state_msg())

        except WebSocketDisconnect:
            manager.disconnect(ws)

    # State push task: broadcast state every 500ms so BPM/clock updates show in UI
    @app.on_event('startup')
    async def start_push():
        async def _push():
            while True:
                await asyncio.sleep(0.5)
                await manager.broadcast(_full_state_msg())
        asyncio.create_task(_push())

    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    if os.path.isdir(static_dir):
        app.mount('/static', StaticFiles(directory=static_dir), name='static')

    @app.get('/')
    async def index():
        return FileResponse(os.path.join(static_dir, 'index.html'))

    return app
```

- [ ] **Step 3: Create placeholder static files so the server starts**

```bash
echo '<!DOCTYPE html><html><body>Loading...</body></html>' > static/index.html
echo '' > static/style.css
echo '' > static/app.js
```

- [ ] **Step 4: Smoke test the server**

```python
# Quick manual check — add to a scratch file, then delete
# Run: python3 -c "from web_server import create_app; print('OK')"
```

```bash
python3 -c "from web_server import create_app; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add web_server.py static/
git commit -m "feat: FastAPI WebSocket server with state sync and REST-free bidirectional API"
```

---

### Task 14: Browser UI — Main Page

**Files:**
- Modify: `static/index.html`
- Modify: `static/style.css`
- Modify: `static/app.js`

**Interfaces:**
- Consumes: WebSocket at `ws://localhost:8080/ws`
- Produces: working main page with faders, presets, clips, BPM, strobe

- [ ] **Step 1: Write static/style.css**

```css
/* static/style.css */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #111; color: #eee; font-family: monospace; font-size: 13px; }
nav { display: flex; gap: 0; background: #1a1a1a; border-bottom: 1px solid #333; }
nav button { background: none; border: none; color: #999; padding: 10px 20px;
             cursor: pointer; border-bottom: 2px solid transparent; }
nav button.active { color: #fff; border-bottom-color: #0af; }
.page { display: none; padding: 16px; }
.page.active { display: block; }

/* Status bar */
#status-bar { display: flex; gap: 16px; align-items: center; padding: 8px 0;
              border-bottom: 1px solid #222; margin-bottom: 12px; }
.bpm-display { font-size: 20px; font-weight: bold; color: #0af; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #333; }
.dot.active { background: #0f0; }
.ctrl { display: flex; align-items: center; gap: 6px; }
.ctrl label { color: #888; }

/* Faders */
#faders { display: flex; gap: 10px; margin-bottom: 16px; }
.fader-col { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.fader-col input[type=range] { writing-mode: vertical-lr; direction: rtl;
                                width: 28px; height: 120px; cursor: pointer;
                                accent-color: #0af; }
.fader-col .fname { font-size: 9px; color: #888; text-align: center; max-width: 36px; }
.fader-col .fcc { font-size: 9px; color: #555; }

/* Presets */
#presets { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.preset-btn { width: 38px; height: 28px; background: #222; border: 1px solid #444;
              color: #aaa; cursor: pointer; border-radius: 3px; font-size: 11px; }
.preset-btn.active { background: #0af; color: #000; border-color: #0af; }
.preset-btn:hover { border-color: #888; }

/* Clips */
#clips { margin-bottom: 16px; }
#clips h3 { color: #666; margin-bottom: 6px; font-size: 11px; text-transform: uppercase; }
#clip-list { display: flex; flex-wrap: wrap; gap: 4px; }
.clip-btn { padding: 3px 8px; background: #1a1a1a; border: 1px solid #333;
            color: #888; border-radius: 2px; font-size: 11px; cursor: default; }
.clip-btn.occupied { color: #ccc; border-color: #555; }
.clip-btn.active { background: #0af; color: #000; border-color: #0af; }

/* Strobe */
#strobe-section { background: #1a1a1a; border: 1px solid #333; padding: 10px;
                  border-radius: 4px; display: flex; align-items: center; gap: 16px; }
#strobe-section.on { border-color: #f50; }
.strobe-rate-display { font-size: 16px; color: #f80; font-weight: bold; min-width: 80px; }

/* Fixture editor */
#canvas-grid { border: 1px solid #333; display: block; cursor: crosshair; }
#fixture-form { margin-top: 12px; display: grid; grid-template-columns: auto 1fr; gap: 6px 10px; }
#fixture-form label { color: #888; align-self: center; }
#fixture-form input, #fixture-form select { background: #222; border: 1px solid #444;
  color: #eee; padding: 3px 6px; font-family: monospace; width: 100%; }

/* MIDI routing */
#midi-table { width: 100%; border-collapse: collapse; }
#midi-table th { color: #666; text-align: left; padding: 4px 8px;
                 border-bottom: 1px solid #333; font-weight: normal; }
#midi-table td { padding: 4px 8px; border-bottom: 1px solid #1a1a1a; }
#midi-table tr:hover td { background: #1a1a1a; }
.learn-btn { background: #222; border: 1px solid #444; color: #888;
             padding: 2px 8px; cursor: pointer; font-size: 11px; }
.learn-btn.learning { background: #f80; color: #000; border-color: #f80; }
button.primary { background: #0af; border: none; color: #000; padding: 6px 14px;
                 cursor: pointer; font-weight: bold; border-radius: 3px; }
button.danger { background: #600; border: none; color: #eee; padding: 6px 14px;
                cursor: pointer; border-radius: 3px; }
```

- [ ] **Step 2: Write static/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MIDI Lightshow</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
<nav>
  <button class="active" onclick="showPage('main',this)">Main</button>
  <button onclick="showPage('fixtures',this)">Fixture Editor</button>
  <button onclick="showPage('midi',this)">MIDI Routing</button>
</nav>

<!-- PAGE: MAIN -->
<div id="page-main" class="page active">
  <div id="status-bar">
    <span class="bpm-display" id="bpm-val">120.0</span>
    <span>BPM</span>
    <span class="dot" id="clock-dot" title="MIDI clock"></span>
    <div class="ctrl">
      <label>Master</label>
      <input type="range" id="master-fader" min="0" max="127" value="127"
             oninput="sendCC('set_master', this.value/127)">
    </div>
    <div class="ctrl">
      <label>Blend G↔V</label>
      <input type="range" id="blend-fader" min="0" max="127" value="0"
             oninput="sendCC('set_blend', this.value/127)">
    </div>
  </div>

  <h3 style="color:#666;font-size:11px;text-transform:uppercase;margin-bottom:8px">Generator Faders</h3>
  <div id="faders"></div>

  <h3 style="color:#666;font-size:11px;text-transform:uppercase;margin-bottom:8px">Presets</h3>
  <div id="presets"></div>
  <div style="margin-bottom:16px">
    <button class="primary" onclick="savePreset()">Save to selected</button>
  </div>

  <div id="clips">
    <h3>Clips (notes 0–63)</h3>
    <div id="clip-list"></div>
  </div>

  <div id="strobe-section">
    <div>
      <div style="color:#888;font-size:10px;text-transform:uppercase">Strobe</div>
      <div class="strobe-rate-display" id="strobe-rate-display">1/4</div>
      <div style="font-size:10px;color:#666" id="strobe-bpm-display">@ 120 BPM</div>
    </div>
    <div class="ctrl">
      <label>Rate</label>
      <input type="range" id="strobe-rate" min="0" max="5" step="1" value="2"
             oninput="ws.send(JSON.stringify({type:'set_strobe_rate',index:+this.value}))">
    </div>
    <div class="ctrl">
      <label>Depth</label>
      <input type="range" id="strobe-depth" min="0" max="127" value="127"
             oninput="sendCC('set_strobe_depth', this.value/127)">
    </div>
    <div id="strobe-indicator" style="color:#555;font-size:11px">OFF (note 88)</div>
  </div>
</div>

<!-- PAGE: FIXTURE EDITOR -->
<div id="page-fixtures" class="page">
  <div style="display:flex;gap:16px;align-items:flex-start">
    <div>
      <div style="margin-bottom:8px;display:flex;gap:8px;align-items:center">
        <label>W<input id="canvas-w" type="number" value="200" style="width:60px;margin-left:4px;background:#222;border:1px solid #444;color:#eee;padding:2px 4px"></label>
        <label>H<input id="canvas-h" type="number" value="100" style="width:60px;margin-left:4px;background:#222;border:1px solid #444;color:#eee;padding:2px 4px"></label>
        <button class="primary" onclick="applyCanvas()">Apply</button>
      </div>
      <canvas id="canvas-grid" width="600" height="300"></canvas>
    </div>
    <div style="min-width:220px">
      <button class="primary" onclick="addStrip()" style="margin-bottom:8px;width:100%">+ Add Strip</button>
      <button class="danger" onclick="deleteStrip()" style="margin-bottom:16px;width:100%">Delete Selected</button>
      <div id="fixture-form" style="display:none">
        <label>Name</label><input id="f-name" type="text">
        <label>X</label><input id="f-x" type="number" value="0">
        <label>Y</label><input id="f-y" type="number" value="0">
        <label>Orient</label>
        <select id="f-orient"><option value="H">Horizontal</option><option value="V">Vertical</option></select>
        <label>Universe</label><input id="f-universe" type="number" value="0">
        <label>Start CH</label><input id="f-ch" type="number" value="0">
        <button class="primary" onclick="applyFixture()" style="grid-column:1/-1;margin-top:8px">Apply</button>
      </div>
    </div>
  </div>
  <div style="margin-top:12px">
    <button class="primary" onclick="saveFixtures()">Save Layout</button>
  </div>
</div>

<!-- PAGE: MIDI ROUTING -->
<div id="page-midi" class="page">
  <table id="midi-table">
    <thead><tr><th>Function</th><th>Type</th><th>Number</th><th>Channel</th><th></th></tr></thead>
    <tbody id="midi-tbody"></tbody>
  </table>
  <div style="margin-top:12px;display:flex;gap:8px">
    <button class="primary" onclick="saveAssignments()">Save</button>
    <button onclick="resetAssignments()">Reset to defaults</button>
  </div>
</div>

<script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write static/app.js**

```javascript
// static/app.js
const STROBE_LABELS = ['1/1','1/2','1/4','1/8','1/16','1/32'];
const FADER_NAMES = ['Algorithm','Beat React','Rhythm','Speed','Hue','Saturation',
                     'Colour Spread','Scale','Direction','Symmetry','Contrast','Blur/Glow'];
const CC_NUMS = [24,25,26,27,28,29,30,31,32,33,34,35];

let ws, state = {}, selectedPreset = null, selectedFixture = null;
let fixtures = [], canvasSize = {width:200, height:100};

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = e => applyState(JSON.parse(e.data));
  ws.onclose = () => setTimeout(connect, 2000);
}

function send(msg) { if (ws.readyState===1) ws.send(JSON.stringify(msg)); }
function sendCC(type, value) { send({type, value: +value}); }

function showPage(name, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  btn.classList.add('active');
}

function applyState(s) {
  state = s;
  // BPM
  document.getElementById('bpm-val').textContent = (s.bpm||120).toFixed(1);
  document.getElementById('clock-dot').classList.toggle('active', !!s.midi_clock_active);
  // Master / blend
  document.getElementById('master-fader').value = Math.round((s.master||1)*127);
  document.getElementById('blend-fader').value = Math.round((s.blend||0)*127);
  // Faders
  const fc = document.getElementById('faders');
  if (!fc.children.length) buildFaders(fc);
  (s.faders||[]).forEach((v,i) => {
    const el = document.getElementById('fader-'+i);
    if (el) el.value = Math.round(v*127);
  });
  // Presets
  document.querySelectorAll('.preset-btn').forEach((btn,i) => {
    btn.classList.toggle('active', s.active_preset === i);
  });
  // Clips
  buildClips(s.clips||[]);
  // Strobe
  document.getElementById('strobe-rate').value = s.strobe_rate_index||2;
  document.getElementById('strobe-depth').value = Math.round((s.strobe_depth||1)*127);
  document.getElementById('strobe-rate-display').textContent = STROBE_LABELS[s.strobe_rate_index||2];
  document.getElementById('strobe-bpm-display').textContent = `@ ${(s.bpm||120).toFixed(0)} BPM`;
  const sec = document.getElementById('strobe-section');
  sec.classList.toggle('on', !!s.strobe_active);
  document.getElementById('strobe-indicator').textContent = s.strobe_active ? 'ON' : 'OFF (note 88)';
  // MIDI table
  if (document.getElementById('page-midi').classList.contains('active')) buildMidiTable(s.assignments||{});
}

function buildFaders(container) {
  container.innerHTML = '';
  FADER_NAMES.forEach((name, i) => {
    const col = document.createElement('div');
    col.className = 'fader-col';
    col.innerHTML = `
      <input type="range" id="fader-${i}" min="0" max="127" value="64"
             oninput="send({type:'set_fader',index:${i},value:this.value/127})">
      <div class="fname">${name}</div>
      <div class="fcc">CC${CC_NUMS[i]}</div>`;
    container.appendChild(col);
  });
}

function buildPresets() {
  const c = document.getElementById('presets');
  c.innerHTML = '';
  for (let i = 0; i < 24; i++) {
    const btn = document.createElement('button');
    btn.className = 'preset-btn';
    btn.textContent = i+1;
    btn.onclick = () => { selectedPreset = i; updatePresetUI(); };
    c.appendChild(btn);
  }
}

function updatePresetUI() {
  document.querySelectorAll('.preset-btn').forEach((b,i) =>
    b.classList.toggle('active', i === selectedPreset));
}

function savePreset() {
  if (selectedPreset !== null) send({type:'save_preset', slot: selectedPreset});
}

function buildClips(clips) {
  const c = document.getElementById('clip-list');
  c.innerHTML = '';
  clips.forEach((name, i) => {
    const btn = document.createElement('div');
    btn.className = 'clip-btn' + (name ? ' occupied' : '') + (state.active_clip===i ? ' active' : '');
    btn.textContent = name ? `${i}: ${name}` : `${i}`;
    c.appendChild(btn);
  });
}

// ── Fixture Editor ────────────────────────────────────────────────────────────
const gridCanvas = document.getElementById('canvas-grid');
const ctx = gridCanvas.getContext('2d');

function applyCanvas() {
  canvasSize = {
    width: +document.getElementById('canvas-w').value,
    height: +document.getElementById('canvas-h').value
  };
  drawGrid();
}

function drawGrid() {
  const scale = 600 / canvasSize.width;
  gridCanvas.width = 600;
  gridCanvas.height = Math.round(canvasSize.height * scale);
  ctx.fillStyle = '#111';
  ctx.fillRect(0, 0, gridCanvas.width, gridCanvas.height);
  ctx.strokeStyle = '#222';
  ctx.lineWidth = 1;
  for (let x = 0; x <= canvasSize.width; x += 10) {
    ctx.beginPath(); ctx.moveTo(x*scale, 0); ctx.lineTo(x*scale, gridCanvas.height); ctx.stroke();
  }
  for (let y = 0; y <= canvasSize.height; y += 10) {
    ctx.beginPath(); ctx.moveTo(0, y*scale); ctx.lineTo(gridCanvas.width, y*scale); ctx.stroke();
  }
  fixtures.forEach((f, idx) => drawFixture(f, idx === selectedFixture, scale));
}

function drawFixture(f, selected, scale) {
  const len = f.length || 40;
  const x = f.x * scale, y = f.y * scale;
  const w = f.orientation === 'H' ? len * scale : 4;
  const h = f.orientation === 'H' ? 4 : len * scale;
  ctx.fillStyle = selected ? '#0af' : '#f80';
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = '#fff';
  ctx.font = '9px monospace';
  ctx.fillText(f.name || `f${fixtures.indexOf(f)}`, x+2, y+10);
}

gridCanvas.onclick = e => {
  const scale = 600 / canvasSize.width;
  const rx = e.offsetX / scale, ry = e.offsetY / scale;
  let hit = -1;
  fixtures.forEach((f, i) => {
    const len = f.length || 40;
    const fx2 = f.x + (f.orientation==='H' ? len : 4/scale);
    const fy2 = f.y + (f.orientation==='H' ? 4/scale : len);
    if (rx >= f.x && rx <= fx2 && ry >= f.y && ry <= fy2) hit = i;
  });
  if (hit >= 0) { selectedFixture = hit; showFixtureForm(fixtures[hit]); drawGrid(); }
};

function addStrip() {
  fixtures.push({name: `strip_${fixtures.length+1}`, x:0, y:0,
                 orientation:'H', length:40, universe:0, start_channel:0});
  selectedFixture = fixtures.length - 1;
  showFixtureForm(fixtures[selectedFixture]);
  drawGrid();
}

function deleteStrip() {
  if (selectedFixture !== null) {
    fixtures.splice(selectedFixture, 1);
    selectedFixture = null;
    document.getElementById('fixture-form').style.display = 'none';
    drawGrid();
  }
}

function showFixtureForm(f) {
  document.getElementById('fixture-form').style.display = 'grid';
  document.getElementById('f-name').value = f.name || '';
  document.getElementById('f-x').value = f.x;
  document.getElementById('f-y').value = f.y;
  document.getElementById('f-orient').value = f.orientation || 'H';
  document.getElementById('f-universe').value = f.universe;
  document.getElementById('f-ch').value = f.start_channel;
}

function applyFixture() {
  if (selectedFixture === null) return;
  fixtures[selectedFixture] = {
    name: document.getElementById('f-name').value,
    x: +document.getElementById('f-x').value,
    y: +document.getElementById('f-y').value,
    orientation: document.getElementById('f-orient').value,
    length: 40,
    universe: +document.getElementById('f-universe').value,
    start_channel: +document.getElementById('f-ch').value,
  };
  drawGrid();
}

function saveFixtures() {
  send({type:'save_fixtures', canvas: canvasSize, fixtures});
}

// ── MIDI Routing ──────────────────────────────────────────────────────────────
let localAssignments = {};
let learningTarget = null;

function buildMidiTable(assignments) {
  localAssignments = JSON.parse(JSON.stringify(assignments));
  const tbody = document.getElementById('midi-tbody');
  tbody.innerHTML = '';
  Object.entries(assignments).forEach(([name, asgn]) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${name}</td>
      <td>${asgn.type}</td>
      <td>${asgn.number}</td>
      <td>${asgn.channel}</td>
      <td><button class="learn-btn ${learningTarget===name?'learning':''}"
          onclick="startLearn('${name}',this)">${learningTarget===name?'Listening…':'Learn'}</button></td>`;
    tbody.appendChild(tr);
  });
}

function startLearn(target, btn) {
  learningTarget = target;
  document.querySelectorAll('.learn-btn').forEach(b => b.classList.remove('learning'));
  btn.classList.add('learning');
  send({type:'learn_start', target});
}

function saveAssignments() {
  send({type:'save_assignments', assignments: localAssignments});
}

function resetAssignments() {
  send({type:'save_assignments', assignments: {}});
}

// ── Init ──────────────────────────────────────────────────────────────────────
buildPresets();
drawGrid();
connect();
```

- [ ] **Step 4: Manual test — start the server**

```bash
python3 -c "
from state import AppState
from preset_manager import PresetManager
from video_player import VideoPlayer
from web_server import create_app
import uvicorn

state = AppState()
pm = PresetManager('presets.json', state)
vp = VideoPlayer('clips')
app = create_app(state, pm, vp, 'fixtures.json', 'config.yaml')
uvicorn.run(app, host='0.0.0.0', port=8080)
"
```

Open `http://localhost:8080` — all three tabs should render, faders should be visible.

- [ ] **Step 5: Commit**

```bash
git add static/ web_server.py
git commit -m "feat: browser UI with faders, presets, clips, fixture editor, MIDI routing"
```

---

### Task 15: main.py — Full Wiring

**Files:**
- Create: `main.py`

**Interfaces:**
- Consumes: all modules
- Produces: runnable app via `python3 main.py`

- [ ] **Step 1: Implement main.py**

```python
# main.py
import asyncio, sys, signal
import uvicorn
from config import load_config, load_fixtures
from state import AppState
from bpm_analyzer import BPMAnalyzer
from midi_input import MidiDispatcher, open_virtual_port
from generator import Generator
from video_player import VideoPlayer
from fixture_sampler import FixtureSampler
from artnet_output import ArtNetSender
from preset_manager import PresetManager
from render_loop import RenderLoop
from web_server import create_app

CONFIG_PATH   = 'config.yaml'
FIXTURES_PATH = 'fixtures.json'
PRESETS_PATH  = 'presets.json'
CLIPS_DIR     = 'clips'

def main():
    cfg      = load_config(CONFIG_PATH)
    fix_data = load_fixtures(FIXTURES_PATH)

    state = AppState()
    state.update(assignments=cfg['midi']['assignments'])

    canvas_w = fix_data['canvas']['width']
    canvas_h = fix_data['canvas']['height']

    bpm_analyzer   = BPMAnalyzer()
    generator      = Generator()
    video_player   = VideoPlayer(CLIPS_DIR)
    fixture_sampler = FixtureSampler(fix_data['fixtures'])
    artnet_sender  = ArtNetSender(cfg['artnet']['ip'], cfg['artnet']['port'])
    preset_manager = PresetManager(PRESETS_PATH, state,
                                   cfg['app']['preset_transition_ms'])
    dispatcher     = MidiDispatcher(state, bpm_analyzer)

    render_loop = RenderLoop(
        state, generator, video_player, fixture_sampler,
        artnet_sender, bpm_analyzer, preset_manager,
        (canvas_h, canvas_w),
    )

    midi_in = open_virtual_port(dispatcher, cfg['midi']['port_name'])
    print(f"[MIDI] Virtual port '{cfg['midi']['port_name']}' open")

    render_loop.start()
    print(f"[Render] 30fps loop started — canvas {canvas_w}x{canvas_h}")
    print(f"[ArtNet] Sending to {cfg['artnet']['ip']}:{cfg['artnet']['port']}")

    app = create_app(state, preset_manager, video_player, FIXTURES_PATH, CONFIG_PATH)

    def shutdown(sig, frame):
        print('\nShutting down…')
        render_loop.stop()
        artnet_sender.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print('[UI] Open http://localhost:8080')
    uvicorn.run(app, host='0.0.0.0', port=8080)

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run all tests one final time**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 3: Smoke test startup**

```bash
python3 main.py
```

Expected output:
```
[MIDI] Virtual port 'LightShow' open
[Render] 30fps loop started — canvas 200x100
[ArtNet] Sending to 10.0.0.23:6454
[UI] Open http://localhost:8080
INFO:     Uvicorn running on http://0.0.0.0:8080
```

Then open `http://localhost:8080`, connect Ableton to "LightShow" MIDI port.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: main.py wires all components and starts app"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Standalone Python app, virtual MIDI port (Task 5, Task 15)
- ✅ Video clip playback triggered by notes 0–63 (Task 9, Task 5)
- ✅ Generator with 6 algorithms and 12 faders CC24–35 (Task 8)
- ✅ 24 presets notes 64–87 with interpolation (Task 11, Task 5)
- ✅ Strobe/gate note 88, CC2 rate as musical divisions, CC3 depth (Task 10, Task 5)
- ✅ BPM from MIDI clock, shown in UI (Task 4, Task 14)
- ✅ Layer blending CC1 (Task 10)
- ✅ Master brightness CC0 (Task 10)
- ✅ Browser UI: faders, presets, clips, strobe, BPM (Task 14)
- ✅ Fixture editor with canvas grid and per-strip universe/channel (Task 14)
- ✅ MIDI routing page with learn mode (Task 14)
- ✅ ArtNet UDP output (Task 6)
- ✅ Fixture sampler with coordinate-based mapping (Task 7)
- ✅ config.yaml and fixtures.json persistence (Task 3)
- ✅ 30fps render loop (Task 12)
