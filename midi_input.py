from __future__ import annotations
from state import AppState, STROBE_DIVISIONS
from bpm_analyzer import BPMAnalyzer

NOTE_CLIP_MIN, NOTE_CLIP_MAX = 0, 63
NOTE_PRESET_MIN, NOTE_PRESET_MAX = 64, 87
MIDI_CLOCK = 0xF8

class MidiDispatcher:
    def __init__(self, state: AppState, bpm_analyzer: BPMAnalyzer, video_player=None,
                 velocity_scales_brightness: bool = True):
        self.state = state
        self.bpm = bpm_analyzer
        self.video_player = video_player
        self.velocity_scales_brightness = velocity_scales_brightness

    def on_message(self, event: tuple[list[int], float], data=None) -> None:
        message, _deltatime = event
        if not message:
            return
        status = message[0]

        if status != MIDI_CLOCK:
            print(f'[midi] {[hex(b) for b in message]}')

        if status == MIDI_CLOCK:
            self.bpm.on_clock_pulse()
            self.state.update(bpm=self.bpm.bpm, midi_clock_active=True)
            return

        msg_type = status & 0xF0
        channel = (status & 0x0F) + 1

        if msg_type == 0xB0:
            if len(message) < 3:
                return
            cc_num, cc_val = message[1], message[2]
            self._handle_cc(cc_num, cc_val, channel)

        elif msg_type == 0x90 and len(message) >= 3 and message[2] > 0:
            note, vel = message[1], message[2]
            self._handle_note_on(note, vel, channel)

        elif msg_type == 0x80 or (msg_type == 0x90 and len(message) >= 3 and message[2] == 0):
            note = message[1]
            self._handle_note_off(note, channel)

    def _handle_cc(self, cc_num: int, cc_val: int, channel: int) -> None:
        val = cc_val / 127.0
        assignments = self.state.assignments

        for name, asgn in assignments.items():
            if asgn.get('type') != 'cc':
                continue
            if asgn.get('number') != cc_num:
                continue
            if asgn.get('channel', 1) != channel:
                continue

            if name == 'master':
                self.state.update(master=val)
            elif name == 'blend':
                self.state.update(blend=val)
            elif name == 'strobe_rate':
                idx = min(int(val * len(STROBE_DIVISIONS)), len(STROBE_DIVISIONS) - 1)
                self.state.update(strobe_rate_index=idx)
            elif name == 'strobe_depth':
                self.state.update(strobe_depth=val)
            elif name.startswith('fader_'):
                idx = int(name.split('_')[1]) - 1
                self.state.set_fader(idx, val)

        if self.state.learn_target:
            target = self.state.learn_target
            self.state.set_assignment(target, {
                'type': 'cc', 'number': cc_num, 'channel': channel})
            self.state.update(learn_target=None)

    def _handle_note_on(self, note: int, velocity: int, channel: int) -> None:
        if NOTE_CLIP_MIN <= note <= NOTE_CLIP_MAX:
            self.state.update(active_clip=note)
            if self.video_player is not None:
                brightness = (velocity / 127.0) if self.velocity_scales_brightness else 1.0
                self.video_player.trigger(note, brightness)
            return

        if NOTE_PRESET_MIN <= note <= NOTE_PRESET_MAX:
            preset_idx = note - NOTE_PRESET_MIN
            self.state.update(active_preset=preset_idx)
            return

        for name, asgn in self.state.assignments.items():
            if asgn.get('type') != 'note' or asgn.get('number') != note:
                continue
            if asgn.get('channel', 1) != channel:
                continue
            if name == 'strobe_toggle':
                self.state.update(strobe_active=True)

        if self.state.learn_target:
            target = self.state.learn_target
            self.state.set_assignment(target, {
                'type': 'note', 'number': note, 'channel': channel})
            self.state.update(learn_target=None)

    def _handle_note_off(self, note: int, channel: int) -> None:
        if NOTE_CLIP_MIN <= note <= NOTE_CLIP_MAX:
            if self.state.active_clip == note:
                self.state.update(active_clip=None)
            if self.video_player is not None:
                self.video_player.stop(note)
            return

        for name, asgn in self.state.assignments.items():
            if asgn.get('type') != 'note' or asgn.get('number') != note:
                continue
            if asgn.get('channel', 1) != channel:
                continue
            if name == 'strobe_toggle':
                self.state.update(strobe_active=False)


def open_virtual_port(dispatcher: MidiDispatcher, port_name: str):
    import rtmidi
    midi_in = rtmidi.MidiIn()
    ports = midi_in.get_ports()
    match = next((i for i, p in enumerate(ports) if port_name in p), None)
    if match is not None:
        print(f'[MIDI] Opening existing port: {ports[match]}')
        midi_in.open_port(match)
    else:
        print(f'[MIDI] Creating virtual port: {port_name}')
        midi_in.open_virtual_port(port_name)
    midi_in.set_callback(dispatcher.on_message)
    midi_in.ignore_types(sysex=True, timing=False, active_sense=True)
    return midi_in
