import unittest
from unittest.mock import Mock, patch
from orchid_studio.api import Controller
from orchid_studio.key_monitor import CHORD_WINDOW_S, KeyDecoder, KeyMonitor


def press(events):
    return [e for e in events if e["type"] == "press"]


class KeyDecoderTests(unittest.TestCase):
    def test_single_key_press_and_release_on_the_raw_chord_channel(self):
        d = KeyDecoder(3)
        self.assertEqual(d.feed([0x92, 48, 72], 10.0), [])  # still inside the chord window
        [event] = d.flush(10.0 + CHORD_WINDOW_S * 2)
        self.assertEqual(event, {"type": "press", "t": 10.0, "root": 48, "name": "C", "octave": 3, "notes": [48],
                                 "intervals": [0], "velocity": 72})
        [release] = d.feed([0x82, 48, 0], 10.3)
        self.assertEqual((release["type"], release["name"], release["held_s"]), ("release", "C", 0.3))
        self.assertEqual(d.feed([0x82, 48, 0], 10.31), [])  # Orchid's repeated note-off

    def test_a_chord_is_one_press_released_when_all_its_notes_stop(self):
        d = KeyDecoder(3)
        for i, note in enumerate((48, 51, 55)):
            d.feed([0x92, note, 65], 5.0 + i * .0001)
        [event] = d.flush(5.1)
        self.assertEqual((event["name"], event["intervals"], event["velocity"]), ("C", [0, 3, 7], 65))
        self.assertEqual(d.feed([0x92, 48, 0], 6.0) + d.feed([0x82, 51, 0], 6.0), [])  # note-on 0 is a note-off
        self.assertEqual(d.feed([0x82, 55, 0], 6.001)[0]["held_s"], 1.001)

    def test_a_note_off_inside_the_window_closes_the_press_first(self):
        d = KeyDecoder(3)
        d.feed([0x92, 60, 30], 1.0)
        events = d.feed([0x82, 60, 0], 1.002)
        self.assertEqual([e["type"] for e in events], ["press", "release"])
        self.assertEqual(events[0]["octave"], 4)  # the voicing dial can move a key up an octave

    def test_mirrored_notes_and_other_channels_are_ignored_and_the_dial_counts_clicks(self):
        d = KeyDecoder(3)
        self.assertEqual(d.feed([0x90, 48, 90], 1.0) + d.feed([0x91, 48, 90], 1.0), [])
        self.assertEqual(d.flush(2.0), [])
        first = d.feed([0xB0, 115, 23], 2.0)[0]
        self.assertEqual((first["type"], first["value"], first["delta"]), ("voicing", 23, None))
        self.assertEqual(d.feed([0xB0, 115, 25], 2.1)[0]["delta"], 2)
        self.assertEqual(d.feed([0xB0, 102, 4], 2.2) + d.feed([0xB1, 115, 4], 2.2), [])  # Sound dial, other channel
        with self.assertRaises(ValueError):
            KeyDecoder(0)

    def test_restruck_held_note_releases_the_earlier_press(self):
        d = KeyDecoder(3)
        d.feed([0x92, 48, 50], 1.0)
        d.flush(1.1)
        d.feed([0x92, 48, 60], 2.0)
        events = d.flush(2.1)
        self.assertEqual([(e["type"], e.get("held_s")) for e in events], [("release", 1.0), ("press", None)])


class KeyMonitorTests(unittest.TestCase):
    def test_monitor_only_opens_an_input_and_records_with_ids_beats_and_a_cursor(self):
        clock = Mock(return_value=100.0)
        reports = []
        monitor = KeyMonitor(reports.append, "Orchid", beat_at=lambda t: t - 90, clock=clock)
        source = Mock()
        source.get_ports.return_value = ["Orchid"]
        def callback(fn):
            fn(([0x92, 50, 81], 0), None)
            clock.return_value = 100.5
            fn(([0x82, 50, 0], 0), None)
            monitor.stop_event.set()
        source.set_callback.side_effect = callback
        with patch("orchid_studio.key_monitor.backend") as backend:
            backend.return_value.MidiIn.return_value = source
            monitor.run()
            backend.return_value.MidiOut.assert_not_called()
        source.ignore_types.assert_called_once_with(sysex=True, timing=True, active_sense=True)
        source.close_port.assert_called_once()
        result = monitor.events()
        down, up = result["events"]
        self.assertEqual((down["id"], down["name"], down["velocity"], down["beat"]), (1, "D", 81, 10.0))
        self.assertEqual((up["type"], up["held_s"]), ("release", 0.5))
        self.assertEqual(monitor.events(after=1)["events"], [up])
        self.assertEqual(up["press_t"], down["t"])  # same rounding, so clients can match them exactly
        self.assertEqual((result["last_key_event_id"], result["now"], result["truncated"]), (2, 100.5, False))
        self.assertEqual(monitor.state["presses"], 1)
        self.assertEqual(reports[0]["event"], "key_monitor_ready")
        with self.assertRaises(ValueError):
            KeyMonitor(Mock(), "Orchid Studio Playback")


class KeyMonitorApiTests(unittest.TestCase):
    def test_enable_read_and_disable_through_the_api(self):
        c = Controller(Mock(), Mock())
        try:
            self.assertEqual(c.execute({"command": "key-events"})["status"], "error")
            self.assertEqual(c.execute({"command": "status"})["key_monitor"], {"enabled": False})
            with patch("orchid_studio.key_monitor.KeyMonitor.start"):
                enabled = c.execute({"command": "key-monitor", "input": "Orchid", "chord_channel": 3})
            self.assertEqual(enabled["key_monitor"]["chord_channel"], 3)
            c.key_monitor.receive([0x92, 52, 70], 1.0)
            c.key_monitor.receive([0x82, 52, 0], 1.2)
            events = c.execute({"command": "key-events", "after": 0})
            self.assertEqual([e["type"] for e in events["events"]], ["press", "release"])
            self.assertIsNone(events["events"][0]["beat"])  # the Studio timeline is not running
            self.assertEqual(c.execute({"command": "status"})["key_monitor"]["presses"], 1)
            self.assertEqual(c.execute({"command": "key-monitor", "enabled": False})["key_monitor"], {"enabled": False})
            self.assertEqual(c.execute({"command": "key-monitor", "enabled": "yes"})["status"], "error")
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
