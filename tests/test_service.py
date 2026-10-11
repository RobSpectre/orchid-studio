import io
import json
import threading
import unittest
from unittest.mock import Mock

from orchid_studio.sequencer import demo_session, session_drums
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


class NativeDrumTransportTests(unittest.TestCase):
    def test_drums_need_native_host_before_existing_playback_stops(self):
        transport = Transport(lambda msg: None, lambda report: None)
        session = demo_session()
        session["drums"] = {"engine": "studio", "pattern": 0}
        try:
            transport.play(demo_session())
            with self.assertRaises(ValueError):
                transport.play(session)
            self.assertTrue(transport.playing)
        finally:
            transport.stop()

    def test_coordinated_start_and_stop(self):
        drums, started = Mock(), threading.Event()
        sent = []
        def send(msg):
            sent.append(msg)
            if msg[0] == 0x90:
                started.set()
        session = demo_session()
        session["drums"] = {"engine": "studio", "pattern": 1, "volume": .25}
        transport = Transport(send, lambda report: None, drums)
        try:
            transport.play(session, bpm=108)
            self.assertTrue(started.wait(1))
            transport.stop()
            drums.start.assert_called_once_with(108, session["drums"])
            self.assertGreaterEqual(drums.stop.call_count, 2)
            self.assertIn([0x80, 60, 0], sent)
        finally:
            transport.panic()
        drums.panic.assert_called_once()

    def test_drums_failure_still_cleans_up_midi(self):
        drums = Mock()
        drums.stop.side_effect = OSError("failed")
        sent = []
        transport = Transport(sent.append, lambda report: None, drums)
        with self.assertRaises(OSError):
            transport.panic()
        self.assertEqual(len(sent), 64)
        drums.panic.assert_called_once()

    def test_drum_controls_validate_before_reaching_native_client(self):
        from orchid_studio.api import Controller
        client = Mock()
        client.command.return_value = {"status": "ok", "engine": "studio-native"}
        controller = Controller(lambda msg: None, lambda event: None, client)
        try:
            for bad in ({"action": []}, {"action": "open-song", "value": "song.h2song"},
                        {"action": "volume", "value": 2}, {"action": "mute", "value": 1}):
                with self.subTest(request=bad):
                    self.assertEqual(controller.execute({"command": "drums", **bad})["status"], "error")
            client.command.assert_not_called()
            response = controller.execute({"id": 1, "command": "drums", "action": "volume", "value": .2})
            self.assertEqual(response["id"], 1)
            client.command.assert_any_call("volume", .2, None)
        finally:
            controller.close()

    def test_schema_rejects_unknown_drum_engines_and_controls(self):
        for drums in ({"engine": "orchid", "pattern": 0}, {"engine": "hydrogen", "pattern": 0},
                      {"engine": "studio", "pattern": 0, "magic": 1}, []):
            with self.subTest(drums=drums), self.assertRaises(ValueError):
                session_drums({"drums": drums})
        self.assertEqual(session_drums({"drums": {"engine": "studio", "pattern": 2}}),
                         {"engine": "studio", "pattern": 2, "volume": .3})


if __name__ == "__main__":
    unittest.main()
