import threading
from state import AppState, FADER_NAMES

def test_default_faders():
    s = AppState()
    assert len(s.faders) == 12
    assert all(v == 0.5 for v in s.faders)

def test_update_fader():
    s = AppState()
    s.update(faders=[0.0] * 12)
    assert s.faders[0] == 0.0

def test_snapshot_is_copy():
    s = AppState()
    snap = s.snapshot()
    snap['faders'][0] = 99.0
    assert s.faders[0] == 0.5

def test_consume_beat():
    s = AppState()
    assert s.consume_beat() is False
    s.update(beat=True)
    assert s.consume_beat() is True
    assert s.consume_beat() is False  # consumed

def test_thread_safe_update():
    s = AppState()
    errors = []
    def writer():
        for _ in range(1000):
            try:
                s.update(master=0.9)
            except Exception as e:
                errors.append(e)
    threads = [threading.Thread(target=writer) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert errors == []

def test_fader_names_length():
    assert len(FADER_NAMES) == 12

def test_set_fader_updates_single_index():
    s = AppState()
    s.set_fader(3, 0.75)
    assert s.faders[3] == 0.75
    assert s.faders[0] == 0.5  # untouched

def test_concurrent_set_fader_no_lost_updates():
    s = AppState()
    errors = []
    def writer(idx):
        for _ in range(500):
            try:
                s.set_fader(idx, 1.0)
                s.set_fader(idx, 0.0)
            except Exception as e:
                errors.append(e)
    threads = [threading.Thread(target=writer, args=(i,)) for i in range(12)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert errors == []
    assert len(s.faders) == 12
