"""Native timing regression tests; no plugin, MIDI device, or audio output needed."""
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(platform.system() == 'Darwin' and shutil.which('xcrun'), 'requires macOS Swift SDK')
class NativeMIDISchedulerTests(unittest.TestCase):
    def test_deadlines_and_cancellation(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / 'midi-tests'
            result = subprocess.run([
                'xcrun', 'swiftc', '-swift-version', '5',
                '-module-cache-path', str(Path(folder) / 'cache'),
                str(root / 'src/orchid_studio/native/MIDIScheduler.swift'),
                str(root / 'tests/native/MIDISchedulerTests.swift'),
                '-o', str(binary), '-framework', 'AVFoundation', '-framework', 'AudioToolbox',
            ], capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('regression checks passed', result.stdout)
