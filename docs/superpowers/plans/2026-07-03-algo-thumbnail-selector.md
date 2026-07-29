# Algorithm Thumbnail Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the continuous "Algorithm" fader with a grid of clickable thumbnail buttons — one per generator algorithm, live-updating to reflect current fader values, staggered so all thumbnails aren't rendered on the same tick.

**Architecture:** `Generator` gains a `render_index(idx, ...)` method (existing `render()` becomes a thin wrapper around it) so a specific algorithm can be rendered without going through the fader-0 selection logic, using its own isolated state buffer. `RenderLoop`'s existing background thread renders one thumbnail per tick on a round-robin schedule (full cycle = 5s ÷ algorithm count), caches each as JPEG, served at `/algo_thumbnail/{idx}` (mirrors the existing `/preview` endpoint). The client replaces the "Algorithm" fader column with an `<img>` grid that polls each thumbnail and posts `set_fader` on click.

**Tech Stack:** Python (numpy, OpenCV), vanilla JS, pytest.

**Recommended order:** Run after the Named Setups plan (`2026-07-03-named-setups.md`) — that plan's `tests/test_web_server.py` harness already stubs `render_loop.get_thumbnail_jpeg`, and its skipped `test_algo_thumbnail_endpoint_returns_204_when_not_rendered` test should be re-added once this plan's endpoint exists (Task 2, Step 1 below does this).

## Global Constraints

- Thumbnail resolution: 48×24 (small enough that per-tick render cost is negligible at 30fps).
- Refresh cycle: 5 seconds total, divided evenly across however many algorithms exist (`len(_ALGOS)`) so renders are staggered, not bursted.
- Each algorithm's state buffer for thumbnail rendering must be isolated per algorithm index — never shared with the main render loop's buffer or another algorithm's thumbnail buffer (stateful algorithms like `fire`/`stars` re-initialize their buffer whenever the requested canvas shape changes, so sharing one buffer across different resolutions/algorithms causes constant flicker/reset).

---

## Task 1: `generator.py` — extract `render_index()` with isolated buffers

**Files:**
- Modify: `generator.py`
- Test: Modify `tests/test_generator.py`

**Interfaces:**
- Produces: `Generator.render_index(idx: int, H: int, W: int, faders: list[float], t: float, beat: float, buf: dict) -> np.ndarray`, `Generator.algo_count() -> int`. `Generator.render()` keeps its existing signature/behavior unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generator.py` (it currently imports `from generator import Generator`; add `_ALGOS` and `_algo_fire` to that import):
```python
from generator import Generator, _ALGOS, _algo_fire
```

Append:
```python
def test_algo_count_matches_algos_list():
    g = Generator()
    assert g.algo_count() == len(_ALGOS)

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
```

Also update the existing `test_render_all_algorithms` test (currently hardcodes `range(6)`, which will silently under-test once more algorithms exist):
```python
def test_render_all_algorithms():
    g = Generator()
    for algo_idx in range(len(_ALGOS)):
        faders = [0.5]*12
        faders[0] = algo_idx / len(_ALGOS)
        frame = g.render(20, 40, faders, 1.0, 0.0)
        assert frame.shape == (20, 40, 3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_generator.py -v`
Expected: FAIL — `AttributeError: 'Generator' object has no attribute 'render_index'` (and `algo_count`).

- [ ] **Step 3: Implement**

In `generator.py`, replace the `Generator` class (currently lines 148-174):
```python
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
with:
```python
_STATEFUL_ALGOS = (_algo_fire, _algo_stars)

def _build_params(faders: list[float]) -> dict:
    return {
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

class Generator:
    def __init__(self):
        self._buf: dict = {}

    def algo_count(self) -> int:
        return len(_ALGOS)

    def render_index(self, idx: int, H: int, W: int, faders: list[float],
                      t: float, beat: float, buf: dict) -> np.ndarray:
        p = _build_params(faders)
        algo = _ALGOS[idx]
        if algo in _STATEFUL_ALGOS:
            frame = algo(H, W, p, t, beat, buf)
        else:
            frame = algo(H, W, p, t, beat)
        frame = _apply_symmetry(frame, p['symmetry'])
        frame = _apply_blur(frame, p['blur_glow'])
        return frame

    def render(self, H: int, W: int, faders: list[float], t: float, beat: float) -> np.ndarray:
        algo_idx = min(int(faders[0] * len(_ALGOS)), len(_ALGOS) - 1)
        return self.render_index(algo_idx, H, W, faders, t, beat, self._buf)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_generator.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add generator.py tests/test_generator.py
git commit -m "refactor: extract Generator.render_index with isolated state buffers"
```

---

## Task 2: `render_loop.py` + `web_server.py` — staggered thumbnail rendering

**Files:**
- Modify: `render_loop.py`
- Modify: `web_server.py`
- Test: Modify `tests/test_render_loop.py`; modify `tests/test_web_server.py` (re-add the skipped 204 test from the Named Setups plan, plus a 200 test)

**Interfaces:**
- Consumes: `Generator.render_index`, `Generator.algo_count` from Task 1.
- Produces: `RenderLoop.get_thumbnail_jpeg(idx: int) -> bytes | None`. `GET /algo_thumbnail/{idx}` endpoint returning JPEG or 204.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render_loop.py`:
```python
def test_thumbnail_jpeg_populates_quickly():
    loop, _, _, _ = _make_loop()
    loop.start()
    time.sleep(0.2)
    loop.stop()
    assert loop.get_thumbnail_jpeg(0) is not None

def test_thumbnail_jpeg_missing_index_returns_none():
    loop, _, _, _ = _make_loop()
    assert loop.get_thumbnail_jpeg(999) is None
```

In `tests/test_web_server.py`, ensure this test exists (it was written but noted as skippable in the Named Setups plan — add it now if not already present):
```python
def test_algo_thumbnail_endpoint_returns_204_when_not_rendered(tmp_path):
    client, *_ = _make_client(tmp_path)
    resp = client.get('/algo_thumbnail/0')
    assert resp.status_code == 204
```
and add:
```python
def test_algo_thumbnail_endpoint_returns_jpeg(tmp_path):
    client, fixture_sampler, fixtures_path, config_path, setups_path = _make_client(tmp_path)
    # _make_client's render_loop is a MagicMock; override get_thumbnail_jpeg for idx 0
    # Re-create the client with a render_loop mock that returns bytes for idx 0:
    from unittest.mock import MagicMock
    from state import AppState
    from web_server import create_app
    state = AppState()
    preset_manager = MagicMock()
    video_player = MagicMock()
    video_player.scan_clips.return_value = [None] * 64
    fixture_sampler = MagicMock()
    render_loop = MagicMock()
    render_loop.get_preview_jpeg.return_value = None
    render_loop.get_thumbnail_jpeg.side_effect = lambda idx: b'\xff\xd8\xff' if idx == 0 else None
    app = create_app(state, preset_manager, video_player, fixture_sampler,
                      render_loop, fixtures_path, config_path, setups_path)
    resp = TestClient(app).get('/algo_thumbnail/0')
    assert resp.status_code == 200
    assert resp.headers['content-type'] == 'image/jpeg'
    assert resp.content == b'\xff\xd8\xff'
```

Note: `_make_client` in `tests/test_web_server.py` was defined in the Named Setups plan with `render_loop = MagicMock()` and `render_loop.get_thumbnail_jpeg.return_value = None` already set — the 204 test above reuses that fixture directly; the 200 test builds its own app with a different mock so it doesn't need to modify the shared fixture.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_render_loop.py tests/test_web_server.py -v`
Expected: FAIL — `AttributeError: 'RenderLoop' object has no attribute 'get_thumbnail_jpeg'` and 404 on `/algo_thumbnail/0`.

- [ ] **Step 3: Implement**

In `render_loop.py`, add module constants after `FPS = 30` (currently line 14):
```python
THUMB_H, THUMB_W = 24, 48
THUMB_CYCLE_SECONDS = 5.0
```

In `RenderLoop.__init__`, after `self._preview_counter = 0` (currently line 35), add:
```python
        self._thumb_jpegs: dict[int, bytes] = {}
        self._thumb_lock = threading.Lock()
        self._thumb_bufs: dict[int, dict] = {}
        self._thumb_counter = 0
```

After the `get_preview_jpeg` method (currently lines 42-44), add:
```python
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
```

In `_loop`, after the existing preview block (currently lines 90-98):
```python
            self._preview_counter += 1
            if self._preview_counter % 3 == 0:  # ~10fps preview
                import cv2
                small = cv2.resize(frame, (400, 400 * H // W),
                                   interpolation=cv2.INTER_NEAREST)
                rgb = cv2.cvtColor(small, cv2.COLOR_RGB2BGR)
                _, buf = cv2.imencode('.jpg', rgb, [cv2.IMWRITE_JPEG_QUALITY, 75])
                with self._preview_lock:
                    self._preview_jpeg = buf.tobytes()
```
add:
```python

            n_algos = self._gen.algo_count()
            cycle_frames = int(THUMB_CYCLE_SECONDS * FPS)
            slot_size = max(1, cycle_frames // n_algos)
            if self._thumb_counter % slot_size == 0:
                algo_idx = (self._thumb_counter // slot_size) % n_algos
                self._render_thumbnail(algo_idx, faders, t, beat)
            self._thumb_counter += 1
```

In `web_server.py`, add a new endpoint right after the existing `/preview` route (currently lines 127-132):
```python
    @app.get('/preview')
    async def preview():
        jpeg = render_loop.get_preview_jpeg()
        if jpeg is None:
            return Response(status_code=204)
        return Response(content=jpeg, media_type='image/jpeg')
```
add:
```python

    @app.get('/algo_thumbnail/{idx}')
    async def algo_thumbnail(idx: int):
        jpeg = render_loop.get_thumbnail_jpeg(idx)
        if jpeg is None:
            return Response(status_code=204)
        return Response(content=jpeg, media_type='image/jpeg')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_render_loop.py tests/test_web_server.py -v`
Expected: All PASS.

Run full suite: `python3 -m pytest -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add render_loop.py web_server.py tests/test_render_loop.py tests/test_web_server.py
git commit -m "feat: staggered algorithm thumbnail rendering and /algo_thumbnail endpoint"
```

---

## Task 3: Front-end — thumbnail button grid replaces the Algorithm fader

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`

No automated tests (no JS harness in this project). Verify manually per Step 3.

- [ ] **Step 1: Add a container in `index.html`**

Before the "Generator Faders" heading (currently lines 38-39):
```html
  <h3 style="color:#666;font-size:11px;text-transform:uppercase;margin-bottom:8px">Generator Faders</h3>
  <div id="faders"></div>
```
add, right before it:
```html
  <h3 style="color:#666;font-size:11px;text-transform:uppercase;margin-bottom:8px">Algorithm</h3>
  <div id="algo-thumbs" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px"></div>
```

- [ ] **Step 2: Update `app.js`**

Change `buildFaders` (currently lines 62-74) to skip index 0:
```javascript
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
```
to:
```javascript
function buildFaders(container) {
  container.innerHTML = '';
  FADER_NAMES.forEach((name, i) => {
    if (i === 0) return;  // algorithm select now lives in the thumbnail grid
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
```

In `applyState(s)`, after the block that builds/updates faders (currently lines 33-38):
```javascript
  const fc = document.getElementById('faders');
  if (!fc.children.length) buildFaders(fc);
  (s.faders||[]).forEach((v,i) => {
    const el = document.getElementById('fader-'+i);
    if (el) el.value = Math.round(v*127);
  });
```
add:
```javascript

  buildAlgoThumbnails();
  const algoCount = document.getElementById('algo-thumbs').children.length;
  const activeAlgoIdx = Math.min(Math.floor((s.faders?.[0]||0) * algoCount), algoCount - 1);
  document.querySelectorAll('.algo-thumb').forEach((el, i) => {
    el.classList.toggle('active', i === activeAlgoIdx);
  });
```

Add new functions near `buildFaders` (after its closing brace):
```javascript
const ALGO_COUNT_GUESS = 16;  // upper bound; thumbnails beyond the real count just 204 forever and are skipped

function buildAlgoThumbnails() {
  const c = document.getElementById('algo-thumbs');
  if (c.children.length) return;
  for (let i = 0; i < ALGO_COUNT_GUESS; i++) {
    const img = document.createElement('img');
    img.className = 'algo-thumb';
    img.dataset.idx = i;
    img.style = 'width:64px;height:32px;object-fit:cover;border:1px solid #444;cursor:pointer;background:#111';
    img.onerror = () => { img.style.display = 'none'; };
    img.onload = () => { img.style.display = ''; };
    img.onclick = () => {
      const count = document.getElementById('algo-thumbs').children.length;
      send({type:'set_fader', index:0, value:(i+0.5)/count});
    };
    c.appendChild(img);
  }
  setInterval(() => {
    document.querySelectorAll('.algo-thumb').forEach(img => {
      img.src = `/algo_thumbnail/${img.dataset.idx}?` + Date.now();
    });
  }, 2000);
}
```

Add a CSS-less "active" visual cue by adding this rule to `static/style.css` (append at end of file):
```css
.algo-thumb.active { outline: 2px solid #0af; }
```

- [ ] **Step 3: Manual verification**

Run: `python3 main.py`, open `http://localhost:8080`.
1. Confirm the "Algorithm" section shows a row of thumbnail images above "Generator Faders" (some may be blank/hidden initially — they fill in over the first 5s cycle).
2. Click a thumbnail — confirm the live `/preview` at the top of the page switches to that algorithm, and the clicked thumbnail gets a blue outline.
3. Move the "Hue" or "Speed" fader — confirm thumbnails visibly change color/motion within a few seconds (they reflect live fader values).
4. Confirm there's no "Algorithm" slider left in the fader row (only 11 sliders remain: Beat React through Blur/Glow).

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/app.js static/style.css
git commit -m "feat: replace Algorithm fader with live thumbnail button grid"
```
