import unittest
import io
import json
import tempfile
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

from orchid_studio.capture import session_from_capture
from orchid_studio.cli import main
from orchid_studio.sequencer import compile_session


def packets():
    # Two beats at 120 BPM then two at 60 BPM: preserve musical note spacing.
    ticks = [i / 48 for i in range(49)] + [1 + i / 24 for i in range(1, 49)]
    messages = [{"time": t, "message": [248]} for t in ticks]
    messages += [{"time": t, "message": m} for t, m in [
        (.01, [144, 60, 80]), (.26, [128, 60, 0]),
        (.51, [145, 36, 70]), (.76, [129, 36, 0]),  # Separate bass excluded.
        (1.02, [144, 64, 81]), (1.52, [144, 64, 0]),
        (2.7, [144, 67, 75]),  # Boundary-clipped note.
        (.4, [176, 64, 127]), (.5, [250]), (.6, [240, 1, 247]),
    ]]
    return sorted(messages, key=lambda p: p["time"])


class CaptureTests(unittest.TestCase):
    def test_clock_normalization_channel_isolation_and_boundary_release(self):
        session = session_from_capture(packets(), channel=1, loop_beats=3.9, length_beats=7.8)
        notes = session["tracks"][0]["notes"]
        self.assertEqual([n["note"] for n in notes], [60, 64, 67])
        self.assertAlmostEqual(notes[0]["duration"], .5)
        self.assertAlmostEqual(notes[1]["beat"], 2)
        self.assertAlmostEqual(notes[1]["duration"], .5)
        self.assertAlmostEqual(notes[-1]["beat"] + notes[-1]["duration"], 3.9)
        self.assertEqual(session["capture"]["boundary_note_releases"], 1)
        events, bpm, length, _ = compile_session(session, bpm=90)
        self.assertEqual((bpm, length, len(events)), (90, 7.8, 12))
        self.assertTrue(all(e.message[0] in (128, 144) for e in events))

    def test_missing_clock_short_capture_and_empty_channel_rejected(self):
        for data, channel, beats in [([], 1, 2), (packets(), 1, 8), (packets(), 4, 2),
                                     (list(reversed(packets())), 1, 2)]:
            with self.subTest(channel=channel, beats=beats), self.assertRaises(ValueError):
                session_from_capture(data, channel=channel, loop_beats=beats)

    def test_same_pitch_retrigger_closes_previous_note(self):
        data = packets() + [{"time": .2, "message": [144, 60, 60]}]
        session = session_from_capture(sorted(data, key=lambda p: p["time"]), channel=1, loop_beats=2)
        first, second = session["tracks"][0]["notes"][:2]
        self.assertAlmostEqual(first["beat"] + first["duration"], second["beat"])

    def test_import_cli_never_opens_midi_or_overwrites_composition(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "capture.json", Path(folder) / "loop.json"
            source.write_text(json.dumps({"received": packets()}))
            args = ["import-capture", str(source), str(target), "--channel", "1", "--loop-beats", "2"]
            with patch("orchid_studio.midi.backend", side_effect=AssertionError), redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
                before = target.read_bytes()
                self.assertEqual(main(args), 1)
                self.assertEqual(target.read_bytes(), before)
