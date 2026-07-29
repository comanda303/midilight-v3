# MIDI ArtNet Lightshow Controller — Design Spec
**Date:** 2026-06-26

## Overview

A standalone Python application that receives MIDI from Ableton Live via a virtual MIDI port and drives an ArtNet LED setup in real time. Zero CPU load on Ableton — all processing happens outside the DAW. Once configured, the musician controls the entire lightshow from Ableton without touching the UI.

**LED setup:** 16 strips × 40 RGB pixels, freely placed on an adjustable virtual canvas. Each strip has its own ArtNet universe and start address.

---

## Architecture

```
Ableton Live
    │ virtual MIDI port (MIDI notes + CC + MIDI clock)
    ▼
Python App
    │
    ├─ MIDI Dispatcher
    │    ├─ notes  → clip trigger / preset recall / strobe on-off
    │    └─ CC     → fader values / master / strobe params
    │
    ├─ BPM Analyzer (MIDI clock 0xF8 → live BPM)
    │
    ├─ Video Player (OpenCV) ──┐
    │                          ├─→ Compositor (blend ratio CC1)
    ├─ Generator (12 faders) ──┘        │
    │                                   ▼
    │                          Strobe / Gate
    │                                   │
    │                          Virtual Canvas (WxH pixel buffer)
    │                                   │
    │                          Fixture Sampler (x,y → fixture)
    │                                   │
    │                          ArtNet Output (UDP)
    │
    └─ WebSocket Server → Browser UI (localhost:8080)
```

**Render loop:** ~30 fps, runs in a background thread independent of MIDI input.

**Key source files:**
- `main.py` — startup, wires all components
- `midi_input.py` — listens to virtual MIDI port, dispatches events
- `bpm_analyzer.py` — tracks MIDI clock, exposes live BPM
- `video_player.py` — loads and plays video files, returns current frame
- `generator.py` — computes a frame from 12 fader parameters + time
- `compositor.py` — blends generator + video layers, applies strobe/gate
- `artnet_output.py` — samples canvas at fixture positions, sends ArtNet UDP
- `preset_manager.py` — saves/loads fader snapshots to JSON
- `web_server.py` — FastAPI + WebSocket, serves the browser UI
- `config.yaml` — all MIDI assignments, canvas size, app settings
- `fixtures.json` — fixture layout (position, universe, channel per strip)

---

## MIDI Mapping

All assignments are configurable via the MIDI Routing page in the UI and saved to `config.yaml`. Defaults below.

**Notes:**

| Note range | Function |
|---|---|
| 0–63 | Trigger video clip (slot index = note number) |
| 64–87 | Recall generator preset 1–24 |
| 88 | Strobe on (note-on) / off (note-off) |
| 89–127 | Reserved |

Note velocity on clip/preset triggers scales clip brightness independently of master. Can be disabled in `config.yaml`.

**CC:**

| CC | Function |
|---|---|
| 0 | Master brightness |
| 1 | Blend ratio (0 = generator only, 127 = video only) |
| 2 | Strobe rate (steps through 1/1, 1/2, 1/4, 1/8, 1/16, 1/32) |
| 3 | Strobe depth (0 = tremolo dip, 127 = full blackout gate) |
| 4–23 | Reserved for future global parameters |
| 24–35 | Generator faders 1–12 |

**MIDI clock:** Ableton sends MIDI clock (0xF8, 24 PPQ) over the same virtual port. The BPM analyzer derives live tempo from pulse timing. Strobe rate locks to BPM × selected division. Manual BPM override available in UI if clock not present.

**MIDI channel:** all messages on a single configurable channel (default: ch 1).

---

## Generator

A real-time visual algorithm that renders a full canvas frame on every tick. The 12 faders shape its output.

**Algorithms (Fader 1, stepped):**

| # | Name | Description |
|---|---|---|
| 1 | Plasma waves | Sinusoidal colour fields |
| 2 | Fire / fluid | Upward fire simulation |
| 3 | Noise crawler | Perlin/simplex noise drifting |
| 4 | Bars & pulses | Vertical/horizontal beat bars |
| 5 | Radial burst | Expanding rings from centre |
| 6 | Starfield | Particle / star movement |

**Faders:**

| # | CC | Name | Effect |
|---|---|---|---|
| 1 | 24 | Algorithm | Steps through 6 algorithms |
| 2 | 25 | Beat react | Punch intensity on each detected beat |
| 3 | 26 | Rhythm density | Pattern complexity (sparse ↔ busy) |
| 4 | 27 | Speed | Animation speed multiplier |
| 5 | 28 | Base hue | Starting colour (0–360°) |
| 6 | 29 | Saturation | Colourful ↔ white/grey |
| 7 | 30 | Colour spread | Monochrome ↔ full spectrum sweep |
| 8 | 31 | Scale | Zoom in/out on the pattern |
| 9 | 32 | Direction | Flow direction angle (0–360°) |
| 10 | 33 | Symmetry | None → mirror → quad |
| 11 | 34 | Contrast | Soft/washed ↔ hard/punchy |
| 12 | 35 | Blur/glow | Bloom softness amount |

**Beat reaction:** MIDI clock pulses are counted; each quarter note fires a `beat` event. Fader 2 scales how much this event distorts/amplifies the pattern (brightness spike, scale pop, colour flash). Independent from the strobe.

**Presets:** 24 slots (notes 64–87), each stores all 12 fader values. Recall interpolates smoothly to new values over a configurable transition time (default 200 ms).

---

## Video Player

**Formats:** mp4, mov, gif, avi (anything OpenCV can decode).

**Clip management:**
- Clips live in `clips/` folder; slot assignment is determined by a leading number in the filename: `00_intro.mp4` → slot 0, `01_drop.mp4` → slot 1, etc.
- Optional `clips/clips.yaml` overrides the filename-based assignment and adds per-clip name, fit mode, default blend
- All clips pre-scanned on startup; missing slots are silently skipped

**Playback:**
- Note-on → starts clip from beginning, loops continuously
- Note-off → clip stops; output falls back to generator layer
- Crossfade time configurable (default 0 ms = instant cut)
- Velocity on note-on scales clip brightness independently of master

**Canvas mapping:** each frame is resized to fill the virtual canvas (fill or fit, configurable). The result is composited with the generator in the next step.

---

## Compositor & Strobe/Gate

**Layer blend:**
- Generator (bottom) + video (top)
- CC1 blend ratio: linear per-pixel interpolation
- 0 = generator only, 127 = video only, middle = both visible

**Strobe/Gate (post-compositor):**
- Runs on the final blended frame before ArtNet output
- Rate: musical division locked to BPM from MIDI clock (1/1 → 1/32), selected via CC2
- Depth (CC3): low = brightness tremolo dip, high = full blackout gate cut
- Shape: square wave (CDJ-style hard cut)
- Toggle: note 88 on/off; when off, full frame passes through unchanged
- Displayed in UI as BPM and division (e.g. "128 BPM — 1/8")

**Per-frame pipeline:**
```
generator frame + video frame
        ↓
  compositor (CC1 blend)
        ↓
  strobe/gate (CC2 rate × CC3 depth × BPM)
        ↓
  virtual canvas (WxH pixel buffer)
        ↓
  fixture sampler (reads pixel at each fixture's x,y)
        ↓
  ArtNet UDP packets → LED hardware
```

---

## Virtual Canvas & Fixture System

**Canvas:** adjustable width × height in pixels (set in Fixture Editor UI). Render pipeline always works in this pixel space.

**Fixture format (`fixtures.json`):**
```json
{
  "canvas": { "width": 200, "height": 100 },
  "fixtures": [
    {
      "name": "strip_01",
      "x": 10, "y": 20,
      "orientation": "H",
      "length": 40,
      "universe": 0,
      "start_channel": 0
    }
  ]
}
```
Each fixture is a 1×40 RGB strip. Orientation H = horizontal, V = vertical. The sampler reads 40 consecutive pixels from the canvas starting at (x, y) and writes them to the ArtNet universe/channel range.

---

## Browser UI

Three pages, tab-switched. Served at `localhost:8080`.

**Page 1 — Main (show control):**
- Live BPM display + MIDI clock status indicator
- Master brightness and blend ratio controls (also show CC assignment)
- 12 vertical faders with name labels and CC number beneath each
- 24 preset buttons (highlight active preset)
- Clip list (slot number + filename, highlight active clip)
- Strobe section: current rate as division + BPM, depth fader, on/off indicator

**Page 2 — Fixture Editor:**
- Canvas size inputs (W × H) with Apply button
- Visual grid showing the virtual canvas; each placed strip shown as a coloured bar
- Add Strip / Delete Selected buttons
- Per-strip panel: X, Y, orientation, universe, start channel, name
- Save layout → writes `fixtures.json`

**Page 3 — MIDI Routing:**
- Table of all functions with their assigned type (CC/Note), number, and MIDI channel
- [Learn] button per row — send one MIDI message to assign
- [Save] and [Reset to defaults] buttons
- Faders and buttons on Page 1 show their assigned CC/note as a small label

---

## Configuration

**`config.yaml`** — loaded on startup, written by UI:
- MIDI port name
- MIDI channel
- All MIDI assignments (function → type/number/channel)
- Canvas size is the source of truth in `fixtures.json`; `config.yaml` does not duplicate it
- Strobe defaults (transition time, default division)
- Preset interpolation time (ms)
- Clip crossfade time (ms)
- ArtNet target IP and port

**`fixtures.json`** — written by Fixture Editor UI.

**`clips/`** — drop video files here, restart app to load.

**`presets.json`** — written by preset save actions in UI.

---

## Technology Stack

| Concern | Library |
|---|---|
| MIDI input | `python-rtmidi` |
| Video decode | `opencv-python` |
| Generator rendering | `numpy` (pixel buffer ops) |
| ArtNet output | raw UDP socket |
| Web server | `FastAPI` + `uvicorn` |
| WebSocket | `fastapi` WebSocket |
| BPM analysis | custom (MIDI clock pulse timing) |
| Config | `PyYAML` |

---

## Out of Scope

- Audio analysis (no microphone / line-in input)
- DMX (ArtNet only)
- Moving head / non-RGB fixture support
- Multi-machine / network sync
