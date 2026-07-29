# Generator Expansion, Thumbnail Selector & Named Setups — Design Spec
**Date:** 2026-07-03

## Overview

Three additions to the existing MIDI ArtNet Lightshow Controller (see `2026-06-26-midi-artnet-lightshow-design.md`):

1. **10 new generator algorithms**, authored by two independent AI agents for comparison, focused on simple, bold, LED-strip-friendly visuals (the existing 6 algorithms lean toward screen-style noise/plasma patterns that lose detail on sparse 40px strips).
2. **Algorithm thumbnail selector** — replaces the continuous "Algorithm" fader with a grid of live-updating thumbnail buttons, one per algorithm.
3. **Named Setups** — save/load bundles of MIDI mapping + fixture layout (including ArtNet addresses), so different physical rigs or shows can be switched between.

---

## 1. New Generator Algorithms

### Interface contract (unchanged, must be followed exactly)

```python
def _algo_name(H, W, p, t, beat) -> np.ndarray:      # stateless
def _algo_name(H, W, p, t, beat, buf) -> np.ndarray:  # stateful (needs buf dict for persistence across frames)
```

- Returns an `H x W x 3` `uint8` RGB array.
- `p` is a dict with keys: `beat_react, rhythm_density, speed, hue, saturation, color_spread, scale, direction, symmetry, contrast, blur_glow` — all floats 0.0–1.0. Algorithms may use whichever subset makes sense; unused keys are ignored.
- `t` — elapsed seconds (float, monotonic). `beat` — 0.0–1.0 pulse value on beat.
- Existing algorithms for reference/non-duplication: `plasma, fire, noise, bars, radial, stars` (`generator.py`).

### Visual constraint

Output is sampled onto **16 LED strips × 40 pixels**, sparsely arranged on a virtual canvas (see `fixtures.json`) — not viewed as a dense screen. Fine noise/texture and complex multi-color gradients get lost. New algorithms must favor **bold, high-contrast, 1–2 color patterns**: e.g. a moving line/bar, a pulsing or growing circle, a chase, a wipe, a breathing fade.

### Authoring process

- Two `general-purpose` agents are dispatched in parallel, **model `fable`** and **model `opus`**, with the **identical prompt** (no mention of the other agent, no assigned slot numbers — that framing would break "identical prompt" and isn't needed by either agent to do its job).
- Each agent independently web-searches for simple LED/VJ visual pattern inspiration and returns **5 complete, runnable Python functions** matching the interface above, as plain text (agents do not edit files directly).
- After both return, the two sets of 5 are reviewed together, shown side by side, and integrated into `generator.py` by appending to `_ALGOS` (final ordering/slot numbers decided at integration time, not by the agents).
- `FADER_NAMES[0]` stays `'Algorithm'` conceptually; the algorithm count `len(_ALGOS)` grows from 6 to 16 and `Generator.render()`'s `algo_idx = min(int(faders[0] * len(_ALGOS)), len(_ALGOS) - 1)` logic requires no change — it already scales with `len(_ALGOS)`.

---

## 2. Algorithm Thumbnail Selector

Replaces the current "Algorithm" continuous-fader column (index 0 of `FADER_NAMES`/`CC_NUMS`) with a grid of clickable thumbnail images, one per algorithm (16 total after part 1).

### Rendering

- Reuses the existing `RenderLoop` background thread (same thread that already produces the `/preview` JPEG at ~10fps) — no new thread.
- One thumbnail is (re-)rendered per tick, on a schedule: a full refresh cycle is 5 seconds, divided into `N` (=16) slots; algorithm `i` renders on tick where `frame_counter % (5s in frames) == i * (5s in frames // N)`. This spreads the 16 renders evenly across the 5s window instead of bursting all at once.
- Each thumbnail render uses the **current live fader values** (`p` dict from current `state.faders[1:]`, current `t`/`beat`) — so a thumbnail shows what that algorithm actually looks like right now, not a fixed default.
- Rendered at low resolution (~48×24) to keep the extra per-tick cost negligible, encoded as JPEG, cached in memory keyed by algorithm index (same lock pattern as the existing `_preview_jpeg`).

### API & UI

- New endpoint `GET /algo_thumbnail/{idx}` — returns cached JPEG for that algorithm index (204 if not yet rendered), mirroring the existing `/preview` endpoint.
- `static/index.html`: the "Algorithm" fader column is removed from the generated fader grid; a new thumbnail grid section is added above/beside the remaining 11 faders.
- `static/app.js`: `buildFaders()` skips index 0; new `buildAlgoThumbnails(count)` renders `count` `<img>` buttons, each polling its own `/algo_thumbnail/{i}` every 2000ms (cache-busting query string, same approach as `/preview`'s 100ms poll — thumbnails poll far less often since each one is only re-rendered every 5s). Click handler sends `{type:'set_fader', index:0, value:(i+0.5)/count}`.

---

## 3. Named Setups (MIDI mapping + fixture layout + ArtNet addresses)

A "setup" is a named snapshot bundling:
- **MIDI assignments** (currently in `config.yaml` → `midi.assignments`)
- **Fixture layout** (currently in `fixtures.json`: canvas size + fixture list with position, orientation, universe, start_channel)

### Storage

New file `setups.json`:
```json
{
  "setup name": {
    "assignments": { "...": "..." },
    "fixtures": { "canvas": {"width":200,"height":100}, "fixtures": [ /* ... */ ] }
  }
}
```

### Behavior

- **Save Setup `{name}`**: takes whatever is currently staged in the Fixture Editor (`fixtures`/`canvasSize` client state) and MIDI Routing tab (`localAssignments`), commits them as the active config exactly as today's individual "Save Layout" and "Save" actions do (writes `fixtures.json` and `config.yaml`), and additionally stores that combined snapshot under `name` in `setups.json`. Overwrites if `name` already exists.
- **Load Setup `{name}`**: reads the named bundle from `setups.json`, writes it as the new active `fixtures.json` + `config.yaml`, updates live server state (`fixture_sampler.set_fixtures(...)`, `state.update(assignments=...)`), and broadcasts full state so both the Fixture Editor grid and MIDI Routing table refresh to match.
- No delete/rename in this pass (YAGNI — not requested; overwrite-by-save-with-same-name covers the practical need).

### New WebSocket message types

- `save_setup {name}` 
- `load_setup {name}`

`state.snapshot()` gains a `setups` key (list of saved names) so the UI can populate the dropdown without a separate HTTP round trip.

### UI

Controls are **duplicated** in both the Fixture Editor tab and the MIDI Routing tab (per user preference — work from whichever tab you're already in):
- A text input for setup name + "Save Setup" button.
- A `<select>` populated from `state.setups` + "Load Setup" button.

Both instances read/write the same underlying `state.setups` list, so saving from one tab immediately shows up in the other's dropdown on the next state broadcast.

---

## Testing

- New algorithms: manually preview via the thumbnail grid and the live `/preview` after integration; no unit tests planned (matches project's existing lack of automated tests for visual algorithms).
- Thumbnail scheduler: verify via `/debug`-style manual check that all 16 thumbnails populate within one 5s cycle and CPU stays acceptable (spot-check, no formal perf test).
- Setups save/load: manual round-trip test — save a setup, change fixtures/mapping, load the setup back, confirm both fixture layout and MIDI table revert correctly, and confirm `setups.json`/`fixtures.json`/`config.yaml` on disk match expectations.
