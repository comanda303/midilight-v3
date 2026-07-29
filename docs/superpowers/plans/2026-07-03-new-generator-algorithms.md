# New Generator Algorithms (Dual-Agent Authored) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 10 new simple, bold, LED-strip-friendly generator algorithms to `generator.py`, authored by two independently dispatched AI agents (5 each) for direct comparison, then integrated and tested.

**Architecture:** Two `general-purpose` agents (`model: fable`, `model: opus`) receive the *identical* prompt (no mention of each other, no assigned slot numbers) asking for 5 algorithms each, matching the existing `_algo_name(H, W, p, t, beat[, buf])` interface. Both return code as text (they do not edit files). The 10 functions are then reviewed, deduplicated if needed, and appended to `generator.py`'s `_ALGOS` list.

**Tech Stack:** Python (numpy, optionally OpenCV for blur — matches existing algorithms), pytest.

**Recommended order:** Run after the Algorithm Thumbnail Selector plan (`2026-07-03-algo-thumbnail-selector.md`) — that plan introduces the `_STATEFUL_ALGOS` tuple and `_build_params` helper that Task 2 below extends. If that plan hasn't run yet, Task 2's Step 3 has a fallback noted inline.

## Global Constraints

- Every new function must match the interface exactly: `def _algo_name(H, W, p, t, beat)` (stateless) or `def _algo_name(H, W, p, t, beat, buf)` (stateful), returning an `H x W x 3` `uint8` numpy array.
- Visual constraint: output is sampled onto 16 sparse 40px LED strips, not a dense screen — favor bold, high-contrast, 1–2 color patterns (moving line/bar, pulsing/growing circle, chase, wipe, breathing fade). Explicitly avoid fine noise/texture, which is the weakness of several existing algorithms (plasma, noise) on real strips.
- Existing algorithms to not duplicate: `plasma, fire, noise, bars, radial, stars`.
- Agents do not edit any files — they return Python code as text for manual integration and side-by-side comparison.

---

## Task 1: Dispatch the two research/authoring agents

**Files:** None (no code changes — this task produces text output to be used in Task 2).

**Interfaces:**
- Produces: two blocks of 5 Python functions each (returned as agent output, to be manually reviewed before Task 2).

- [ ] **Step 1: Send the identical prompt to both agents in parallel, in the background**

Use the Agent tool twice, in the same message (parallel), both with `subagent_type: general-purpose`, `run_in_background: true`, and this exact prompt text for both (only the `model` field differs — `fable` for one call, `opus` for the other):

```
You're designing simple procedural visual algorithms for a real-time LED lightshow. The output is NOT a screen -- it's sampled onto 16 physical LED strips of 40 pixels each, sparsely arranged on a virtual canvas, so fine detail, noise, and complex gradients are invisible or muddy. Favor bold, high-contrast, 1-2 color patterns: e.g. a single moving line/bar, a pulsing or growing/shrinking circle, a chase, a wipe, a breathing fade, sparkle bursts.

Research (web search) simple LED/VJ visual pattern ideas for inspiration, then design and implement 5 new algorithms as Python functions.

Each function must match this interface exactly:

    def _algo_name(H, W, p, t, beat):
        ...
        return frame  # H x W x 3 numpy uint8 array, values 0-255

    # OR, if the algorithm needs to persist state between frames (e.g. a moving position):
    def _algo_name(H, W, p, t, beat, buf):
        if 'unique_key' not in buf:
            buf['unique_key'] = initial_value
        ...
        return frame

- H, W: canvas height/width in pixels (ints).
- p: dict of floats 0.0-1.0 with these keys (use whichever are relevant to your algorithm, ignore the rest): beat_react, rhythm_density, speed, hue, saturation, color_spread, scale, direction, symmetry, contrast, blur_glow.
- t: elapsed seconds (float, monotonically increasing).
- beat: 0.0 or 1.0 -- a one-frame pulse on each detected musical beat.
- buf: a plain dict, private to your algorithm, for storing state across frames (e.g. position, velocity). Use a unique key name so it never collides with any other algorithm's state.
- Return an H x W x 3 numpy array, dtype uint8, RGB order.

Existing algorithms already implemented (do not duplicate these ideas): plasma (layered sine-wave color field), fire (simulated flame rising from the bottom edge), noise (directional layered sine noise), bars (moving horizontal/vertical color bars), radial (expanding rings from center), stars (starfield flying toward viewer).

For each of your 5 algorithms, provide:
1. The complete Python function code (ready to paste into a module using `numpy as np`; a `_hsv_to_rgb(h, s, v)` helper already exists and converts arrays of hue/saturation/value in 0-1 range to an RGB uint8 array -- you may call it, with h/s/v as same-shaped numpy arrays).
2. A short (2-4 word) display name for a UI thumbnail label.
3. One sentence describing the visual.

Do not edit any files. Return only the 5 functions with their names/descriptions in your final message -- no other commentary.
```

Give each Agent call a `description` like "LED algorithm design (fable)" / "LED algorithm design (opus)" respectively.

- [ ] **Step 2: Wait for both to complete, review side by side**

When both background agents finish, read both sets of 5. Check each function against the constraints above (matches interface exactly, returns correct shape/dtype conceptually, uses bold/simple visuals not fine noise, no name collisions with existing `_algo_*` functions or between the two sets — rename if needed, e.g. suffix `_v2`). Present both sets to the user for comparison before proceeding to Task 2, since the user explicitly wants to compare fable's vs opus's output.

---

## Task 2: Integrate the 10 algorithms into `generator.py`

**Files:**
- Modify: `generator.py`
- Test: Modify `tests/test_generator.py`

**Interfaces:**
- Consumes: the 10 reviewed functions from Task 1.
- Produces: `_ALGOS` grows from 6 to 16 entries; `Generator.algo_count()` (if the Thumbnail Selector plan has landed) or `len(_ALGOS)` (if not) reflects 16 automatically — no other code changes needed for callers, since all existing logic already scales with `len(_ALGOS)`.

- [ ] **Step 1: Write/update the failing test**

`tests/test_generator.py`'s `test_render_all_algorithms` (added/updated by the Thumbnail Selector plan, or still using a hardcoded `range(6)` if that plan hasn't run) must iterate `len(_ALGOS)`, not a fixed number, so it automatically covers the new algorithms:
```python
def test_render_all_algorithms():
    g = Generator()
    for algo_idx in range(len(_ALGOS)):
        faders = [0.5]*12
        faders[0] = algo_idx / len(_ALGOS)
        frame = g.render(20, 40, faders, 1.0, 0.0)
        assert frame.shape == (20, 40, 3)
```
(If `_ALGOS` isn't already imported in the test file, add it: `from generator import Generator, _ALGOS`.)

Add one test asserting the new count explicitly, to catch integration mistakes (e.g. forgetting to append one):
```python
def test_algo_count_is_sixteen_after_expansion():
    assert len(_ALGOS) == 16
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_generator.py -v`
Expected: FAIL on `test_algo_count_is_sixteen_after_expansion` (still 6) — the other test passes trivially either way since it iterates dynamically, so it isn't a useful failing-test signal by itself; the count test is what drives this task.

- [ ] **Step 3: Implement**

Append the 10 reviewed functions from Task 1 to `generator.py`, before the `_ALGOS = [...]` line (currently line 146). Each function follows the pattern of the existing ones (e.g. `_algo_plasma`, lines 35-49). Rename any of the 10 that collide with each other or with existing names.

Update the `_ALGOS` list (currently line 146):
```python
_ALGOS = [_algo_plasma, _algo_fire, _algo_noise, _algo_bars, _algo_radial, _algo_stars]
```
to include all 16, e.g.:
```python
_ALGOS = [_algo_plasma, _algo_fire, _algo_noise, _algo_bars, _algo_radial, _algo_stars,
          _algo_<new_1>, _algo_<new_2>, _algo_<new_3>, _algo_<new_4>, _algo_<new_5>,
          _algo_<new_6>, _algo_<new_7>, _algo_<new_8>, _algo_<new_9>, _algo_<new_10>]
```

If any of the 10 new functions are stateful (take a `buf` parameter), add them to `_STATEFUL_ALGOS` (introduced by the Thumbnail Selector plan; if that plan hasn't landed yet, add them instead to the inline check in `Generator.render()`: `if algo in (_algo_fire, _algo_stars, _algo_<new_stateful_1>, ...):`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_generator.py -v`
Expected: All PASS, including `test_algo_count_is_sixteen_after_expansion`.

Run full suite: `python3 -m pytest -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add generator.py tests/test_generator.py
git commit -m "feat: add 10 new LED-friendly generator algorithms (fable + opus authored)"
```

- [ ] **Step 6: Manual verification**

Run: `python3 main.py`, open `http://localhost:8080`. Click through the algorithm thumbnails (if the Thumbnail Selector plan has landed) or drag the Algorithm fader across its full range, confirming all 16 algorithms render distinct, bold visuals with no crashes.
