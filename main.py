import asyncio, sys, signal
import uvicorn
from config import load_config, load_fixtures
from state import AppState
from bpm_analyzer import BPMAnalyzer
from midi_input import MidiDispatcher, open_virtual_port
from generator import Generator
from video_player import VideoPlayer
from fixture_sampler import FixtureSampler
from artnet_output import ArtNetSender
from preset_manager import PresetManager
from render_loop import RenderLoop
from web_server import create_app

CONFIG_PATH   = 'config.yaml'
FIXTURES_PATH = 'fixtures.json'
PRESETS_PATH  = 'presets.json'
SETUPS_PATH   = 'setups.json'
CLIPS_DIR     = 'clips'

def main():
    cfg      = load_config(CONFIG_PATH)
    fix_data = load_fixtures(FIXTURES_PATH)

    state = AppState()
    state.update(assignments=cfg['midi']['assignments'])

    canvas_w = fix_data['canvas']['width']
    canvas_h = fix_data['canvas']['height']

    bpm_analyzer    = BPMAnalyzer()
    generator       = Generator()
    video_player    = VideoPlayer(CLIPS_DIR)
    fixture_sampler = FixtureSampler(fix_data['fixtures'])
    artnet_sender   = ArtNetSender(cfg['artnet']['ip'], cfg['artnet']['port'])
    preset_manager  = PresetManager(PRESETS_PATH, state,
                                    cfg['app']['preset_transition_ms'])
    dispatcher      = MidiDispatcher(state, bpm_analyzer, video_player,
                                     cfg['app']['velocity_scales_brightness'])

    render_loop = RenderLoop(
        state, generator, video_player, fixture_sampler,
        artnet_sender, bpm_analyzer, preset_manager,
        (canvas_h, canvas_w),
    )

    midi_in = open_virtual_port(dispatcher, cfg['midi']['port_name'])
    print(f"[MIDI] Virtual port '{cfg['midi']['port_name']}' open")

    render_loop.start()
    print(f"[Render] 30fps loop started — canvas {canvas_w}x{canvas_h}")
    print(f"[ArtNet] Sending to {cfg['artnet']['ip']}:{cfg['artnet']['port']}")

    app = create_app(state, preset_manager, video_player, fixture_sampler, render_loop, FIXTURES_PATH, CONFIG_PATH, SETUPS_PATH)

    def shutdown(sig, frame):
        print('\nShutting down…')
        render_loop.stop()
        artnet_sender.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print('[UI] Open http://localhost:8080')
    uvicorn.run(app, host='0.0.0.0', port=8080)

if __name__ == '__main__':
    main()
