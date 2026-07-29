import json
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from state import AppState
from web_server import create_app
from config import save_config, default_config, save_fixtures

def _make_client(tmp_path):
    state = AppState()
    preset_manager = MagicMock()
    video_player = MagicMock()
    video_player.scan_clips.return_value = [None] * 64
    fixture_sampler = MagicMock()
    render_loop = MagicMock()
    render_loop.get_preview_jpeg.return_value = None
    render_loop.get_thumbnail_jpeg.return_value = None
    render_loop._gen.algo_count.return_value = 6

    config_path = str(tmp_path / 'config.yaml')
    fixtures_path = str(tmp_path / 'fixtures.json')
    setups_path = str(tmp_path / 'setups.json')
    save_config(default_config(), config_path)
    save_fixtures({'canvas': {'width': 200, 'height': 100}, 'fixtures': []}, fixtures_path)

    app = create_app(state, preset_manager, video_player, fixture_sampler,
                      render_loop, fixtures_path, config_path, setups_path)
    client = TestClient(app)
    return client, fixture_sampler, fixtures_path, config_path, setups_path

def test_websocket_sends_fixtures_reload_on_connect(tmp_path):
    client, *_ = _make_client(tmp_path)
    with client.websocket_connect('/ws') as ws:
        state_msg = ws.receive_json()
        assert state_msg['type'] == 'state'
        assert state_msg['setups'] == []
        assert state_msg['algo_count'] == 6
        reload_msg = ws.receive_json()
        assert reload_msg['type'] == 'fixtures_reload'
        assert reload_msg['canvas']['width'] == 200

def test_save_setup_persists_bundle_and_broadcasts(tmp_path):
    client, fixture_sampler, fixtures_path, config_path, setups_path = _make_client(tmp_path)
    with client.websocket_connect('/ws') as ws:
        ws.receive_json()  # state
        ws.receive_json()  # fixtures_reload
        ws.send_json({
            'type': 'save_setup',
            'name': 'venue_a',
            'canvas': {'width': 300, 'height': 150},
            'fixtures': [{'name': 'strip_1', 'x': 0, 'y': 0, 'orientation': 'V',
                          'length': 40, 'universe': 0, 'start_channel': 0}],
            'assignments': {'master': {'type': 'cc', 'number': 0, 'channel': 1}},
        })
        reload_msg = ws.receive_json()
        assert reload_msg['type'] == 'fixtures_reload'
        assert reload_msg['canvas']['width'] == 300
        state_msg = ws.receive_json()
        assert state_msg['type'] == 'state'
        assert 'venue_a' in state_msg['setups']

    with open(setups_path) as f:
        saved = json.load(f)
    assert saved['venue_a']['fixtures']['canvas']['width'] == 300
    assert saved['venue_a']['assignments']['master']['number'] == 0
    fixture_sampler.set_fixtures.assert_called_once()

def test_algo_thumbnail_endpoint_returns_204_when_not_rendered(tmp_path):
    client, *_ = _make_client(tmp_path)
    resp = client.get('/algo_thumbnail/0')
    assert resp.status_code == 204

def test_algo_thumbnail_endpoint_returns_jpeg(tmp_path):
    client, fixture_sampler, fixtures_path, config_path, setups_path = _make_client(tmp_path)
    # _make_client's render_loop is a MagicMock; override get_thumbnail_jpeg for idx 0
    # Re-create the client with a render_loop mock that returns bytes for idx 0:
    from unittest.mock import MagicMock
    from state import AppState
    from web_server import create_app
    state = AppState()
    preset_manager = MagicMock()
    video_player = MagicMock()
    video_player.scan_clips.return_value = [None] * 64
    fixture_sampler = MagicMock()
    render_loop = MagicMock()
    render_loop.get_preview_jpeg.return_value = None
    render_loop.get_thumbnail_jpeg.side_effect = lambda idx: b'\xff\xd8\xff' if idx == 0 else None
    app = create_app(state, preset_manager, video_player, fixture_sampler,
                      render_loop, fixtures_path, config_path, setups_path)
    resp = TestClient(app).get('/algo_thumbnail/0')
    assert resp.status_code == 200
    assert resp.headers['content-type'] == 'image/jpeg'
    assert resp.content == b'\xff\xd8\xff'

def test_load_setup_restores_bundle(tmp_path):
    client, fixture_sampler, fixtures_path, config_path, setups_path = _make_client(tmp_path)
    with client.websocket_connect('/ws') as ws:
        ws.receive_json(); ws.receive_json()  # initial state + fixtures_reload

        ws.send_json({
            'type': 'save_setup', 'name': 'venue_a',
            'canvas': {'width': 300, 'height': 150},
            'fixtures': [{'name': 'strip_1', 'x': 0, 'y': 0, 'orientation': 'V',
                          'length': 40, 'universe': 0, 'start_channel': 0}],
            'assignments': {'master': {'type': 'cc', 'number': 0, 'channel': 1}},
        })
        ws.receive_json(); ws.receive_json()  # fixtures_reload + state from save_setup

        ws.send_json({
            'type': 'save_fixtures',
            'canvas': {'width': 200, 'height': 100},
            'fixtures': [],
        })
        ws.receive_json()  # state broadcast from save_fixtures (no fixtures_reload for plain save)

        ws.send_json({'type': 'load_setup', 'name': 'venue_a'})
        reload_msg = ws.receive_json()
        assert reload_msg['type'] == 'fixtures_reload'
        assert reload_msg['canvas']['width'] == 300
        state_msg = ws.receive_json()
        assert state_msg['assignments']['master']['number'] == 0
