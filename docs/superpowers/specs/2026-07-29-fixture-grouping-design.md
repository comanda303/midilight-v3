# Fixture Grouping — Design

**Goal:** Let fixtures be tagged into named groups in the Fixture Editor, then moved/rotated/bulk-edited/copied as a unit, on top of the 4-way orientation work already shipped (commit `232d90a`).

**Tech Stack:** Same as the rest of the editor — vanilla JS in `static/app.js`, inline styles in `static/index.html`, no framework, global functions/vars, direct DOM manipulation. This is entirely a `fixtures.json` schema addition + front-end change; no backend (`fixture_sampler.py`, `midi_input.py`, etc.) changes are needed — grouping is purely an editing-time concept, not a rendering-time one.

## Data model

One new optional field per fixture entry in `fixtures.json`:

```json
{ "name": "strip_1", "group": "left_wall", "x": 5, "y": 0, "orientation": "V", "length": 40, "universe": 0, "start_channel": 0 }
```

Fixtures with the same non-empty `group` string belong to the same group. No group ever needs its own top-level entry — membership is entirely implicit from matching strings. An empty/missing `group` means "ungrouped," same as today's fixtures.

## Selection UX

Clicking a fixture on the canvas keeps behaving exactly as it does today: it becomes `selectedFixture`, and the single-fixture form (`#fixture-form`) is shown. This is unchanged so no existing single-fixture workflow breaks.

**The single-fixture form gets one new field: `Group` (free-text), alongside Name/X/Y/Orient/Universe/Start CH.** This is the only way to create, join, rename, or leave a group — type the same string into every fixture you want grouped together; clear it to leave a group entirely. `showFixtureForm()`/`applyFixture()` read/write it like every other field. Leaving it blank (the default for both existing fixtures and new ones from `addStrip()`) means ungrouped, exactly like today.

If the clicked fixture has a non-empty `group`, the single-fixture form additionally shows a **"Select Group (N)"** button (N = member count). Clicking it enters **group-selection mode**:
- A new module-level var, `selectedGroup` (string name, or `null`), is set.
- `#fixture-form` is hidden; a new `#group-form` panel is shown instead.
- `drawGrid()`/`drawFixture()` highlight every fixture whose `group === selectedGroup` (same selected-color treatment `#0af` used for single selection today).
- `Escape` clears `selectedGroup` the same way it already clears `selectedFixture`.

Only one of `selectedFixture` / `selectedGroup` is active at a time — selecting a group clears `selectedFixture` and vice versa.

## Group panel (`#group-form`)

Shown only while `selectedGroup !== null`. Contains:

1. **Bulk-set fields** — one shared value applied to every member at once, each with its own input + "Apply to Group" button:
   - **Length** — sets `length` on every member.
   - **Universe** — sets `universe` on every member.
   - **Name prefix** — renames every member to `` `${prefix}_${i+1}` `` where `i` is the member's index within the group, counted in the order members appear in the `fixtures` array (stable, matches how `Tab`-cycling already orders fixtures).
2. **Rotate Group** button — see geometry below.
3. **Copy Group** button — see below.
4. **Ungroup** button — replaces "Delete Selected" in this mode (same button position, different label+handler): clears `group` on every member. Fixtures themselves are **not** deleted — per your call, this is the non-destructive default. Deleting an individual fixture still works exactly as today, via the single-fixture form's existing "Delete Selected."

## Rotate Group — geometry

Fixtures only support axis-aligned orientation (`H`/`H180`/`V`/`V180`), not arbitrary angles, so "rotate" means: turn the whole group 90° clockwise as a rigid block, around the center of the group's current bounding box.

**Step 1 — bounding box & pivot.** For every member, compute its occupied rectangle exactly as `drawFixture()`/the click-hit-test already do (`isHorizontal(orientation) ? {w: length, h: 4} : {w: 4, h: length}`, anchored at `x,y`). The group's bounding box is the union of all members' rectangles; the pivot is its center `(cx, cy)`.

**Step 2 — per-member transform.** For each member:
- Compute its current rectangle center: `(mx + w/2, my + h/2)`.
- Rotate that point 90° clockwise around the pivot using screen-space rotation (y grows downward): `newCenter = (cx - (my_center - cy), cy + (mx_center - cx))`.
- Update orientation via the fixed geometric cycle (derived from rotating each orientation's pixel-0→last-pixel direction vector 90° CW — this is **not** the same cycle order as the single-fixture `#` key, which is arbitrary since that one never moves anything):
  ```
  H    → V180
  V180 → H180
  H180 → V
  V    → H
  ```
- Re-derive the new top-left `x, y` from `newCenter` using the **new** orientation's width/height (which is just `length`/`4` swapped from before, since horizontal↔vertical flipped).

This is applied to every member using the *same* pivot computed once in Step 1, so the group rotates as a single block — members' positions relative to each other are preserved, only rotated.

**Edge cases, accepted as-is:**
- A rotated member can land at a negative coordinate or partly/fully off-canvas — already handled gracefully elsewhere (`fixture_sampler.py` skips out-of-canvas fixtures without raising).
- Overlap between fixtures (within or across groups) stays allowed, consistent with the rest of the editor — no collision checks anywhere in this feature.
- Groups of size 1 rotate fine (bounding box = that one fixture's rectangle, pivot = its own center) — no special-casing needed.

## Copy Group

Duplicates every member of the selected group in one action:
- Each copy gets `_copy` appended to its own `name` **and** to the shared `group` value. If a group called e.g. `left_wall_copy` already exists (i.e. this is the second time this group has been copied), append an incrementing number instead: `left_wall_copy2`, `left_wall_copy3`, … — checked against existing `group` values across all fixtures before assigning, so two separate copies never silently merge into one group.
- Every copy's `universe` is incremented by 1 from its source fixture's `universe`; `start_channel` is left unchanged. **Accepted limitation** (your explicit choice over the alternative "scan and append after last used channel" approach): this doesn't verify the next universe is actually free elsewhere in `fixtures.json` — if it collides with something else, you'll need to fix it manually afterward, same as any other manual channel assignment today.
- `x`/`y`/`orientation`/`length` are copied unchanged (identical footprint, offset only in universe) — same spot on the canvas as the originals, so you'll want to reposition the new group (e.g. via arrow keys or a group rotate) right after copying, same workflow as today's single-fixture "Copy Fixture."
- The new group becomes `selectedGroup` immediately, matching how `copyFixture()`/`addStrip()` already auto-select what they just created.

## Testing

No backend changes, and this project has zero automated JS test coverage by existing convention (matches every prior front-end-only task, e.g. the keyboard-shortcuts/preset-fix work). Verification will be manual: create a multi-member group, confirm "Select Group" highlights all of them, exercise each bulk field, Rotate Group (checking the H→V180→H180→V→H cycle and that relative positions are preserved), Copy Group (checking universe bump and the `_copy`/`_copy2` naming), and Ungroup (confirming fixtures survive with `group` cleared).

## Out of scope (for this pass)

- Arbitrary bulk-edit of any field (only Length/Universe/Name-prefix, per your choice).
- Multi-select via ctrl/shift-click to build a group interactively — groups are formed by hand-typing the same `group` string into each fixture's form, not by a selection gesture.
- Collision-aware channel placement on copy (see accepted limitation above).
