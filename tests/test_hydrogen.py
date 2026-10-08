import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

from orchid_studio.drum_song import write_demo_song
from orchid_studio.hydrogen import (HydrogenClient, command_message, decode_message,
                                   encode_message, session_drums)
from orchid_studio.sequencer import compile_session, demo_session
from orchid_studio.service import Transport, serve


class HydrogenTests(unittest.TestCase):
    def test_exact_osc_wire_types_and_padding(self):
        self.assertEqual(encode_message("/Hydrogen/BPM", (96,)),
                         b"/Hydrogen/BPM\0\0\0,f\0\0\x42\xc0\0\0")
        packet = encode_message("/Hydrogen/LOAD_DRUMKIT", ("GMRockKit",))
        self.assertEqual(decode_message(packet), {"address": "/Hydrogen/LOAD_DRUMKIT", "arguments": ["GMRockKit"]})
        self.assertEqual(len(packet) % 4, 0)

    def test_control_mapping_and_validation(self):
        self.assertEqual(command_message("pattern", 0), ("/Hydrogen/SELECT_ONLY_NEXT_PATTERN", (0,)))
        self.assertEqual(command_message("strip-volume", .5, 1), ("/Hydrogen/STRIP_VOLUME_ABSOLUTE/1", (.5,)))
        self.assertEqual(command_message("mode", "pattern"), ("/Hydrogen/SONG_MODE_ACTIVATION", (0.,)))
        for args in (("volume", float("nan")), ("bpm", 0), ("strip-volume", 1, 0),
                     ("pattern", -1), ("pattern", 1.5), ("loop", 1), ("kit", "a\0b"),
                     ("play", 1), ([],)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                command_message(*args)

    def test_socket_persistent_source_and_delivery_not_claimed(self):
        sock = Mock()
        with patch("orchid_studio.hydrogen.socket.socket", return_value=sock):
            with HydrogenClient() as client:
                first = client.command("bpm", 96)
                client.command("volume", .3)
            sock.bind.assert_called_once_with(("127.0.0.1", 9001))
            self.assertEqual(sock.sendto.call_count, 2)
            self.assertFalse(first["confirmed"])
            sock.close.assert_called_once()

    def test_drums_need_enabled_adapter_before_existing_playback_stops(self):
        transport = Transport(lambda msg: None, lambda report: None)
        session = demo_session()
        session["drums"] = {"engine": "hydrogen", "pattern": 0}
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
        session["drums"] = {"engine": "hydrogen", "pattern": 1, "volume": .25}
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

    def test_drums_failure_still_cleans_both_engines(self):
        drums = Mock()
        drums.stop.side_effect = OSError("failed")
        sent = []
        transport = Transport(sent.append, lambda report: None, drums)
        with self.assertRaises(OSError):
            transport.panic()
        self.assertEqual(len(sent), 64)
        drums.panic.assert_called_once()

    def test_service_controls_and_malformed_action(self):
        drums, reports = Mock(), []
        drums.command.return_value = {"status": "sent", "confirmed": False}
        lines = [json.dumps({"command": "drums", "action": []}),
                 json.dumps({"id": 1, "command": "drums", "action": "volume", "value": .2})]
        serve(lambda msg: None, lines, reports.append, drums)
        self.assertEqual(reports[0]["status"], "error")
        drums.command.assert_any_call("volume", .2, None)
        self.assertEqual(reports[-1]["id"], 1)

    def test_schema_rejects_unknown_drum_engines_and_controls(self):
        for drums in ({"engine": "orchid", "pattern": 0}, {"engine": "hydrogen", "pattern": 0, "magic": 1}, []):
            with self.assertRaises(ValueError):
                session_drums({"drums": drums})

    def test_layer_loops_expand_separately(self):
        session = {"version": 1, "bpm": 96, "length_beats": 8, "tracks": [
            {"name": "performed", "channel": 1, "loop_beats": 4,
             "notes": [{"beat": 0, "duration": 1, "note": 60}]},
            {"name": "bass", "channel": 2, "loop_beats": 2,
             "notes": [{"beat": 0, "duration": 1, "note": 36}]},
        ]}
        events, *_ = compile_session(session, repeats=2, transpose=2)
        performed = [e for e in events if e.track == "performed" and e.message[0] == 0x90]
        bass = [e for e in events if e.track == "bass" and e.message[0] == 0x91]
        self.assertEqual([e.beat for e in performed], [0, 4, 8, 12])
        self.assertEqual([e.beat for e in bass], list(range(0, 16, 2)))
        self.assertEqual(bass[0].message[1], 38)
        session["tracks"][0]["loop_beats"] = 3
        with self.assertRaises(ValueError):
            compile_session(session)

    def test_song_generation_reuses_kit_metadata_without_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "drumkit.xml").write_text('<drumkit_info xmlns="urn:kit"><name>Test</name><instrumentList>' +
                ''.join(f'<instrument><id>{i}</id><name>{name}</name></instrument>'
                        for i, name in enumerate(("Kick", "Snare", "Hat Closed"))) + '</instrumentList></drumkit_info>')
            output = root / "song.h2song"
            report = write_demo_song(output, root)
            song = ET.parse(output).getroot()
            self.assertEqual(len(song.findall("patternList/pattern")), 2)
            self.assertEqual(len(song.findall("patternList/pattern[1]/noteList/note")), 12)
            self.assertTrue(all(n.text == "-1" for n in song.findall("instrumentList/instrument/midiOutChannel")))
            self.assertFalse(report["samples_copied"])
            with self.assertRaises(FileExistsError):
                write_demo_song(output, root)


if __name__ == "__main__":
    unittest.main()
