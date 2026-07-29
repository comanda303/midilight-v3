from __future__ import annotations
import json
import yaml

def default_config() -> dict:
    return {
        'midi': {
            'port_name': 'LightShow',
            'channel': 1,
            'assignments': {
                'master':        {'type': 'cc',   'number': 0,  'channel': 1},
                'blend':         {'type': 'cc',   'number': 1,  'channel': 1},
                'strobe_rate':   {'type': 'cc',   'number': 2,  'channel': 1},
                'strobe_depth':  {'type': 'cc',   'number': 3,  'channel': 1},
                **{f'fader_{i+1}': {'type': 'cc', 'number': 24 + i, 'channel': 1}
                   for i in range(12)},
                'strobe_toggle': {'type': 'note', 'number': 88, 'channel': 1},
            },
        },
        'artnet': {'ip': '10.0.0.23', 'port': 6454},
        'app': {
            'preset_transition_ms': 200,
            'clip_crossfade_ms': 0,
            'velocity_scales_brightness': True,
        },
    }

def load_config(path: str) -> dict:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else default_config()
    except (FileNotFoundError, yaml.YAMLError):
        return default_config()

def save_config(config: dict, path: str) -> None:
    with open(path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

def load_fixtures(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'canvas': {'width': 200, 'height': 100}, 'fixtures': []}

def save_fixtures(data: dict, path: str) -> None:
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def load_setups(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_setups(data: dict, path: str) -> None:
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
