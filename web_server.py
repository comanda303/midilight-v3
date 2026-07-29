from __future__ import annotations
import asyncio, json, os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from state import AppState
from preset_manager import PresetManager
from video_player import VideoPlayer
from config import save_fixtures, save_config, load_config, load_fixtures, load_setups, save_setups

class ConnectionManager:
    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)

    async def broadcast(self, msg: dict):
        data = json.dumps(msg)
        for client in list(self._clients):
            try:
                await client.send_text(data)
            except Exception:
                if client in self._clients:
                    self._clients.remove(client)

def create_app(state: AppState, preset_manager: PresetManager,
               video_player: VideoPlayer, fixture_sampler, render_loop,
               fixtures_path: str, config_path: str, setups_path: str) -> FastAPI:
    app = FastAPI()
    manager = ConnectionManager()

    def _full_state_msg() -> dict:
        snap = state.snapshot()
        snap['type'] = 'state'
        snap['clips'] = video_player.scan_clips()
        snap['setups'] = list(load_setups(setups_path).keys())
        snap['algo_count'] = render_loop._gen.algo_count()
        return snap

    @app.websocket('/ws')
    async def ws_endpoint(ws: WebSocket):
        await manager.connect(ws)
        await ws.send_text(json.dumps(_full_state_msg()))
        fixtures_data = load_fixtures(fixtures_path)
        await ws.send_text(json.dumps({'type': 'fixtures_reload', **fixtures_data}))
        try:
            while True:
                text = await ws.receive_text()
                msg = json.loads(text)
                mtype = msg.get('type')

                if mtype == 'set_fader':
                    state.set_fader(int(msg['index']), float(msg['value']))

                elif mtype == 'set_master':
                    state.update(master=float(msg['value']))

                elif mtype == 'set_blend':
                    state.update(blend=float(msg['value']))

                elif mtype == 'set_strobe_rate':
                    state.update(strobe_rate_index=int(msg['index']))

                elif mtype == 'set_strobe_depth':
                    state.update(strobe_depth=float(msg['value']))

                elif mtype == 'set_bpm':
                    state.update(bpm=float(msg['value']))

                elif mtype == 'set_strobe':
                    state.update(strobe_active=bool(msg['active']))

                elif mtype == 'set_strobe_duty':
                    state.update(strobe_duty=float(msg['value']))

                elif mtype == 'clip_trigger':
                    slot = int(msg['slot'])
                    state.update(active_clip=slot)
                    video_player.trigger(slot)

                elif mtype == 'clip_stop':
                    slot = int(msg['slot'])
                    state.update(active_clip=None)
                    video_player.stop(slot)

                elif mtype == 'save_preset':
                    preset_manager.save(int(msg['slot']))

                elif mtype == 'save_fixtures':
                    data = {'canvas': msg['canvas'], 'fixtures': msg['fixtures']}
                    save_fixtures(data, fixtures_path)
                    fixture_sampler.set_fixtures(msg['fixtures'])

                elif mtype == 'save_assignments':
                    state.update(assignments=msg['assignments'])
                    cfg = load_config(config_path)
                    cfg['midi']['assignments'] = msg['assignments']
                    save_config(cfg, config_path)

                elif mtype == 'save_setup':
                    name = msg['name']
                    assignments = msg['assignments']
                    fixtures_data = {'canvas': msg['canvas'], 'fixtures': msg['fixtures']}
                    state.update(assignments=assignments)
                    cfg = load_config(config_path)
                    cfg['midi']['assignments'] = assignments
                    save_config(cfg, config_path)
                    save_fixtures(fixtures_data, fixtures_path)
                    fixture_sampler.set_fixtures(msg['fixtures'])
                    setups = load_setups(setups_path)
                    setups[name] = {'assignments': assignments, 'fixtures': fixtures_data}
                    save_setups(setups, setups_path)
                    await manager.broadcast({'type': 'fixtures_reload', **fixtures_data})

                elif mtype == 'load_setup':
                    setups = load_setups(setups_path)
                    bundle = setups.get(msg['name'])
                    if bundle is not None:
                        state.update(assignments=bundle['assignments'])
                        cfg = load_config(config_path)
                        cfg['midi']['assignments'] = bundle['assignments']
                        save_config(cfg, config_path)
                        save_fixtures(bundle['fixtures'], fixtures_path)
                        fixture_sampler.set_fixtures(bundle['fixtures']['fixtures'])
                        await manager.broadcast({'type': 'fixtures_reload', **bundle['fixtures']})

                elif mtype == 'learn_start':
                    state.update(learn_target=msg['target'])

                elif mtype == 'learn_stop':
                    state.update(learn_target=None)

                await manager.broadcast(_full_state_msg())

        except WebSocketDisconnect:
            manager.disconnect(ws)

    @app.on_event('startup')
    async def start_push():
        async def _push():
            while True:
                await asyncio.sleep(0.5)
                await manager.broadcast(_full_state_msg())
        asyncio.create_task(_push())

    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    if os.path.isdir(static_dir):
        app.mount('/static', StaticFiles(directory=static_dir), name='static')

    @app.get('/preview')
    async def preview():
        jpeg = render_loop.get_preview_jpeg()
        if jpeg is None:
            return Response(status_code=204)
        return Response(content=jpeg, media_type='image/jpeg')

    @app.get('/algo_thumbnail/{idx}')
    async def algo_thumbnail(idx: int):
        jpeg = render_loop.get_thumbnail_jpeg(idx)
        if jpeg is None:
            return Response(status_code=204)
        return Response(content=jpeg, media_type='image/jpeg')

    @app.get('/debug')
    async def debug_info():
        snap = state.snapshot()
        loaded = {str(k): video_player._clip_names[k]
                  for k in range(64) if video_player._clip_names[k] is not None}
        return {
            'clips_loaded': loaded,
            'caps_keys': list(video_player._caps.keys()),
            'active_clip': snap.get('active_clip'),
            'blend': snap.get('blend'),
        }

    @app.get('/')
    async def index():
        return FileResponse(os.path.join(static_dir, 'index.html'))

    return app
