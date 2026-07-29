# MIDI ArtNet Lightshow Controller

Standalone Python app that receives MIDI from Ableton Live and drives an ArtNet LED matrix in real time.

## Requirements

- Python 3.9+ (verified working on 3.9.6 macOS system Python; originally documented as 3.12+)
- Linux or macOS (virtual MIDI port via python-rtmidi)
- A machine on the same network as your ArtNet node

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Configuration

Edit `config.yaml` before first run:
- `artnet.ip` — IP address of your ArtNet node (default: `10.0.0.23`)
- `midi.port_name` — name of the virtual MIDI port Ableton connects to (default: `LightShow`)

## Run

```bash
./start.sh
```

Convenience script that `cd`s into the project directory and runs `main.py` with the venv's Python — works from a double-click or any working directory. (Equivalent to `.venv/bin/python main.py`.)

Output:
```
[MIDI] Virtual port 'LightShow' open
[Render] 30fps loop started — canvas 200x100
[ArtNet] Sending to 10.0.0.23:6454
[UI] Open http://localhost:8080
```

## Usage

1. Open `http://localhost:8080` in a browser
2. In Ableton Live → MIDI preferences → enable the `LightShow` input port
3. Control from Ableton:

| MIDI | Function |
|------|----------|
| Notes 0–63 | Trigger video clips (note-on starts, note-off stops) |
| Notes 64–87 | Recall generator preset 1–24 |
| Note 88 | Strobe on (note-on) / off (note-off) |
| CC 0 | Master brightness |
| CC 1 | Blend: generator ↔ video |
| CC 2 | Strobe rate (1/1 → 1/32, BPM-locked) |
| CC 3 | Strobe depth (tremolo dip → full blackout) |
| CC 24–35 | Generator faders 1–12 |

## Adding video clips

Drop video files into the `clips/` folder. Name them with a leading slot number:

```
clips/00_intro.mp4
clips/01_drop.mp4
clips/15_outro.mp4
```

Restart the app to load new clips. Supported formats: mp4, mov, avi, gif (anything OpenCV can decode).

## Fixture mapping

Open the **Fixture Editor** tab in the browser UI:

1. Set canvas size (W × H pixels)
2. Click **+ Add Strip** for each LED strip
3. Set X, Y position, orientation, ArtNet universe and start channel
4. Click **Save Layout**

Each strip is 40 RGB pixels. Universe/channel must match your ArtNet node wiring.
X/Y is always the top-left corner of the strip's bounding box, for every orientation.

**Orientation** (press `#` in the editor to cycle):
| Value | Pixel 0 | Growing toward |
|-------|---------|-----------------|
| `H` (default) | left | right |
| `H180` | right | left |
| `V` (default) | bottom | up |
| `V180` | top | down |

The green square marks pixel 0, the red square marks the last pixel, drawn on each
strip in the editor canvas.

## MIDI learn

Open the **MIDI Routing** tab and click **Learn** next to any function. Send one MIDI message from Ableton to assign it.

## Generator algorithms

Fader 1 (CC 24) steps through 6 visual algorithms:

| Range | Algorithm |
|-------|-----------|
| 0–17% | Plasma waves |
| 17–33% | Fire / fluid |
| 33–50% | Noise crawler |
| 50–67% | Bars & pulses |
| 67–83% | Radial burst |
| 83–100% | Starfield |

## Presets

Save: select a preset button in the UI → click **Save to selected**  
Recall: send MIDI note 64–87 from Ableton (or click in UI)  
Faders interpolate smoothly to the recalled values over 200 ms.

## Changelog

### 2026-07-29
- **Fixture orientation now has 4 states** (`H`, `H180`, `V`, `V180`) instead of 2, giving full 90°-step control over which end of a strip is pixel 0 — see Fixture mapping above. Editor canvas now draws a green square at pixel 0 and a red square at the last pixel of every strip.
- **Breaking change:** `V` used to mean pixel 0 at the top; it now means pixel 0 at the **bottom** (matches the new "default = left or bottom" convention). `V180` is the old top-start behavior. `fixtures.json` was **not** auto-migrated — any fixture saved as `V` before this change will sample its pixels in reverse order the next time it's loaded. Check/re-save each strip's orientation in the Fixture Editor before your next live use.
- `fixture_sampler.py` reverses the sampled pixel array for `H180`/`V`; `H`/`V180` are unchanged from before.

### 2026-07-27
- **Fix:** `MidiDispatcher.on_message` in `midi_input.py` treated its first argument as the raw MIDI byte list, but `python-rtmidi` actually calls the callback with a `(message_bytes, delta_time)` tuple. This caused a `TypeError` inside the CoreMIDI real-time callback thread on every incoming message — silently swallowed, with no error output — so no MIDI ever reached the app (learn, clip triggers, CC control, all dead) despite the virtual port existing and accepting messages correctly. Fixed by unpacking `message, _deltatime = event` at the top of `on_message`. Updated all direct-call sites in `tests/test_midi_input.py` to pass the same `(message, delta_time)` tuple shape.
- Added `start.sh` as a one-command launcher (activates the project's `.venv`, runs `main.py`).
- Set up a local `.venv` for this machine (macOS system Python 3.9.6) and installed `requirements.txt` into it — dependencies aren't portable between machines/venvs, so a fresh `.venv` is needed on each machine this project runs on.
