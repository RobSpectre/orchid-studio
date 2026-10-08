import unittest
from unittest.mock import Mock, patch
from orchid_studio.sound_follow import SoundFollower, sound_report


class SoundFollowTests(unittest.TestCase):
    def test_only_observed_sound_reports_pass(self):
        bulk = [240, 0, 34, 12, 52, 48] + [0] * 135 + [247]
        self.assertEqual(len(bulk), 142)
        self.assertEqual(sound_report([176, 102, 48]), {'kind': 'preset', 'preset': 49})
        self.assertEqual(sound_report(bulk), {'kind': 'sound-state', 'preset': 49})
        for packet in ([144, 60, 90], [146, 60, 90], [176, 64, 127], [177, 102, 48],
                       [176, 102, 100], [176, 113, 1], [248], [250],
                       [240, 0, 34, 12, 115, 0, 247], bulk[:-1], bulk[:4]+[53]+bulk[5:]):
            self.assertIsNone(sound_report(packet))

    def test_follower_opens_only_input_and_forwards_no_notes(self):
        sent, events = [], []
        follower = SoundFollower(sent.append, events.append, 'Orchid')
        source = Mock()
        source.get_ports.return_value = ['Orchid']
        packets = iter([([144, 60, 90], 0), ([176, 102, 48], 0)])
        def get_message():
            try:
                return next(packets)
            except StopIteration:
                follower.stop_event.set()
                return None
        source.get_message.side_effect = get_message
        with patch('orchid_studio.sound_follow.backend') as backend:
            backend.return_value.MidiIn.return_value = source
            follower.run()
            backend.return_value.MidiOut.assert_not_called()
        self.assertEqual(sent, [[176, 102, 48]])
        self.assertEqual(follower.state['last_preset'], 49)
        source.close_port.assert_called_once()
        source.delete.assert_called_once()
