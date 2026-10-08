import io
import json
import threading
import unittest

from orchid_studio.sequencer import demo_session
from orchid_studio.service import Transport, serve


class ServiceTests(unittest.TestCase):
    def test_stop_interrupts_wait_and_releases_note(self):
        sent, reports = [], []
        note_started = threading.Event()
        def send(message):
            sent.append(message)
            if message[0] == 0x90:
                note_started.set()
        transport = Transport(send, reports.append)
        try:
            transport.play(demo_session(), bpm=20)
            self.assertTrue(note_started.wait(1))
            transport.stop()
            self.assertFalse(transport.playing)
            self.assertIn([0x80, 60, 0], sent)
            self.assertIn({"event": "stopped", "cleanup": "sent"}, reports)
        finally:
            transport.stop()

    def test_invalid_replacement_preserves_current_playback(self):
        transport = Transport(lambda message: None, lambda report: None)
        try:
            transport.play(demo_session())
            with self.assertRaises(ValueError):
                transport.play({})
            self.assertTrue(transport.playing)
        finally:
            transport.stop()

    def test_json_protocol_recovers_and_eof_panics(self):
        sent, reports = [], []
        serve(sent.append, io.StringIO('bad json\n[]\n{"id":1,"command":"status"}\n'), reports.append)
        self.assertEqual([r["status"] for r in reports], ["error", "error", "ok"])
        self.assertEqual(reports[-1]["id"], 1)
        self.assertEqual(len(sent), 64)
        for channel in range(16):
            self.assertIn([0xB0 | channel, 64, 0], sent)
            self.assertIn([0xB0 | channel, 120, 0], sent)

    def test_quit_stops_reading_commands(self):
        reports = []
        serve(lambda message: None,
              [json.dumps({"command": "quit"}), json.dumps({"command": "demo"})], reports.append)
        self.assertEqual(reports, [{"id": None, "status": "closing"}])


if __name__ == "__main__":
    unittest.main()
