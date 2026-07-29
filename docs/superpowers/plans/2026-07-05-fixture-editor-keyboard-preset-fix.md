# Fixture Editor Copy/Keyboard Shortcuts and Preset Save Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Copy Fixture" button and keyboard shortcuts (move/reorient/spawn/delete/cycle/deselect) to the Fixture Editor, default new fixtures to vertical orientation, and fix the "Save to selected" preset button so its slot selection actually persists and gives visible save confirmation.

**Architecture:** All three changes are client-side only (`static/index.html`, `static/app.js`, `static/style.css`) — no backend/data-format changes. They extend the existing vanilla-JS, global-function/global-variable style already used throughout `app.js`, with no new abstractions.

**Tech Stack:** Vanilla JS, inline styles, plain CSS classes — matches existing project conventions exactly.

## Global Constraints

- No framework, no classes/modules — global functions and global variables only, matching every existing function in `static/app.js`.
- No backend changes — every change here only touches the in-memory `fixtures`/`canvasSize`/`selectedFixture`/`selectedPreset` client state already used by the existing editor; persistence still goes through the existing `saveFixtures()`/`save_preset` message flows, unchanged.
- No automated JS test harness exists in this project (matches every prior front-end-only task, e.g. the Algorithm Thumbnail Selector's Task 3) — verification for every task here is manual, via running the app.
- Keyboard shortcuts must not fire while focus is inside an `INPUT`, `TEXTAREA`, or `SELECT` element, and must not fire outside the Fixture Editor tab.
- Fixture nudge step: 1px per arrow-key press, 10px with Shift held.
- New fixtures (via "+ Add Strip" or the `+` keyboard shortcut) default to `orientation: 'V'`. "Copy Fixture" instead copies the source fixture's orientation.

---

## Task 1: Copy Fixture button + default vertical orientation

**Files:**
- Modify: `static/index.html:93` (add button)
- Modify: `static/app.js:226-232` (change `addStrip()`'s default orientation, add `copyFixture()`)

**Interfaces:**
- Produces: `copyFixture()` — new global function, callable from an `onclick` handler, no arguments, no return value. Reads `selectedFixture`/`fixtures` (existing globals), mutates `fixtures` and `selectedFixture` (existing globals), calls existing `showFixtureForm(f)` and `drawGrid()`.

- [ ] **Step 1: Add the "Copy Fixture" button to `index.html`**

In `static/index.html`, the fixture-editor button column currently reads (lines 91-93):
```html
    <div style="min-width:220px">
      <button class="primary" onclick="addStrip()" style="margin-bottom:8px;width:100%">+ Add Strip</button>
      <button class="danger" onclick="deleteStrip()" style="margin-bottom:16px;width:100%">Delete Selected</button>
```
Change it to:
```html
    <div style="min-width:220px">
      <button class="primary" onclick="addStrip()" style="margin-bottom:8px;width:100%">+ Add Strip</button>
      <button onclick="copyFixture()" style="margin-bottom:8px;width:100%">Copy Fixture</button>
      <button class="danger" onclick="deleteStrip()" style="margin-bottom:16px;width:100%">Delete Selected</button>
```

- [ ] **Step 2: Change `addStrip()`'s default orientation to vertical**

In `static/app.js`, `addStrip()` currently reads (lines 226-232):
```js
function addStrip() {
  fixtures.push({name: `strip_${fixtures.length+1}`, x:0, y:0,
                 orientation:'H', length:40, universe:0, start_channel:0});
  selectedFixture = fixtures.length - 1;
  showFixtureForm(fixtures[selectedFixture]);
  drawGrid();
}
```
Change `orientation:'H'` to `orientation:'V'`:
```js
function addStrip() {
  fixtures.push({name: `strip_${fixtures.length+1}`, x:0, y:0,
                 orientation:'V', length:40, universe:0, start_channel:0});
  selectedFixture = fixtures.length - 1;
  showFixtureForm(fixtures[selectedFixture]);
  drawGrid();
}
```

- [ ] **Step 3: Add `copyFixture()` right after `addStrip()`**

Insert immediately after the `addStrip()` function (still before `deleteStrip()`):
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

- [ ] **Step 4: Manual verification**

Run: `python3 main.py` (from project root), open `http://localhost:8080`, go to the Fixture Editor tab.
1. Click "+ Add Strip" — confirm the new fixture appears vertical (a tall thin rectangle, not wide/short) on the canvas and in the form's Orient dropdown (should show "Vertical").
2. Click an existing fixture to select it, note its X/Y/Orient/Universe/Start CH in the form, then click "Copy Fixture" — confirm a new fixture appears at the *same* X/Y position with the *same* orientation, universe, and start channel as the source, and that it's auto-selected (form updates to show the new fixture's auto-generated name, same coordinates/address as the source).
3. Click "Copy Fixture" with nothing selected (deselect first by reloading the page, or by implementing Task 2's Escape first if done out of order) — confirm nothing happens (no new fixture, no console error).

- [ ] **Step 5: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: add Copy Fixture button, default new fixtures to vertical orientation"
```

---

## Task 2: Keyboard shortcuts for the Fixture Editor

**Files:**
- Modify: `static/app.js` (add a new `keydown` listener; insert after the `saveFixtures()` function, before the `// ── MIDI Routing ──` section comment, i.e. after line 269 in the current file)

**Interfaces:**
- Consumes: `selectedFixture`, `fixtures` (existing globals), `addStrip()`, `deleteStrip()`, `showFixtureForm(f)`, `drawGrid()` (existing functions, including `addStrip()` as modified by Task 1).
- Produces: no new named functions — a single anonymous `keydown` event listener registered at module load time.

- [ ] **Step 1: Add the keydown listener**

In `static/app.js`, `saveFixtures()` currently ends the Fixture Editor section (lines 267-269):
```js
function saveFixtures() {
  send({type:'save_fixtures', canvas: canvasSize, fixtures});
}
```
Immediately after it (still before the `// ── MIDI Routing ──` comment), add:
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

- [ ] **Step 2: Manual verification**

Run: `python3 main.py` (from project root), open `http://localhost:8080`, go to the Fixture Editor tab.
1. Click a fixture to select it. Press the Right arrow key 5 times — confirm the fixture's X value in the form and on the canvas increases by 1 each press (5px total). Hold Shift and press Right once more — confirm it jumps by 10.
2. With a fixture selected, press `#` — confirm the Orient dropdown flips between Horizontal/Vertical and the canvas rectangle's shape flips (wide↔tall).
3. Click into the "Name" text field in the fixture form and type a `#` character and press an arrow key while the field has focus — confirm the shortcuts do NOT fire (the `#` is typed literally into the field, the fixture does not move), then click elsewhere to defocus and confirm the shortcuts work again.
4. Press `+` (no field focused) — confirm a new vertical fixture is added and auto-selected, same as clicking "+ Add Strip".
5. Press `Tab` repeatedly — confirm the selection cycles through all fixtures in order and wraps back to the first one after the last.
6. Press `Escape` — confirm the fixture form hides and no fixture shows as selected (blue) on the canvas.
7. With nothing selected, press `Delete` — confirm nothing happens (no error). Select a fixture, press `Delete` — confirm it's removed, same as clicking "Delete Selected".
8. Switch to the Main tab and press an arrow key — confirm nothing happens to any fixture (shortcuts are inactive outside the Fixture Editor tab).

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: add keyboard shortcuts for fixture editor (move, orient, spawn, delete, cycle, deselect)"
```

---

## Task 3: Preset selection/save fix

**Files:**
- Modify: `static/style.css:29` (add `.preset-btn.selected`, add `.save-flash`)
- Modify: `static/index.html:47` (give the "Save to selected" button an id)
- Modify: `static/app.js:60-62` (leave untouched — confirm it only touches `.active`), `static/app.js:130-149` (`buildPresets()`, `updatePresetUI()`, `savePreset()`)

**Interfaces:**
- Produces: `updatePresetUI()` keeps its existing name/signature (no args, no return) but now toggles `.selected` instead of `.active`. `savePreset()` keeps its existing name/signature.

- [ ] **Step 1: Add CSS for the new `.selected` state and the save-confirmation flash**

In `static/style.css`, the preset button rules currently read (lines 26-30):
```css
#presets { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.preset-btn { width: 38px; height: 28px; background: #222; border: 1px solid #444;
              color: #aaa; cursor: pointer; border-radius: 3px; font-size: 11px; }
.preset-btn.active { background: #0af; color: #000; border-color: #0af; }
.preset-btn:hover { border-color: #888; }
```
Add a `.selected` rule right after `.preset-btn.active`:
```css
#presets { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.preset-btn { width: 38px; height: 28px; background: #222; border: 1px solid #444;
              color: #aaa; cursor: pointer; border-radius: 3px; font-size: 11px; }
.preset-btn.active { background: #0af; color: #000; border-color: #0af; }
.preset-btn.selected { border-color: #0af; border-width: 2px; }
.preset-btn:hover { border-color: #888; }
```
At the end of the file (after the existing `.algo-thumb.active` rule on line 64), add:
```css
.save-flash { background: #0f0 !important; color: #000; }
```

- [ ] **Step 2: Give the "Save to selected" button an id**

In `static/index.html`, the button currently reads (line 47):
```html
    <button class="primary" onclick="savePreset()">Save to selected</button>
```
Change it to:
```html
    <button id="save-preset-btn" class="primary" onclick="savePreset()">Save to selected</button>
```

- [ ] **Step 3: Fix `buildPresets()`/`updatePresetUI()` to toggle `.selected`, not `.active`**

In `static/app.js`, these currently read (lines 130-145):
```js
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
```
`buildPresets()` is unchanged. Change `updatePresetUI()` to toggle `.selected` instead of `.active`:
```js
function updatePresetUI() {
  document.querySelectorAll('.preset-btn').forEach((b,i) =>
    b.classList.toggle('selected', i === selectedPreset));
}
```

Confirm (no edit needed) that `applyState(s)` in the same file still reads exactly as today (lines 60-62), toggling `.active` only, driven only by `s.active_preset`:
```js
  document.querySelectorAll('.preset-btn').forEach((btn,i) => {
    btn.classList.toggle('active', s.active_preset === i);
  });
```
This is what makes the fix work: `.active` (server-driven) and `.selected` (client-driven) are now independent classes, so the periodic state broadcast can no longer erase the user's slot selection.

- [ ] **Step 4: Add save confirmation flash to `savePreset()`**

`savePreset()` currently reads (lines 147-149):
```js
function savePreset() {
  if (selectedPreset !== null) send({type:'save_preset', slot: selectedPreset});
}
```
Change it to:
```js
function savePreset() {
  if (selectedPreset === null) return;
  send({type:'save_preset', slot: selectedPreset});
  const btn = document.getElementById('save-preset-btn');
  btn.textContent = 'Saved!';
  btn.classList.add('save-flash');
  setTimeout(() => { btn.textContent = 'Save to selected'; btn.classList.remove('save-flash'); }, 1000);
}
```

- [ ] **Step 5: Manual verification**

Run: `python3 main.py` (from project root), open `http://localhost:8080`, stay on the Main tab.
1. Click preset button "4" — confirm it gets a blue outline (not a filled blue background) immediately.
2. Wait at least 1 second (longer than the 0.5s broadcast interval) without clicking anything else — confirm the blue outline on button "4" is still there (this is the actual bug fix: previously it would have disappeared).
3. Click "Save to selected" — confirm the button briefly shows "Saved!" with a green background, then reverts to "Save to selected" after about a second.
4. Move a fader, then click preset button "7", then "Save to selected" again — confirm button "7" gets the outline (not "4"), and after saving, check `presets.json` in the project root contains an entry at index 6 (0-indexed) matching the fader values you set.
5. Confirm clicking "Save to selected" with no preset button ever clicked (fresh page load) does nothing (no message sent, no console error) — reload the page first to reset `selectedPreset` to null, then click "Save to selected" immediately.

- [ ] **Step 6: Commit**

```bash
git add static/style.css static/index.html static/app.js
git commit -m "fix: separate preset save-target selection from MIDI-active highlight, add save confirmation"
```
