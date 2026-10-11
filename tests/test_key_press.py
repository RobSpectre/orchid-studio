import threading
import unittest
from unittest.mock import Mock, patch

from orchid_studio.api import Controller
from orchid_studio.key_press import KeyPress, parse_press
from orchid_studio.note_duration import duration_beats
from orchid_studio.timeline import Timeline
from orchid_studio.voicing import chord_voicing_packet, set_chord_voicing


class NotationTests(unittest.TestCase):
    def test_robot_score_duration_values(self):
        for text, beats in {'1/4': 1, '1/8': .5, '1/2': 2, '1': 4, '1/16': .25,
                            '1/8.': .75, '1/4t': 2/3, 'w': 4, 'h': 2, 'q': 1,
                            'e.': .75, 'et': 1/3, 's': .25, '2bars': 8,
                            '1bar': 4, '1.5bars': 6, '2bars+1/2': 10,
                            '1/4+1/16': 1.25, ' 1 bar + q ': 5,
                            '10000bars': 40000}.items():
            with self.subTest(text=text):
                self.assertAlmostEqual(duration_beats(text), beats)

    def test_invalid_duration_and_pitch_fail_before_playing(self):
        for value in (None, 1, True, '', ' ', '0', '0bars', '-1bar', '1/3', '1/0',
                      'q+', 'q..', 'nan', '1beat', 'x' * 41):
            with self.subTest(value=value), self.assertRaises(ValueError):
                duration_beats(value)
        for i, key in enumerate(('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')):
            self.assertEqual(parse_press({'key': key})['note'], 60 + i)
        self.assertEqual(parse_press({'key': 'G', 'octave': 9})['note'], 127)
        for request in ({'key': 'H'}, {'key': 'C4'}, {'key': 'G#', 'octave': 9},
                        {'key': 'C', 'octave': True}, {'key': 'C', 'velocity': 0},
                        {'key': 'C', 'slot': 7}, {'key': 'C', 'chord': 'chord.maj'}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                parse_press(request)


class VoicingTests(unittest.TestCase):
    def test_researched_sysex_checksum_and_exact_hardware_port(self):
        self.assertEqual(chord_voicing_packet(24), [240, 0, 34, 12, 1, 69, 24, 116, 247])
        for value in (1, 60):
            self.assertEqual(sum(chord_voicing_packet(value)[1:-1]) % 128, 0)
        port = Mock()
        port.get_ports.return_value = ['Other', 'Orchid']
        with patch('orchid_studio.voicing.backend') as backend:
            backend.return_value.MidiOut.return_value = port
            result = set_chord_voicing(24)
            port.open_port.assert_called_once_with(1)
            port.send_message.assert_called_once_with(chord_voicing_packet(24))
            self.assertFalse(result['confirmed'])
            port.close_port.assert_called_once()
            port.delete.assert_called_once()

    def test_bad_values_and_ports_never_send_and_failed_send_closes(self):
        with patch('orchid_studio.voicing.backend') as backend:
            for value in (0, 61, True, 1.5, '24', None):
                with self.assertRaises(ValueError): set_chord_voicing(value)
            for output in ('', 'Other', 'Orchid Studio Playback', None):
                with self.assertRaises(ValueError): set_chord_voicing(24, output)
            backend.assert_not_called()
            port = backend.return_value.MidiOut.return_value
            port.get_ports.return_value = ['Orchid', 'Orchid']
            with self.assertRaises(ValueError): set_chord_voicing(24)
            port.send_message.assert_not_called()
            port.delete.assert_called_once()
            port.reset_mock()
            port.get_ports.return_value = ['Orchid']
            port.send_message.side_effect = RuntimeError('disconnected')
            with self.assertRaises(RuntimeError): set_chord_voicing(24)
            port.close_port.assert_called_once()
            port.delete.assert_called_once()


class MusicalHoldTests(unittest.TestCase):
    def run_key(self, duration='q', running=True, change=None, fail=False):
        now = [0.]
        timeline = Timeline(60, clock=lambda: now[0])
        if running: timeline.reset(60)
        messages, events = [], []
        def send(slot, message):
            messages.append((now[0], slot, message))
            if fail and message[0] == 159: raise RuntimeError('send failed')
        key = KeyPress(send, timeline, events.append, clock=lambda: now[0])
        def wait(_):
            now[0] += .01
            if change: change(timeline, now[0])
            self.assertLess(now[0], 5)
            return False
        key.cancel = Mock()
        key.cancel.is_set.return_value = False
        key.cancel.wait.side_effect = wait
        spec = {**parse_press({'key': 'F#', 'duration': duration}), 'press_id': 1}
        key.state = dict(spec)
        key.run(spec)
        return key.snapshot(), messages, events

    def test_release_after_duration_running_or_idle(self):
        for running in (True, False):
            state, messages, events = self.run_key(running=running)
            self.assertEqual(messages[0][1:], (6, [159, 66, 64]))
            self.assertAlmostEqual(messages[1][0], 1, places=2)
            self.assertEqual(messages[1][2], [143, 66, 0])
            self.assertEqual([m[2] for m in messages[-4:]], [[191, cc, 0] for cc in (64, 66, 123, 120)])
            self.assertEqual(state['reason'], 'duration')
            self.assertEqual(events[-1]['event'], 'key_released')

    def test_duration_follows_tempo_change(self):
        def change(timeline, now):
            if now >= .5: timeline.tempo(120, 0)
        state, messages, _ = self.run_key(change=change)
        self.assertAlmostEqual(messages[1][0], .75, places=2)
        self.assertEqual(state['remaining_beats'], 0)

    def test_duration_follows_integrated_tempo_ramp(self):
        started = [False]
        def change(timeline, now):
            if not started[0]:
                timeline.tempo(120, 1)
                started[0] = True
        _, messages, _ = self.run_key(change=change)
        released_at = messages[1][0]
        # First .01 s at 60 BPM, then integral of smoothstep 60 -> 120.
        elapsed = released_at - .01
        integrated = .01 + elapsed + elapsed**3 - elapsed**4 / 2
        self.assertGreaterEqual(integrated, 1)
        self.assertLess(integrated, 1.02)

    def test_pause_and_send_error_release_notes(self):
        state, messages, _ = self.run_key(change=lambda t, now: t.pause(True) if now >= .2 else None)
        self.assertEqual(state['reason'], 'paused')
        self.assertAlmostEqual(messages[1][0], .2, places=2)
        state, messages, events = self.run_key(fail=True)
        self.assertEqual(state['status'], 'error')
        self.assertEqual(messages[1][2], [143, 66, 0])
        self.assertEqual(events[-1]['event'], 'key_press_error')


class KeyAPITests(unittest.TestCase):
    def controller(self):
        c = Controller(Mock(), Mock())
        self.addCleanup(c.close)
        c.sounds.host = Mock()
        c.sounds.host.error = None
        c.sounds.host.process.poll.return_value = None
        return c

    def test_stop_release_and_close_cancel_long_keys_without_blocking_api(self):
        for command in ('key-release', 'stop', 'panic', 'quit', 'close'):
            with self.subTest(command=command):
                c = self.controller()
                host = c.sounds.host
                pressed = threading.Event()
                c.report_output = lambda e: pressed.set() if e['event'] == 'key_pressed' else None
                reply = c.execute({'command': 'key-press', 'key': 'C', 'duration': '10000bars'})
                self.assertEqual(reply['status'], 'queued')
                self.assertTrue(pressed.wait(1))
                self.assertEqual(c.execute({'command': 'status'})['key_press']['status'], 'held')
                self.assertEqual(c.execute({'command': 'key-press', 'key': 'D'})['status'], 'error')
                if command == 'close': c.close()
                else: self.assertNotEqual(c.execute({'command': command})['status'], 'error')
                host.call.assert_any_call('midi', slot=6, message=[143, 60, 0], wait=False)
                self.assertEqual(c.key_press.snapshot()['status'], 'released')

    def test_errors_do_not_mutate_hardware_state_and_discovery_covers_new_commands(self):
        c = self.controller()
        self.assertTrue({'key-press', 'key-release', 'chord-voicing'} <= set(c.execute({'command': 'capabilities'})['commands']))
        with patch('orchid_studio.voicing.set_chord_voicing') as setter:
            setter.return_value = {'value': 24, 'confirmed': False, 'output': 'Orchid'}
            self.assertEqual(c.execute({'command': 'chord-voicing', 'value': 24})['status'], 'sent')
            setter.side_effect = ValueError('missing port')
            self.assertEqual(c.execute({'command': 'chord-voicing', 'value': 25})['status'], 'error')
            self.assertEqual(c.snapshot()['chord_voicing']['value'], 24)
        c.sounds.healthy = lambda: False
        self.assertEqual(c.execute({'command': 'key-press', 'key': 'C'})['status'], 'error')
        self.assertEqual(c.key_press.snapshot()['status'], 'idle')


if __name__ == '__main__':
    unittest.main()
