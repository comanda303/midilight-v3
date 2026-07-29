# Fixture Grouping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let fixtures be tagged into named groups in the Fixture Editor, then selected, nudged, bulk-edited, rotated 90° as a rigid unit, copied (with auto-offset universe), and ungrouped — per `docs/superpowers/specs/2026-07-29-fixture-grouping-design.md`.

**Architecture:** Entirely client-side (`static/index.html`, `static/app.js`) — no backend changes. Adds one new optional field (`group`) to the fixture data shape, a new `selectedGroup` client global parallel to the existing `selectedFixture`, and a new `#group-form` panel parallel to the existing `#fixture-form`. Group actions reuse existing patterns (the arrow-key nudge, the `isHorizontal()`/bounding-box math already used for drawing and hit-testing) rather than introducing new abstractions.

**Tech Stack:** Vanilla JS, inline styles, global functions/variables — matches `static/app.js` exactly, same conventions as the 2026-07-05 keyboard-shortcuts work and the 2026-07-29 fixture-rotation work.

## Global Constraints

- No framework, no classes/modules — global functions and global variables only.
- No backend changes. `fixture_sampler.py` and everything server-side is untouched — `group` is a UI/editing-time concept only, never read by the render/sampling path.
- No automated JS test harness exists in this project — verification for every task is manual, via running the app (this project's established convention; see the fixture-rotation plan work from earlier this session).
- Only one of `selectedFixture` / `selectedGroup` is ever active at a time.
- `group` is always stored as a string (`''` for ungrouped), never `null`/`undefined`, so every read can safely use `f.group` or `f.group === x` without an extra existence check.
- Group rotation's orientation cycle is `H → V180 → H180 → V → H` (derived from rotating each orientation's pixel-0→last-pixel direction vector 90° clockwise) — **not** the same order as the single-fixture `#` key's cycle (`['H','H180','V','V180']`), which is arbitrary since that one never repositions anything.

---

## Task 1: `group` field on the fixture form

**Files:**
- Modify: `static/index.html` (`#fixture-form`)
- Modify: `static/app.js` (`addStrip()`, `showFixtureForm()`, `applyFixture()`)

**Interfaces:**
- Produces: fixture objects now always carry a `group: string` field (`''` when ungrouped). `showFixtureForm(f)`/`applyFixture()` keep their existing signatures, now also handling `f-group`.

- [ ] **Step 1: Add the Group input to the fixture form**

In `static/index.html`, `#fixture-form` currently reads:
```html
      <div id="fixture-form" style="display:none">
        <label>Name</label><input id="f-name" type="text">
        <label>X</label><input id="f-x" type="number" value="0">
```
Change it to:
```html
      <div id="fixture-form" style="display:none">
        <label>Name</label><input id="f-name" type="text">
        <label>Group</label><input id="f-group" type="text" placeholder="(none)">
        <label>X</label><input id="f-x" type="number" value="0">
```

- [ ] **Step 2: Default new fixtures to ungrouped**

In `static/app.js`, `addStrip()` currently reads:
```js
function addStrip() {
  fixtures.push({name: `strip_${fixtures.length+1}`, x:0, y:0,
                 orientation:'V', length:40, universe:0, start_channel:0});
  selectedFixture = fixtures.length - 1;
  showFixtureForm(fixtures[selectedFixture]);
  drawGrid();
}
```
Change it to:
```js
function addStrip() {
  fixtures.push({name: `strip_${fixtures.length+1}`, group:'', x:0, y:0,
                 orientation:'V', length:40, universe:0, start_channel:0});
  selectedFixture = fixtures.length - 1;
  showFixtureForm(fixtures[selectedFixture]);
  drawGrid();
}
```
(`copyFixture()` is unchanged — its `{...src, name: ...}` spread already carries `group` over from the source fixture, same as every other field.)

- [ ] **Step 3: Read/write `group` in the form**

In `static/app.js`, `showFixtureForm()` currently reads:
```js
function showFixtureForm(f) {
  document.getElementById('fixture-form').style.display = 'grid';
  document.getElementById('f-name').value = f.name || '';
  document.getElementById('f-x').value = f.x;
```
Change it to:
```js
function showFixtureForm(f) {
  document.getElementById('fixture-form').style.display = 'grid';
  document.getElementById('f-name').value = f.name || '';
  document.getElementById('f-group').value = f.group || '';
  document.getElementById('f-x').value = f.x;
```

`applyFixture()` currently reads:
```js
function applyFixture() {
  if (selectedFixture === null) return;
  fixtures[selectedFixture] = {
    name: document.getElementById('f-name').value,
    x: +document.getElementById('f-x').value,
```
Change it to:
```js
function applyFixture() {
  if (selectedFixture === null) return;
  fixtures[selectedFixture] = {
    name: document.getElementById('f-name').value,
    group: document.getElementById('f-group').value.trim(),
    x: +document.getElementById('f-x').value,
```

- [ ] **Step 4: Manual verification**

Run: `.venv/bin/python main.py` (from project root), open `http://localhost:8080`, go to the Fixture Editor tab.
1. Click an existing fixture (e.g. `strip_1`) — confirm the form now shows an empty "Group" field.
2. Type `left_wall` into Group, click Apply, click **Save Layout**.
3. Click `strip_2`, type `left_wall` into its Group field too, click Apply, click **Save Layout**.
4. Open `fixtures.json` in the project root — confirm both `strip_1` and `strip_2` now have `"group": "left_wall"`, and every other fixture has `"group": ""`.
5. Click "+ Add Strip" — confirm its Group field shows empty (not `undefined`, not stale from the last-viewed fixture).

- [ ] **Step 5: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: add group field to fixture editor form"
```

---

## Task 2: Group selection, highlighting, and keyboard move

**Files:**
- Modify: `static/index.html` (add `#select-group-btn` inside `#fixture-form`, add new `#group-form` panel as a sibling of `#fixture-form`)
- Modify: `static/app.js` (globals, `drawGrid()`, `gridCanvas.onclick`, `showFixtureForm()`, the `keydown` listener; new functions `selectGroup()`, `selectGroupOfCurrent()`, `showGroupForm()`, `ungroupSelected()`)

**Interfaces:**
- Consumes: `isHorizontal(orientation)` (existing, from the fixture-rotation work).
- Produces: `selectedGroup` (global, string group name or `null`). `selectGroup(name)` — global function, one string arg, sets `selectedGroup`, clears `selectedFixture`, shows the group panel, redraws. `showGroupForm(name)` — global function, one string arg, refreshes the group panel's name/member-list display for the given group name; **Tasks 3 and 4 call this directly** after bulk-editing/rotating to refresh the displayed member list without re-selecting. `ungroupSelected()` — global function, no args, clears `group` on every member of `selectedGroup`.

- [ ] **Step 1: Add the "Select Group" button and the group panel**

In `static/index.html`, `#fixture-form`'s closing Apply button currently reads:
```html
        <label>Start CH</label><input id="f-ch" type="number" value="0">
        <button class="primary" onclick="applyFixture()" style="grid-column:1/-1;margin-top:8px">Apply</button>
      </div>
```
Change it to (adds the button right after Apply, still inside `#fixture-form`):
```html
        <label>Start CH</label><input id="f-ch" type="number" value="0">
        <button class="primary" onclick="applyFixture()" style="grid-column:1/-1;margin-top:8px">Apply</button>
        <button id="select-group-btn" onclick="selectGroupOfCurrent()" style="grid-column:1/-1;margin-top:4px;display:none">Select Group</button>
      </div>
```

Immediately after that `</div>` (still inside the `min-width:220px` column, as a sibling of `#fixture-form`), add the group panel:
```html
      <div id="group-form" style="display:none">
        <div style="color:#888;font-size:11px;text-transform:uppercase;margin-bottom:6px">Group: <span id="group-name-display"></span></div>
        <div id="group-members" style="font-size:11px;color:#aaa;margin-bottom:10px"></div>
        <button class="danger" onclick="ungroupSelected()" style="width:100%">Ungroup</button>
      </div>
```

- [ ] **Step 2: Add the `selectedGroup` global**

In `static/app.js`, the top of the file currently reads:
```js
let ws, state = {}, selectedPreset = null, selectedFixture = null;
let fixtures = [], canvasSize = {width:200, height:100};
```
Change it to:
```js
let ws, state = {}, selectedPreset = null, selectedFixture = null, selectedGroup = null;
let fixtures = [], canvasSize = {width:200, height:100};
```

- [ ] **Step 3: Highlight every member of the selected group on canvas**

In `static/app.js`, `drawGrid()`'s last line currently reads:
```js
  fixtures.forEach((f, idx) => drawFixture(f, idx === selectedFixture, scale));
```
Change it to:
```js
  fixtures.forEach((f, idx) => drawFixture(f, idx === selectedFixture || (selectedGroup !== null && f.group === selectedGroup), scale));
```

- [ ] **Step 4: Clicking a fixture always clears group-selection mode**

In `static/app.js`, `gridCanvas.onclick` currently ends with:
```js
  if (hit >= 0) { selectedFixture = hit; showFixtureForm(fixtures[hit]); drawGrid(); }
};
```
Change it to:
```js
  if (hit >= 0) {
    selectedGroup = null;
    selectedFixture = hit;
    showFixtureForm(fixtures[hit]);
    drawGrid();
  }
};
```

- [ ] **Step 5: `showFixtureForm()` hides the group panel and shows/hides "Select Group"**

`showFixtureForm()` (as left by Task 1) currently reads:
```js
function showFixtureForm(f) {
  document.getElementById('fixture-form').style.display = 'grid';
  document.getElementById('f-name').value = f.name || '';
  document.getElementById('f-group').value = f.group || '';
  document.getElementById('f-x').value = f.x;
  document.getElementById('f-y').value = f.y;
  document.getElementById('f-orient').value = f.orientation || 'H';
  document.getElementById('f-universe').value = f.universe;
  document.getElementById('f-ch').value = f.start_channel;
}
```
Change it to:
```js
function showFixtureForm(f) {
  document.getElementById('group-form').style.display = 'none';
  document.getElementById('fixture-form').style.display = 'grid';
  document.getElementById('f-name').value = f.name || '';
  document.getElementById('f-group').value = f.group || '';
  document.getElementById('f-x').value = f.x;
  document.getElementById('f-y').value = f.y;
  document.getElementById('f-orient').value = f.orientation || 'H';
  document.getElementById('f-universe').value = f.universe;
  document.getElementById('f-ch').value = f.start_channel;

  const btn = document.getElementById('select-group-btn');
  if (f.group) {
    const count = fixtures.filter(x => x.group === f.group).length;
    btn.textContent = `Select Group (${count})`;
    btn.style.display = 'block';
  } else {
    btn.style.display = 'none';
  }
}
```

- [ ] **Step 6: Add `selectGroup()`, `selectGroupOfCurrent()`, `showGroupForm()`, `ungroupSelected()`**

In `static/app.js`, insert these four functions right after `showFixtureForm()` (before `applyFixture()`):
```js
function selectGroupOfCurrent() {
  if (selectedFixture === null) return;
  const g = fixtures[selectedFixture].group;
  if (!g) return;
  selectGroup(g);
}

function selectGroup(g) {
  selectedGroup = g;
  selectedFixture = null;
  document.getElementById('fixture-form').style.display = 'none';
  showGroupForm(g);
  drawGrid();
}

function showGroupForm(g) {
  const members = fixtures.filter(f => f.group === g);
  document.getElementById('group-form').style.display = 'block';
  document.getElementById('group-name-display').textContent = `${g} (${members.length})`;
  document.getElementById('group-members').textContent = members.map(f => f.name).join(', ');
}

function ungroupSelected() {
  if (selectedGroup === null) return;
  fixtures.forEach(f => { if (f.group === selectedGroup) f.group = ''; });
  selectedGroup = null;
  document.getElementById('group-form').style.display = 'none';
  drawGrid();
}
```

- [ ] **Step 7: Arrow keys move the whole group together; Escape clears group selection too**

In `static/app.js`, the `keydown` listener's tail currently reads:
```js
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

  if (e.key === '#') {
    e.preventDefault();
    const idx = ORIENTATIONS.indexOf(f.orientation);
    f.orientation = ORIENTATIONS[(idx + 1) % ORIENTATIONS.length];
  }
  else if (e.key === 'ArrowUp')    { e.preventDefault(); f.y -= step; }
  else if (e.key === 'ArrowDown')  { e.preventDefault(); f.y += step; }
  else if (e.key === 'ArrowLeft')  { e.preventDefault(); f.x -= step; }
  else if (e.key === 'ArrowRight') { e.preventDefault(); f.x += step; }
  else return;

  showFixtureForm(f);
  drawGrid();
});
```
Change it to:
```js
  if (e.key === 'Escape') {
    e.preventDefault();
    selectedFixture = null;
    selectedGroup = null;
    document.getElementById('fixture-form').style.display = 'none';
    document.getElementById('group-form').style.display = 'none';
    drawGrid();
    return;
  }

  const step = e.shiftKey ? 10 : 1;

  if (selectedGroup !== null) {
    if (e.key === 'ArrowUp')         { e.preventDefault(); fixtures.forEach(f => { if (f.group === selectedGroup) f.y -= step; }); }
    else if (e.key === 'ArrowDown')  { e.preventDefault(); fixtures.forEach(f => { if (f.group === selectedGroup) f.y += step; }); }
    else if (e.key === 'ArrowLeft')  { e.preventDefault(); fixtures.forEach(f => { if (f.group === selectedGroup) f.x -= step; }); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); fixtures.forEach(f => { if (f.group === selectedGroup) f.x += step; }); }
    else return;
    drawGrid();
    return;
  }

  if (selectedFixture === null) return;
  const f = fixtures[selectedFixture];

  if (e.key === '#') {
    e.preventDefault();
    const idx = ORIENTATIONS.indexOf(f.orientation);
    f.orientation = ORIENTATIONS[(idx + 1) % ORIENTATIONS.length];
  }
  else if (e.key === 'ArrowUp')    { e.preventDefault(); f.y -= step; }
  else if (e.key === 'ArrowDown')  { e.preventDefault(); f.y += step; }
  else if (e.key === 'ArrowLeft')  { e.preventDefault(); f.x -= step; }
  else if (e.key === 'ArrowRight') { e.preventDefault(); f.x += step; }
  else return;

  showFixtureForm(f);
  drawGrid();
});
```

- [ ] **Step 8: Manual verification**

Run: `.venv/bin/python main.py`, open `http://localhost:8080`, Fixture Editor tab. (Continue from Task 1's `left_wall` group on `strip_1`/`strip_2`, or create one now.)
1. Click `strip_1` — confirm a **"Select Group (2)"** button appears below Apply.
2. Click a fixture with no group (e.g. `strip_3`, assuming it's still ungrouped) — confirm the button is hidden.
3. Click `strip_1` again, click "Select Group (2)" — confirm: the single-fixture form hides, a new panel appears showing "Group: left_wall (2)" and both member names, and **both** `strip_1` and `strip_2` are highlighted blue on the canvas (not just one).
4. With the group selected, press the Right arrow key 5 times — confirm **both** highlighted fixtures move right by 5px together (their relative spacing unchanged), and neither the single-fixture form nor an error appears.
5. Press Escape — confirm the group panel hides and nothing is highlighted.
6. Select the group again, click "Ungroup" — confirm the panel hides, and clicking `strip_1`/`strip_2` individually now shows no "Select Group" button (their Group field is empty) but they still exist with their last-moved X/Y.
7. Click a plain fixture (no group) directly after having a group selected — confirm the group panel hides and the single-fixture form shows instead (selection modes don't overlap).

- [ ] **Step 9: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: select whole fixture group, highlight members, move together, ungroup"
```

---

## Task 3: Bulk-set Length / Universe / Name-prefix

**Files:**
- Modify: `static/index.html` (`#group-form`)
- Modify: `static/app.js` (new functions `bulkSetLength()`, `bulkSetUniverse()`, `bulkSetNamePrefix()`)

**Interfaces:**
- Consumes: `selectedGroup`, `fixtures`, `showGroupForm(g)` (from Task 2).
- Produces: three new global functions, each no-argument (they read their own input field), each a no-op if `selectedGroup === null`.

- [ ] **Step 1: Add the bulk-field inputs to the group panel**

In `static/index.html`, `#group-form` (as left by Task 2) currently reads:
```html
      <div id="group-form" style="display:none">
        <div style="color:#888;font-size:11px;text-transform:uppercase;margin-bottom:6px">Group: <span id="group-name-display"></span></div>
        <div id="group-members" style="font-size:11px;color:#aaa;margin-bottom:10px"></div>
        <button class="danger" onclick="ungroupSelected()" style="width:100%">Ungroup</button>
      </div>
```
Change it to:
```html
      <div id="group-form" style="display:none">
        <div style="color:#888;font-size:11px;text-transform:uppercase;margin-bottom:6px">Group: <span id="group-name-display"></span></div>
        <div id="group-members" style="font-size:11px;color:#aaa;margin-bottom:10px"></div>

        <label>Length</label>
        <div style="display:flex;gap:4px;margin-bottom:8px">
          <input id="g-length" type="number" value="40" style="width:70px;background:#222;border:1px solid #444;color:#eee;padding:2px 4px">
          <button onclick="bulkSetLength()">Apply to Group</button>
        </div>

        <label>Universe</label>
        <div style="display:flex;gap:4px;margin-bottom:8px">
          <input id="g-universe" type="number" value="0" style="width:70px;background:#222;border:1px solid #444;color:#eee;padding:2px 4px">
          <button onclick="bulkSetUniverse()">Apply to Group</button>
        </div>

        <label>Name prefix</label>
        <div style="display:flex;gap:4px;margin-bottom:10px">
          <input id="g-name-prefix" type="text" placeholder="e.g. wall" style="width:70px;background:#222;border:1px solid #444;color:#eee;padding:2px 4px">
          <button onclick="bulkSetNamePrefix()">Apply to Group</button>
        </div>

        <button class="danger" onclick="ungroupSelected()" style="width:100%">Ungroup</button>
      </div>
```

- [ ] **Step 2: Add the three bulk-set functions**

In `static/app.js`, insert these right after `ungroupSelected()`:
```js
function bulkSetLength() {
  if (selectedGroup === null) return;
  const len = +document.getElementById('g-length').value;
  fixtures.forEach(f => { if (f.group === selectedGroup) f.length = len; });
  drawGrid();
  showGroupForm(selectedGroup);
}

function bulkSetUniverse() {
  if (selectedGroup === null) return;
  const u = +document.getElementById('g-universe').value;
  fixtures.forEach(f => { if (f.group === selectedGroup) f.universe = u; });
  showGroupForm(selectedGroup);
}

function bulkSetNamePrefix() {
  if (selectedGroup === null) return;
  const prefix = document.getElementById('g-name-prefix').value.trim();
  if (!prefix) return;
  let i = 0;
  fixtures.forEach(f => { if (f.group === selectedGroup) { i++; f.name = `${prefix}_${i}`; } });
  showGroupForm(selectedGroup);
}
```

- [ ] **Step 3: Manual verification**

Run: `.venv/bin/python main.py`, open `http://localhost:8080`, Fixture Editor tab, select the `left_wall` group.
1. Set Length to `20`, click its "Apply to Group" — confirm both group members' canvas rectangles shrink to 20px on the canvas, and clicking either one individually afterward shows `20` in its Length... actually the single-fixture form has no Length field today (it's fixed at 40 in `applyFixture()`) — instead, confirm by opening `fixtures.json` after **Save Layout**: both members show `"length": 20`.
2. Set Universe to `3`, click Apply — confirm `fixtures.json` (after Save Layout) shows `"universe": 3` on both members, and fixtures in *other* groups/ungrouped are untouched.
3. Set Name prefix to `wall`, click Apply — confirm the "Group members" line in the panel updates immediately to show `wall_1, wall_2` (order matching their position in the fixtures array), without needing to re-select the group.
4. Confirm none of the three actions touch any fixture **outside** `left_wall` — check a third, ungrouped fixture's values are unchanged in `fixtures.json`.

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: bulk-set length, universe, and name prefix for a fixture group"
```

---

## Task 4: Rotate Group (90° geometric rotation)

**Files:**
- Modify: `static/index.html` (`#group-form`)
- Modify: `static/app.js` (new `ROTATE_CW` map, new functions `groupBoundingBox()`, `rotateGroup()`)

**Interfaces:**
- Consumes: `isHorizontal(orientation)`, `selectedGroup`, `fixtures`, `showGroupForm(g)`, `drawGrid()`.
- Produces: `rotateGroup()` — global function, no args, no-op if `selectedGroup === null`.

- [ ] **Step 1: Add the Rotate Group button**

In `static/index.html`, `#group-form` (as left by Task 3) currently ends with:
```html
        <button class="danger" onclick="ungroupSelected()" style="width:100%">Ungroup</button>
      </div>
```
Change it to (adds Rotate Group right before Ungroup):
```html
        <button class="primary" onclick="rotateGroup()" style="width:100%;margin-bottom:8px">Rotate Group 90°</button>
        <button class="danger" onclick="ungroupSelected()" style="width:100%">Ungroup</button>
      </div>
```

- [ ] **Step 2: Add the orientation-cycle map and the bounding-box helper**

In `static/app.js`, `ORIENTATIONS`/`isHorizontal()` currently read:
```js
const ORIENTATIONS = ['H', 'H180', 'V', 'V180'];
function isHorizontal(orientation) { return orientation === 'H' || orientation === 'H180'; }
```
Change it to (adds the rotation-cycle map right after):
```js
const ORIENTATIONS = ['H', 'H180', 'V', 'V180'];
function isHorizontal(orientation) { return orientation === 'H' || orientation === 'H180'; }

// 90-degree-clockwise orientation cycle for whole-group rotation -- derived from
// rotating each orientation's pixel-0-to-last-pixel direction vector 90deg CW.
// Deliberately a different cycle than the single-fixture '#' key above, which
// never repositions anything so its cycle order is arbitrary.
const ROTATE_CW = {H: 'V180', V180: 'H180', H180: 'V', V: 'H'};

function groupBoundingBox(members) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  members.forEach(f => {
    const len = f.length || 40;
    const horiz = isHorizontal(f.orientation);
    const w = horiz ? len : 4;
    const h = horiz ? 4 : len;
    minX = Math.min(minX, f.x);
    minY = Math.min(minY, f.y);
    maxX = Math.max(maxX, f.x + w);
    maxY = Math.max(maxY, f.y + h);
  });
  return {cx: (minX + maxX) / 2, cy: (minY + maxY) / 2};
}
```

- [ ] **Step 3: Add `rotateGroup()`**

In `static/app.js`, insert this right after `bulkSetNamePrefix()`:
```js
function rotateGroup() {
  if (selectedGroup === null) return;
  const members = fixtures.filter(f => f.group === selectedGroup);
  const {cx, cy} = groupBoundingBox(members);

  members.forEach(f => {
    const len = f.length || 40;
    const horiz = isHorizontal(f.orientation);
    const w = horiz ? len : 4;
    const h = horiz ? 4 : len;
    const centerX = f.x + w / 2, centerY = f.y + h / 2;

    // Screen-space 90deg clockwise point rotation around (cx, cy): (dx,dy) -> (-dy,dx)
    const newCenterX = cx - (centerY - cy);
    const newCenterY = cy + (centerX - cx);

    f.orientation = ROTATE_CW[f.orientation];
    const newHoriz = isHorizontal(f.orientation);
    const newW = newHoriz ? len : 4;
    const newH = newHoriz ? 4 : len;
    f.x = Math.round(newCenterX - newW / 2);
    f.y = Math.round(newCenterY - newH / 2);
  });

  drawGrid();
  showGroupForm(selectedGroup);
}
```

- [ ] **Step 4: Manual verification**

Run: `.venv/bin/python main.py`, open `http://localhost:8080`, Fixture Editor tab.
1. Set up a clean test group: create 3 fresh vertical strips (`+ Add Strip` three times, all default `V`, length 40), position them at X=0/Y=0, X=10/Y=0, X=20/Y=0 (edit X/Y in the form, Apply each), and give all three `group: rotate_test`. Save Layout.
2. Click one of them, "Select Group (3)", click **"Rotate Group 90°"**.
3. Confirm all 3 fixtures are now horizontal (wide/short rectangles, not tall/thin) and stacked one above another (roughly equal X, increasing Y in steps of ~10) instead of side by side — i.e. the arrangement visibly rotated a quarter turn, matching the brainstormed "3 strips side by side → stacked top to bottom" example.
4. Click "Rotate Group 90°" three more times (4 total) — confirm the group returns to its original orientation (all vertical again) and approximately its original position (allowing for `Math.round` drift of at most a pixel or two per rotation).
5. Try it on a group of 1 (put just one fixture in a group, select it, rotate) — confirm no error, and it simply flips orientation and stays centered on the same spot.

- [ ] **Step 5: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: rotate a fixture group 90 degrees as a rigid unit"
```

---

## Task 5: Copy Group

**Files:**
- Modify: `static/index.html` (`#group-form`)
- Modify: `static/app.js` (new functions `uniqueGroupName()`, `copyGroup()`)

**Interfaces:**
- Consumes: `selectedGroup`, `fixtures`, `selectGroup(g)` (from Task 2).
- Produces: `copyGroup()` — global function, no args, no-op if `selectedGroup === null`.

- [ ] **Step 1: Add the Copy Group button**

In `static/index.html`, `#group-form` (as left by Task 4) currently reads:
```html
        <button class="primary" onclick="rotateGroup()" style="width:100%;margin-bottom:8px">Rotate Group 90°</button>
        <button class="danger" onclick="ungroupSelected()" style="width:100%">Ungroup</button>
      </div>
```
Change it to:
```html
        <button class="primary" onclick="rotateGroup()" style="width:100%;margin-bottom:8px">Rotate Group 90°</button>
        <button onclick="copyGroup()" style="width:100%;margin-bottom:8px">Copy Group</button>
        <button class="danger" onclick="ungroupSelected()" style="width:100%">Ungroup</button>
      </div>
```

- [ ] **Step 2: Add `uniqueGroupName()` and `copyGroup()`**

In `static/app.js`, insert these right after `rotateGroup()`:
```js
function uniqueGroupName(base) {
  const existing = new Set(fixtures.map(f => f.group).filter(g => g));
  let candidate = `${base}_copy`;
  let n = 2;
  while (existing.has(candidate)) {
    candidate = `${base}_copy${n}`;
    n++;
  }
  return candidate;
}

function copyGroup() {
  if (selectedGroup === null) return;
  const members = fixtures.filter(f => f.group === selectedGroup);
  const newGroupName = uniqueGroupName(selectedGroup);
  const copies = members.map(f => ({...f, name: `${f.name}_copy`, group: newGroupName, universe: f.universe + 1}));
  fixtures.push(...copies);
  selectGroup(newGroupName);
}
```

- [ ] **Step 3: Manual verification**

Run: `.venv/bin/python main.py`, open `http://localhost:8080`, Fixture Editor tab. Use the `rotate_test` group from Task 4 (3 members, universe presumably `0`).
1. Select the group, click **"Copy Group"** — confirm 3 new fixtures appear at the *same* X/Y as the originals (fully overlapping on canvas — expected, per the spec's accepted limitation), the group panel now shows the *new* group (`rotate_test_copy`, 3 members named `..._copy`), and it's auto-selected/highlighted.
2. Click **Save Layout**, open `fixtures.json` — confirm the 3 new entries have `"universe": 1` (original members' `"universe": 0` untouched) and names ending in `_copy`.
3. Click `rotate_test` (the **original** group, not the copy) again, click "Select Group (3)", then "Copy Group" a **second** time — confirm this second copy is named `rotate_test_copy2` (not `rotate_test_copy` again, which already exists from step 1 and would otherwise silently merge the two copies into one group).
4. Confirm this second copy's members are at `"universe": 1` too (it copies from the *originals*, still at universe `0`, not from the first copy) — each copy generation is computed from its own source, not cumulative.

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: copy a fixture group with auto-incremented universe"
```
