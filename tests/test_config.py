import json, os, tempfile
import pytest
from config import load_config, save_config, load_fixtures, save_fixtures, default_config, load_setups, save_setups

def test_default_config_has_required_keys():
    cfg = default_config()
    assert 'midi' in cfg
    assert 'artnet' in cfg
    assert 'app' in cfg
    assert cfg['midi']['channel'] == 1
    assert cfg['artnet']['port'] == 6454

def test_save_and_load_config(tmp_path):
    cfg = default_config()
    cfg['artnet']['ip'] = '1.2.3.4'
    path = str(tmp_path / 'config.yaml')
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded['artnet']['ip'] == '1.2.3.4'

def test_load_config_missing_file_returns_default(tmp_path):
    path = str(tmp_path / 'nonexistent.yaml')
    cfg = load_config(path)
    assert cfg['midi']['channel'] == 1

def test_load_config_empty_file_returns_default(tmp_path):
    path = tmp_path / 'config.yaml'
    path.write_text('')
    cfg = load_config(str(path))
    assert cfg['midi']['channel'] == 1

def test_save_and_load_fixtures(tmp_path):
    data = {
        'canvas': {'width': 300, 'height': 150},
        'fixtures': [{'name': 'strip_01', 'x': 0, 'y': 10,
                      'orientation': 'H', 'length': 40,
                      'universe': 0, 'start_channel': 0}]
    }
    path = str(tmp_path / 'fixtures.json')
    save_fixtures(data, path)
    loaded = load_fixtures(path)
    assert loaded['canvas']['width'] == 300
    assert loaded['fixtures'][0]['name'] == 'strip_01'

def test_load_fixtures_missing_file_returns_empty(tmp_path):
    path = str(tmp_path / 'nope.json')
    data = load_fixtures(path)
    assert data['fixtures'] == []
    assert 'canvas' in data

def test_load_setups_missing_file_returns_empty(tmp_path):
    path = str(tmp_path / 'setups.json')
    assert load_setups(path) == {}

def test_save_and_load_setups(tmp_path):
    path = str(tmp_path / 'setups.json')
    data = {
        'venue_a': {
            'assignments': {'master': {'type': 'cc', 'number': 0, 'channel': 1}},
            'fixtures': {'canvas': {'width': 200, 'height': 100}, 'fixtures': []},
        }
    }
    save_setups(data, path)
    loaded = load_setups(path)
    assert loaded['venue_a']['fixtures']['canvas']['width'] == 200
    assert loaded['venue_a']['assignments']['master']['number'] == 0
