# Fixture Editor Enhancements, Keyboard Shortcuts, and Preset Save Fix — Design

**Goal:** Three related front-end improvements to `static/index.html` / `static/app.js`:
1. A "Copy Fixture" button in the Fixture Editor.
2. Keyboard shortcuts for moving/reorienting/spawning/deleting/cycling/deselecting the selected fixture.
3. A fix for the broken "Save to selected" preset button (a UI bug, not a backend bug).

**Tech Stack:** Vanilla JS, inline styles — matches the existing `static/app.js` conventions exactly (no framework, global functions/vars, direct DOM manipulation). No backend changes are required for any of the three items; everything here is client-side.

## Background: diagnosis of the preset bug

`preset-btn` buttons currently serve two purposes with one CSS class (`active`):
- Server truth: which preset is currently recalled/playing (`state.active_preset`, driven by MIDI note-triggered recalls in `midi_input.py`).
- Client-only UI: which slot number the user has clicked, to be the target of the next "Save to selected" click (`selectedPreset` in `app.js`).

`applyState(s)` runs on every WebSocket `state` message — which arrives after *every* user action and again every 0.5s from the server's background push loop (`web_server.py`'s `start_push`). It unconditionally re-applies `.active` based on `s.active_preset` for every preset button:

```js
document.querySelectorAll('.preset-btn').forEach((btn,i) => {
  btn.classList.toggle('active', s.active_preset === i);
});
```

Since `active_preset` is `None` unless a MIDI recall happened, this wipes the highlight the user just set by clicking a slot number, within at most 0.5s. The underlying `selectedPreset` JS variable is untouched by this (so a save sent shortly after would still have worked), but the user has no lasting visual confirmation their click registered, and no confirmation a save succeeded — hence "the button doesn't work." The backend `save_preset` handling (`web_server.py:94-95`, `preset_manager.py:save()`) is unaffected and works correctly today.

## 1. Copy Fixture button

**UI:** New button in `#page-fixtures`, next to "Delete Selected" (`static/index.html`, inside the `min-width:220px` column, after the existing `Delete Selected` button):

```html
<button onclick="copyFixture()" style="margin-bottom:16px;width:100%">Copy Fixture</button>
```

**Behavior (`static/app.js`):** New `copyFixture()` function, modeled directly on `addStrip()`:

```js
function copyFixture() {
  if (selectedFixture === null) return;
  const src = fixtures[selectedFixture];
  fixtures.push({...src, name: `strip_${fixtures.length+1}`});
  selectedFixture = fixtures.length - 1;
  showFixtureForm(fixtures[selectedFixture]);
  drawGrid();
}
```

This clones every field of the source fixture (`x`, `y`, `orientation`, `length`, `universe`, `start_channel`) — including orientation, per your decision — and only overrides `name` with a fresh auto-generated one so it doesn't collide with the source's name. The new fixture is selected immediately, matching `addStrip()`'s existing behavior, so it's immediately ready to be repositioned with the new keyboard shortcuts (e.g. nudge it off of the original's exact position). As with every other fixture-editor action, this only changes the in-memory `fixtures` array — "Save Layout" is still required to persist to disk.

## 2. Default orientation for newly spawned fixtures

`addStrip()` currently hardcodes `orientation:'H'`. Change this one line to `orientation:'V'`, so both the "+ Add Strip" button and the new `+` keyboard shortcut (which calls the same function) spawn vertical fixtures by default. `copyFixture()` is unaffected by this default since it copies the source's orientation instead.

## 3. Keyboard shortcuts

A single global `keydown` listener, added once at the bottom of `static/app.js`:

```js
document.addEventListener('keydown', e => {
  if (!document.getElementById('page-fixtures').classList.contains('active')) return;
  if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) return;

  if (e.key === '+') { e.preventDefault(); addStrip(); return; }
  if (e.key === 'Delete') { e.preventDefault(); deleteStrip(); return; }

  if (e.key === 'Tab') {
    e.preventDefault();
    if (fixtures.length === 0) return;
    selectedFixture = selectedFixture === null ? 0 : (selectedFixture + 1) % fixtures.length;
    showFixtureForm(fixtures[selectedFixture]);
    drawGrid();
    return;
  }

  if (e.key === 'Escape') {
    e.preventDefault();
    selectedFixture = null;
    document.getElementById('fixture-form').style.display = 'none';
    drawGrid();
    return;
  }

  if (selectedFixture === null) return;
  const f = fixtures[selectedFixture];
  const step = e.shiftKey ? 10 : 1;

  if (e.key === '#') { e.preventDefault(); f.orientation = f.orientation === 'H' ? 'V' : 'H'; }
  else if (e.key === 'ArrowUp')    { e.preventDefault(); f.y -= step; }
  else if (e.key === 'ArrowDown')  { e.preventDefault(); f.y += step; }
  else if (e.key === 'ArrowLeft')  { e.preventDefault(); f.x -= step; }
  else if (e.key === 'ArrowRight') { e.preventDefault(); f.x += step; }
  else return;

  showFixtureForm(f);
  drawGrid();
});
```

**Guards, and why:**
- **Tab check** (`#page-fixtures.active`) — shortcuts only apply while the Fixture Editor tab is actually visible, so arrow keys don't do something unexpected while on the Main or MIDI Routing tab.
- **Focus check** (not inside `INPUT`/`TEXTAREA`/`SELECT`) — so typing into the Name/X/Y/Universe/Channel fields, or using the Orientation dropdown, isn't hijacked by these shortcuts (e.g. typing "40" into a coordinate field shouldn't nudge the fixture via arrow-key autocomplete navigation, and `#` should still be typeable in the Name field).
- **`+` and Delete** work with no fixture selected (spawning doesn't need one; deleting with nothing selected is a no-op already, matching `deleteStrip()`'s existing guard).
- **`Tab`** cycles through `fixtures` in array order: selects the first fixture if none is currently selected, otherwise advances to the next index, wrapping back to 0 after the last one. `preventDefault()` stops the browser's normal focus-cycling behavior so it doesn't jump focus to the next button/input instead. No-ops if there are zero fixtures.
- **`Escape`** clears the current selection (`selectedFixture = null`) and hides the fixture form, regardless of whether anything was selected — there's currently no click-to-deselect, so this is the only way to deselect without picking another fixture via click or Tab.
- **Arrow keys and `#`** require a selection (`selectedFixture !== null`) since they act on the selected fixture.
- Nudge step is **1px, or 10px with Shift held**, per your choice.

No backend/data-format changes — this only mutates the same in-memory `fixtures` array the mouse-driven editor already mutates, so "Save Layout" persists it exactly as today.

## 4. Preset selection/save fix

**Separate the two concepts with two CSS classes** (`static/style.css`):

```css
.preset-btn.selected { border-color: #0af; }
```

(`.preset-btn.active` — solid blue background — stays reserved for "currently recalled via MIDI," unchanged.)

**`static/app.js` changes:**

- `buildPresets()`'s click handler and `updatePresetUI()` toggle `.selected` (not `.active`) based on `selectedPreset`.
- `applyState(s)`'s preset loop keeps toggling `.active` only, from `s.active_preset` — untouched, still reflects MIDI-driven recall state. Since it no longer touches `.selected`, the user's save-target choice now survives every broadcast.
- `savePreset()` additionally flashes the "Save to selected" button on send, as an optimistic confirmation (fire-and-forget, consistent with every other save action in this app — none of them have a server ack today):

```js
function savePreset() {
  if (selectedPreset === null) return;
  send({type:'save_preset', slot: selectedPreset});
  const btn = document.querySelector('#page-main button.primary[onclick="savePreset()"]');
  btn.textContent = 'Saved!';
  btn.classList.add('save-flash');
  setTimeout(() => { btn.textContent = 'Save to selected'; btn.classList.remove('save-flash'); }, 1000);
}
```

```css
.save-flash { background: #0f0 !important; color: #000; }
```

## Testing

No backend changes, and this project has zero automated JS test coverage by existing convention (matches every prior front-end-only task in this codebase, e.g. the Thumbnail Selector's Task 3). Verification will be manual: run the app, exercise Copy Fixture, each keyboard shortcut (arrows, `#`, `+`, Delete, Tab, Escape — including confirming they don't fire while a text field has focus or another tab is active, and that Tab wraps around correctly and Escape deselects), and the preset select→save flow (confirm the highlight survives past 0.5s and the flash appears).
