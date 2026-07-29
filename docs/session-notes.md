# MIDI Lightshow — Session Notes

## Project Overview

Standalone Python app receiving MIDI from Ableton Live, driving ArtNet LED setup.
- **16 strips × 40 RGB pixels** via ArtNet
- **FastAPI + WebSocket** browser UI at `http://localhost:8080`
- **30fps render loop** with generator, video player, compositor
- **Entry point:** `python3 main.py` (from project root)

---

## Current Hardware Setup

- **ArtNet target:** `10.0.0.23:6454` (LED driver IP — change in `config.yaml`)
- **Fixtures:** defined in `fixtures.json` — edit via Fixture Editor tab in UI
- **Clips folder:** `clips/` — name files like `1_red.mp4`, `2_clip.mp4` (slot number prefix required)

---

## MIDI Setup (macOS)

### IAC Driver approach (working)
Virtual ports (rtmidi) don't reliably connect with Ableton on Mac. Use macOS IAC Driver instead:

1. Open **Audio MIDI Setup** (Spotlight search)
2. Double-click **IAC Driver** → check **"Device is online"**
3. In `config.yaml` set `port_name: "IAC Driver Bus 1"`
4. In **Ableton Preferences → Link/Tempo/MIDI → MIDI Ports** enable **Track** output for IAC Driver Bus 1
5. Enable **Sync** output for IAC Driver Bus 1 (sends BPM clock)
6. In Ableton: MIDI track output → **IAC Driver Bus 1**, Ch. 1

The Python code (`midi_input.py`) automatically detects whether to open an existing port or create a virtual one based on the port name in config.

### Linux
On Linux the virtual port `LightShow` is created automatically — no IAC Driver needed.

---

## MIDI Mapping (Channel 1)

| MIDI | Function |
|------|----------|
| CC 0 | Master brightness |
| CC 1 | Blend (Generator ↔ Video) |
| CC 2 | Strobe rate |
| CC 3 | Strobe depth |
| CC 24–35 | Generator faders 1–12 |
| Note 0–63 | Clip trigger (note on = play, note off = stop) |
| Note 64–87 | Preset recall |
| Note 88 | Strobe toggle (note on = on, note off = off) |
| MIDI Clock | BPM sync (blue dot in UI) |

Mappings are remappable via the **MIDI Routing** tab in the browser UI (click Learn, move a knob).

---

## What Was Fixed/Added This Session

### Fixed
- **Clip buttons not clickable** — server was running old code; restart fixed it (clips were loading fine)
- **MIDI not reaching Python from Ableton on Mac** — switched from virtual port to IAC Driver
- **`midi_input.py`** now auto-detects: opens existing port by name if found, otherwise creates virtual port

### Added
- **Clip trigger buttons** in UI — click to play, click again to stop
- **Video preview** — live JPEG preview above faders (~10fps)
- **Strobe ON/OFF toggle button** in UI (alongside MIDI note 88)
- **Strobe Duration fader** — controls duty cycle (flash length vs. dark time)
- **`/debug` endpoint** — `http://localhost:8080/debug` shows loaded clips and state

---

## Known Issues / Next Steps

- **Video clips on Mac** — OpenCV can't read H.264 on Mac in some cases. Fix: re-encode with FFmpeg:
  ```bash
  brew install ffmpeg
  ffmpeg -i input.mp4 -c:v libx264 -pix_fmt yuv420p output.mp4
  ```
- **MIDI Learn** — needs live testing now that IAC Driver is working
- **Strobe duty cycle** not yet assignable via MIDI (only UI fader)
- **Dist zip** needs updating after today's changes

---

## Installation (new machine)

```bash
unzip midi-lightshow-dist.zip -d midi-lightshow
cd midi-lightshow
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
# copy video clips into clips/ folder
# edit config.yaml (artnet ip, port_name)
python3 main.py
```

Then open `http://localhost:8080`

---

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point, wires everything together |
| `config.yaml` | ArtNet IP, MIDI port name, CC/note assignments |
| `fixtures.json` | LED strip positions and ArtNet universe mapping |
| `web_server.py` | FastAPI + WebSocket + `/preview` + `/debug` |
| `midi_input.py` | MIDI dispatcher, auto port detection |
| `render_loop.py` | 30fps loop, preview JPEG generation |
| `video_player.py` | OpenCV clip slots 0–63 |
| `compositor.py` | Blend, strobe (with duty cycle), master |
| `generator.py` | 6 visual algorithms × 12 faders |
| `static/` | Browser UI (index.html, app.js, style.css) |
| `clips/` | Video files (name: `<slot>_name.mp4`) |
