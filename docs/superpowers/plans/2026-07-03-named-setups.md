# Named Setups (MIDI Mapping + Fixture Layout) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user save the current MIDI mapping + fixture layout (incl. ArtNet universe/channel) as a named "setup" and reload it later, from either the Fixture Editor or MIDI Routing tab.

**Architecture:** A new `setups.json` file (same load/save pattern as `presets.json`/`fixtures.json`) stores `{name: {assignments, fixtures}}`. Two new WebSocket message types (`save_setup`, `load_setup`) commit the bundle as the active config (same effect as today's "Save Layout"/"Save" buttons) and, for `load_setup`, additionally push a `fixtures_reload` message so connected browsers refresh their Fixture Editor grid (client-side fixture edits are otherwise never synced from the server after initial page load — this plan also fixes that gap, since Load Setup needs it).

**Tech Stack:** Python (FastAPI, PyYAML), vanilla JS, pytest + FastAPI `TestClient`.

## Global Constraints

- Match existing project conventions: plain functions in `config.py` for JSON/YAML persistence (no classes), MagicMock-based mocking in tests, inline styles in HTML (no CSS framework).
- No delete/rename of setups in this pass — saving under an existing name overwrites it (YAGNI, not requested).
- `setups.json` bundle format: `{"<name>": {"assignments": {...}, "fixtures": {"canvas": {...}, "fixtures": [...]}}}`.

---

## Task 1: `config.py` — load/save setups

**Files:**
- Modify: `config.py` (append after `save_fixtures`, currently ends at line 49)
- Test: `tests/test_config.py` (modify import line 3, append tests)

**Interfaces:**
- Produces: `load_setups(path: str) -> dict` (returns `{}` if file missing), `save_setups(data: dict, path: str) -> None`.

- [ ] **Step 1: Write the failing tests**

Modify `tests/test_config.py` line 3 from:
```python
from config import load_config, save_config, load_fixtures, save_fixtures, default_config
```
to:
```python
from config import load_config, save_config, load_fixtures, save_fixtures, default_config, load_setups, save_setups
```

Append to `tests/test_config.py`:
```python
def test_load_setups_missing_file_returns_empty(tmp_path):
    path = str(tmp_path / 'setups.json')
    assert load_setups(path) == {}

def test_save_and_load_setups(tmp_path):
    path = str(tmp_path / 'setups.json')
    data = {
        'venue_a': {
            'assignments': {'master': {'type': 'cc', 'number': 0, 'channel': 1}},
            'fixtures': {'canvas': {'width': 200, 'height': 100}, 'fixtures': []},
        }
    }
    save_setups(data, path)
    loaded = load_setups(path)
    assert loaded['venue_a']['fixtures']['canvas']['width'] == 200
    assert loaded['venue_a']['assignments']['master']['number'] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_setups'`

- [ ] **Step 3: Implement**

Append to `config.py`:
```python
def load_setups(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_setups(data: dict, path: str) -> None:
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: All PASS (6 tests: 4 existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add load_setups/save_setups for named setup persistence"
```

---

## Task 2: `web_server.py` — save_setup / load_setup handlers + fixtures sync

**Files:**
- Modify: `web_server.py`
- Modify: `main.py`
- Test: Create `tests/test_web_server.py`

**Interfaces:**
- Consumes: `load_setups`, `save_setups` from Task 1; `load_fixtures`, `save_fixtures`, `load_config`, `save_config` (existing, `config.py`).
- Produces: `create_app(state, preset_manager, video_player, fixture_sampler, render_loop, fixtures_path, config_path, setups_path) -> FastAPI` (adds one trailing required param `setups_path` to the existing signature). WS message types `save_setup {name, canvas, fixtures, assignments}` and `load_setup {name}`. A `fixtures_reload` message (`{'type': 'fixtures_reload', 'canvas': {...}, 'fixtures': [...]}`) sent once on every new connection and after every `save_setup`/`load_setup`. `_full_state_msg()`'s dict gains a `'setups'` key: `list[str]` of saved setup names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_web_server.py`:
```python
import json
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from state import AppState
from web_server import create_app
from config import save_config, default_config, save_fixtures

def _make_client(tmp_path):
    state = AppState()
    preset_manager = MagicMock()
    video_player = MagicMock()
    video_player.scan_clips.return_value = [None] * 64
    fixture_sampler = MagicMock()
    render_loop = MagicMock()
    render_loop.get_preview_jpeg.return_value = None
    render_loop.get_thumbnail_jpeg.return_value = None

    config_path = str(tmp_path / 'config.yaml')
    fixtures_path = str(tmp_path / 'fixtures.json')
    setups_path = str(tmp_path / 'setups.json')
    save_config(default_config(), config_path)
    save_fixtures({'canvas': {'width': 200, 'height': 100}, 'fixtures': []}, fixtures_path)

    app = create_app(state, preset_manager, video_player, fixture_sampler,
                      render_loop, fixtures_path, config_path, setups_path)
    client = TestClient(app)
    return client, fixture_sampler, fixtures_path, config_path, setups_path

def test_websocket_sends_fixtures_reload_on_connect(tmp_path):
    client, *_ = _make_client(tmp_path)
    with client.websocket_connect('/ws') as ws:
        state_msg = ws.receive_json()
        assert state_msg['type'] == 'state'
        assert state_msg['setups'] == []
        reload_msg = ws.receive_json()
        assert reload_msg['type'] == 'fixtures_reload'
        assert reload_msg['canvas']['width'] == 200

def test_save_setup_persists_bundle_and_broadcasts(tmp_path):
    client, fixture_sampler, fixtures_path, config_path, setups_path = _make_client(tmp_path)
    with client.websocket_connect('/ws') as ws:
        ws.receive_json()  # state
        ws.receive_json()  # fixtures_reload
        ws.send_json({
            'type': 'save_setup',
            'name': 'venue_a',
            'canvas': {'width': 300, 'height': 150},
            'fixtures': [{'name': 'strip_1', 'x': 0, 'y': 0, 'orientation': 'V',
                          'length': 40, 'universe': 0, 'start_channel': 0}],
            'assignments': {'master': {'type': 'cc', 'number': 0, 'channel': 1}},
        })
        reload_msg = ws.receive_json()
        assert reload_msg['type'] == 'fixtures_reload'
        assert reload_msg['canvas']['width'] == 300
        state_msg = ws.receive_json()
        assert state_msg['type'] == 'state'
        assert 'venue_a' in state_msg['setups']

    with open(setups_path) as f:
        saved = json.load(f)
    assert saved['venue_a']['fixtures']['canvas']['width'] == 300
    assert saved['venue_a']['assignments']['master']['number'] == 0
    fixture_sampler.set_fixtures.assert_called_once()

def test_load_setup_restores_bundle(tmp_path):
    client, fixture_sampler, fixtures_path, config_path, setups_path = _make_client(tmp_path)
    with client.websocket_connect('/ws') as ws:
        ws.receive_json(); ws.receive_json()  # initial state + fixtures_reload

        ws.send_json({
            'type': 'save_setup', 'name': 'venue_a',
            'canvas': {'width': 300, 'height': 150},
            'fixtures': [{'name': 'strip_1', 'x': 0, 'y': 0, 'orientation': 'V',
                          'length': 40, 'universe': 0, 'start_channel': 0}],
            'assignments': {'master': {'type': 'cc', 'number': 0, 'channel': 1}},
        })
        ws.receive_json(); ws.receive_json()  # fixtures_reload + state from save_setup

        ws.send_json({
            'type': 'save_fixtures',
            'canvas': {'width': 200, 'height': 100},
            'fixtures': [],
        })
        ws.receive_json()  # state broadcast from save_fixtures (no fixtures_reload for plain save)

        ws.send_json({'type': 'load_setup', 'name': 'venue_a'})
        reload_msg = ws.receive_json()
        assert reload_msg['type'] == 'fixtures_reload'
        assert reload_msg['canvas']['width'] == 300
        state_msg = ws.receive_json()
        assert state_msg['assignments']['master']['number'] == 0

def test_algo_thumbnail_endpoint_returns_204_when_not_rendered(tmp_path):
    client, *_ = _make_client(tmp_path)
    resp = client.get('/algo_thumbnail/0')
    assert resp.status_code == 204
```

Note: the last test (`test_algo_thumbnail_endpoint_returns_204_when_not_rendered`) will only pass once the Thumbnail Selector plan's `/algo_thumbnail/{idx}` endpoint exists — if that plan hasn't run yet, skip adding this one test for now (the other four are this task's actual scope).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_web_server.py -v`
Expected: FAIL — `create_app() missing 1 required positional argument: 'setups_path'`

- [ ] **Step 3: Implement**

In `web_server.py`, change the import line (currently line 9):
```python
from config import save_fixtures, save_config, load_config
```
to:
```python
from config import save_fixtures, save_config, load_config, load_fixtures, load_setups, save_setups
```

Change `create_app`'s signature (currently lines 32-34):
```python
def create_app(state: AppState, preset_manager: PresetManager,
               video_player: VideoPlayer, fixture_sampler, render_loop,
               fixtures_path: str, config_path: str) -> FastAPI:
```
to:
```python
def create_app(state: AppState, preset_manager: PresetManager,
               video_player: VideoPlayer, fixture_sampler, render_loop,
               fixtures_path: str, config_path: str, setups_path: str) -> FastAPI:
```

Change `_full_state_msg` (currently lines 38-42):
```python
    def _full_state_msg() -> dict:
        snap = state.snapshot()
        snap['type'] = 'state'
        snap['clips'] = video_player.scan_clips()
        return snap
```
to:
```python
    def _full_state_msg() -> dict:
        snap = state.snapshot()
        snap['type'] = 'state'
        snap['clips'] = video_player.scan_clips()
        snap['setups'] = list(load_setups(setups_path).keys())
        return snap
```

Change the connect block (currently lines 44-47):
```python
    @app.websocket('/ws')
    async def ws_endpoint(ws: WebSocket):
        await manager.connect(ws)
        await ws.send_text(json.dumps(_full_state_msg()))
```
to:
```python
    @app.websocket('/ws')
    async def ws_endpoint(ws: WebSocket):
        await manager.connect(ws)
        await ws.send_text(json.dumps(_full_state_msg()))
        fixtures_data = load_fixtures(fixtures_path)
        await ws.send_text(json.dumps({'type': 'fixtures_reload', **fixtures_data}))
```

Add two new `elif` branches right after the existing `save_assignments` branch (currently lines 98-102):
```python
                elif mtype == 'save_assignments':
                    state.update(assignments=msg['assignments'])
                    cfg = load_config(config_path)
                    cfg['midi']['assignments'] = msg['assignments']
                    save_config(cfg, config_path)

                elif mtype == 'save_setup':
                    name = msg['name']
                    assignments = msg['assignments']
                    fixtures_data = {'canvas': msg['canvas'], 'fixtures': msg['fixtures']}
                    state.update(assignments=assignments)
                    cfg = load_config(config_path)
                    cfg['midi']['assignments'] = assignments
                    save_config(cfg, config_path)
                    save_fixtures(fixtures_data, fixtures_path)
                    fixture_sampler.set_fixtures(msg['fixtures'])
                    setups = load_setups(setups_path)
                    setups[name] = {'assignments': assignments, 'fixtures': fixtures_data}
                    save_setups(setups, setups_path)
                    await manager.broadcast({'type': 'fixtures_reload', **fixtures_data})

                elif mtype == 'load_setup':
                    setups = load_setups(setups_path)
                    bundle = setups.get(msg['name'])
                    if bundle is not None:
                        state.update(assignments=bundle['assignments'])
                        cfg = load_config(config_path)
                        cfg['midi']['assignments'] = bundle['assignments']
                        save_config(cfg, config_path)
                        save_fixtures(bundle['fixtures'], fixtures_path)
                        fixture_sampler.set_fixtures(bundle['fixtures']['fixtures'])
                        await manager.broadcast({'type': 'fixtures_reload', **bundle['fixtures']})
```

In `main.py`, add a path constant after line 17 (`PRESETS_PATH  = 'presets.json'`):
```python
SETUPS_PATH   = 'setups.json'
```
and change the `create_app(...)` call (currently line 52):
```python
    app = create_app(state, preset_manager, video_player, fixture_sampler, render_loop, FIXTURES_PATH, CONFIG_PATH)
```
to:
```python
    app = create_app(state, preset_manager, video_player, fixture_sampler, render_loop, FIXTURES_PATH, CONFIG_PATH, SETUPS_PATH)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_web_server.py -v`
Expected: PASS for the first three tests. The fourth (`test_algo_thumbnail_endpoint_returns_204_when_not_rendered`) passes only after the Thumbnail Selector plan lands (its `MagicMock` already stubs `get_thumbnail_jpeg`, but the `/algo_thumbnail/{idx}` route doesn't exist yet on `web_server.py` until that plan adds it — if it fails with 404 at this point, delete that one test for now; it will be re-added by the Thumbnail plan).

Run full suite to confirm nothing else broke: `python3 -m pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add web_server.py main.py tests/test_web_server.py
git commit -m "feat: add save_setup/load_setup websocket messages and fixtures sync on connect"
```

---

## Task 3: Front-end — Setup controls in Fixture Editor and MIDI Routing tabs

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`

**Interfaces:**
- Consumes: `send()`, `state` (global), `fixtures`/`canvasSize` (global), `applyState()` — all existing in `app.js`.
- Produces: `saveSetup(tab)`, `loadSetup(tab)`, `populateSetupSelects(names)` — new global functions in `app.js`.

No automated tests for this task (project has no JS test harness — matches existing convention where `static/app.js` has zero test coverage). Verify manually per Step 3.

- [ ] **Step 1: Add UI controls to `index.html`**

In `#page-fixtures`, after the existing "Save Layout" button block (currently lines 103-105):
```html
  <div style="margin-top:12px">
    <button class="primary" onclick="saveFixtures()">Save Layout</button>
  </div>
```
add immediately after:
```html
  <div style="margin-top:12px;display:flex;gap:8px;align-items:center">
    <input id="setup-name-fixtures" type="text" placeholder="Setup name"
           style="background:#222;border:1px solid #444;color:#eee;padding:4px 6px">
    <button class="primary" onclick="saveSetup('fixtures')">Save Setup</button>
    <select id="setup-select-fixtures" style="background:#222;border:1px solid #444;color:#eee;padding:4px 6px"></select>
    <button onclick="loadSetup('fixtures')">Load Setup</button>
  </div>
```

In `#page-midi`, after the existing Save/Reset button block (currently lines 114-117):
```html
  <div style="margin-top:12px;display:flex;gap:8px">
    <button class="primary" onclick="saveAssignments()">Save</button>
    <button onclick="resetAssignments()">Reset to defaults</button>
  </div>
```
add immediately after:
```html
  <div style="margin-top:12px;display:flex;gap:8px;align-items:center">
    <input id="setup-name-midi" type="text" placeholder="Setup name"
           style="background:#222;border:1px solid #444;color:#eee;padding:4px 6px">
    <button class="primary" onclick="saveSetup('midi')">Save Setup</button>
    <select id="setup-select-midi" style="background:#222;border:1px solid #444;color:#eee;padding:4px 6px"></select>
    <button onclick="loadSetup('midi')">Load Setup</button>
  </div>
```

- [ ] **Step 2: Add JS logic to `app.js`**

Replace the `connect()` function (currently lines 9-13):
```javascript
function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = e => applyState(JSON.parse(e.data));
  ws.onclose = () => setTimeout(connect, 2000);
}
```
with:
```javascript
function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = e => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'fixtures_reload') {
      canvasSize = msg.canvas;
      fixtures = msg.fixtures;
      selectedFixture = null;
      document.getElementById('fixture-form').style.display = 'none';
      document.getElementById('canvas-w').value = canvasSize.width;
      document.getElementById('canvas-h').value = canvasSize.height;
      drawGrid();
    } else {
      applyState(msg);
    }
  };
  ws.onclose = () => setTimeout(connect, 2000);
}
```

In `applyState(s)`, add a call to populate the setup dropdowns. After the line (currently line 44):
```javascript
  buildClips(s.clips||[]);
```
add:
```javascript
  populateSetupSelects(s.setups||[]);
```

At the end of the "MIDI Routing" section (after `resetAssignments()`, currently lines 253-255), add:
```javascript
function saveSetup(tab) {
  const name = document.getElementById('setup-name-'+tab).value.trim();
  if (!name) return;
  send({type:'save_setup', name, canvas: canvasSize, fixtures, assignments: state.assignments||{}});
}

function loadSetup(tab) {
  const sel = document.getElementById('setup-select-'+tab);
  if (!sel.value) return;
  send({type:'load_setup', name: sel.value});
}

function populateSetupSelects(names) {
  ['fixtures','midi'].forEach(tab => {
    const sel = document.getElementById('setup-select-'+tab);
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '';
    names.forEach(n => {
      const opt = document.createElement('option');
      opt.value = n; opt.textContent = n;
      sel.appendChild(opt);
    });
    if (names.includes(current)) sel.value = current;
  });
}
```

- [ ] **Step 3: Manual verification**

Run: `python3 main.py` (from project root), open `http://localhost:8080`.
1. Go to Fixture Editor tab, move/add a strip, type a name in the new "Setup name" field, click "Save Setup" — confirm no JS console errors, and `setups.json` appears in the project root containing that name.
2. Go to MIDI Routing tab — confirm the same setup name now appears in its "Load Setup" dropdown (proves `state.setups` is shared across tabs).
3. Change the fixture layout again (don't save), then select the saved setup from the dropdown and click "Load Setup" — confirm the Fixture Editor grid snaps back to the saved layout.
4. Restart `main.py` — confirm the reloaded layout persisted (since `load_setup` writes `fixtures.json`/`config.yaml` as the active config).

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: add Save/Load Setup controls to Fixture Editor and MIDI Routing tabs"
```
