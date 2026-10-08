"""Compile our AU wrapper locally; never fetch or copy the licensed plugin."""
from importlib.resources import files
import os
import platform
import plistlib
import shutil
import subprocess

from .paths import data_dir, host_path


def build_host():
    if platform.system() != 'Darwin':
        raise ValueError('The six-voice Pistil AU host currently supports macOS only.')
    if not shutil.which('xcrun'):
        raise ValueError('Install Apple Command Line Tools with xcode-select --install, then retry.')
    target = host_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    cache = data_dir() / 'swift-module-cache'
    cache.mkdir(parents=True, exist_ok=True)
    sources = files('orchid_studio').joinpath('native')
    main = cache / 'main.swift'
    sampler = cache / 'DrumSampler.swift'
    main.write_text(sources.joinpath('PistilHost.swift').read_text())
    sampler.write_text(sources.joinpath('DrumSampler.swift').read_text())
    temporary = target.with_suffix('.next')
    result = subprocess.run(['xcrun', 'swiftc', '-swift-version', '5', '-O',
        '-module-cache-path', str(cache), str(main), str(sampler), '-o', str(temporary),
        '-framework', 'AppKit', '-framework', 'AVFoundation', '-framework', 'AudioToolbox',
        '-framework', 'CoreAudioKit'], capture_output=True, text=True)
    if result.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError('Native build failed: ' + result.stderr[-6000:])
    os.replace(temporary, target)
    info = {'CFBundleExecutable': target.name, 'CFBundleIdentifier': 'local.orchid-studio.pistil-host',
        'CFBundleName': 'Orchid Studio Pistil', 'CFBundlePackageType': 'APPL',
        'NSHighResolutionCapable': True, 'NSPrincipalClass': 'NSApplication',
        'LSMinimumSystemVersion': '13.0'}
    (target.parent.parent / 'Info.plist').write_bytes(plistlib.dumps(info))
    return {'status': 'built', 'path': str(target), 'architecture': platform.machine(),
            'plugin_bundled': False}
