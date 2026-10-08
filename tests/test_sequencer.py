import copy
import io
import json
import subprocess
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from orchid_studio.cli import main, midi_inventory
from orchid_studio.midi import exact_port, software_output
from orchid_studio.sequencer import Player, compile_session, demo_session


class FakeClock:
    def __init__(self):
        self.now = 0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class SequencerTests(unittest.TestCase):
    def test_tempo_transpose_repeat_and_balanced_notes(self):
        events, bpm, length, channels = compile_session(demo_session(), transpose=5, repeats=2, bpm=120)
        self.assertEqual((bpm, length, channels), (120, 32, {0}))
        self.assertEqual(events[0].message, (0x90, 65, 48))
        self.assertEqual(events[32].beat, 16)
        clock, sent = FakeClock(), []
        player = Player(sent.append, channels, clock=clock.clock, sleep=clock.sleep)
        player.play(events, bpm, length)
        self.assertEqual(clock.now, 16)
        self.assertFalse(player.active)
        self.assertEqual(sent[-4:], [[0xB0, cc, 0] for cc in (64, 66, 123, 120)])
        self.assertEqual(len(sent), 68)

    def test_tracks_stay_separate_and_all_get_panic(self):
        session = demo_session()
        bass = copy.deepcopy(session["tracks"][0])
        bass.update(name="bass", channel=4)
        session["tracks"].append(bass)
        events, bpm, length, channels = compile_session(session)
        sent, clock = [], FakeClock()
        Player(sent.append, channels, clock=clock.clock, sleep=clock.sleep).play(events, bpm, length)
        self.assertEqual(channels, {0, 3})
        self.assertIn([0x93, 60, 48], sent)
        self.assertIn([0xB3, 64, 0], sent)

    def test_interrupt_releases_active_note_and_pedals(self):
        sent = []
        clock = FakeClock()
        events, bpm, length, channels = compile_session(demo_session())
        def sleep(seconds):
            if sent:
                raise KeyboardInterrupt
        player = Player(sent.append, channels, clock=clock.clock, sleep=sleep)
        with self.assertRaises(KeyboardInterrupt):
            player.play(events, bpm, length)
        self.assertEqual(sent[1], [0x80, 60, 0])
        self.assertEqual(sent[-1], [0xB0, 120, 0])

    def test_cleanup_continues_after_send_failure(self):
        sent = []
        def send(message):
            sent.append(message)
            if message[0] == 0x80:
                raise OSError("disconnected")
        player = Player(send, {0, 3})
        player.active.add((0, 60))
        with self.assertRaises(RuntimeError):
            player.panic()
        self.assertIn([0xB3, 120, 0], sent)

    def test_send_failure_still_attempts_note_off(self):
        sent, clock = [], FakeClock()
        def send(message):
            sent.append(message)
            if message[0] == 0x90:
                raise OSError("send failed")
        events, bpm, length, channels = compile_session(demo_session())
        with self.assertRaises(OSError):
            Player(send, channels, clock=clock.clock, sleep=clock.sleep).play(events, bpm, length)
        self.assertIn([0x80, 60, 0], sent)

    def test_invalid_sessions_rejected(self):
        for value in (0, -1, float("nan"), float("inf"), True, "fast"):
            with self.subTest(bpm=value), self.assertRaises(ValueError):
                compile_session(demo_session(), bpm=value)
        session = demo_session()
        session["tracks"][0]["notes"][0]["note"] = 100
        with self.assertRaises(ValueError):
            compile_session(session, transpose=48)
        for field, value in (("note", 128), ("beat", -1), ("duration", 17), ("velocity", 0)):
            session = demo_session()
            session["tracks"][0]["notes"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                compile_session(session)

    def test_duplicate_channels_and_overlapping_notes_rejected(self):
        session = demo_session()
        track = copy.deepcopy(session["tracks"][0])
        track["name"] = "bass"
        session["tracks"].append(track)
        with self.assertRaises(ValueError):
            compile_session(session)
        session = demo_session()
        session["tracks"][0]["notes"].append(session["tracks"][0]["notes"][0].copy())
        with self.assertRaises(ValueError):
            compile_session(session)

    def test_release_precedes_retrigger(self):
        session = demo_session()
        session["length_beats"] = 1
        session["tracks"][0]["notes"] = [{"beat": 0, "duration": 1, "note": 60}]
        events, *_ = compile_session(session, repeats=2)
        self.assertEqual([e.message[0] for e in events if e.beat == 1], [0x80, 0x90])


class CLITests(unittest.TestCase):
    def test_dry_run_never_opens_midi(self):
        with patch("orchid_studio.midi.backend", side_effect=AssertionError), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["demo", "--dry-run"]), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "dry_run")

    def test_native_abort_becomes_diagnostic(self):
        result = subprocess.CompletedProcess([], -6, "", "native abort")
        with patch("orchid_studio.cli.subprocess.run", return_value=result):
            self.assertFalse(midi_inventory()["available"])

    def test_output_only_creates_virtual_source(self):
        with patch("orchid_studio.midi.backend") as backend:
            with software_output():
                pass
            output = backend.return_value.MidiOut.return_value
            output.open_virtual_port.assert_called_once_with("Orchid Studio Playback")
            output.open_port.assert_not_called()
            output.close_port.assert_called_once()

    def test_exact_unambiguous_port_required(self):
        self.assertEqual(exact_port(["A", "B"], "B"), 1)
        for ports in (["Other A"], ["A", "A"]):
            with self.assertRaises(ValueError):
                exact_port(ports, "A")


if __name__ == "__main__":
    unittest.main()
