import time
from bpm_analyzer import BPMAnalyzer

def test_bpm_calculation():
    analyzer = BPMAnalyzer()
    interval = 1.0 / 48.0  # 120 BPM = 48 pulses/sec
    t = 0.0
    for _ in range(50):
        analyzer.on_clock_pulse(t)
        t += interval
    assert 115 < analyzer.bpm < 125

def test_beat_fires_every_24_pulses():
    analyzer = BPMAnalyzer()
    beats = 0
    for i in range(72):  # 3 beats worth
        analyzer.on_clock_pulse(float(i) / 48.0)
        if analyzer.consume_beat():
            beats += 1
    assert beats == 3

def test_consume_beat_resets_flag():
    analyzer = BPMAnalyzer()
    for i in range(24):
        analyzer.on_clock_pulse(float(i) / 48.0)
    assert analyzer.consume_beat() is True
    assert analyzer.consume_beat() is False

def test_clock_active_after_pulses():
    analyzer = BPMAnalyzer()
    assert analyzer.clock_active is False
    analyzer.on_clock_pulse(0.0)
    assert analyzer.clock_active is True

def test_default_bpm():
    analyzer = BPMAnalyzer()
    assert analyzer.bpm == 120.0

def test_bpm_recovers_after_clock_stop_and_restart():
    analyzer = BPMAnalyzer()
    interval = 1.0 / 48.0  # 120 BPM
    t = 0.0
    for _ in range(50):
        analyzer.on_clock_pulse(t)
        t += interval
    t += 10.0  # clock stopped for 10 seconds
    for _ in range(5):
        analyzer.on_clock_pulse(t)
        t += interval
    assert 115 < analyzer.bpm < 125
