"""Writable state is separate from installed code; existing checkouts keep local/."""
import os
from pathlib import Path
import platform


def data_dir():
    override = os.environ.get('ORCHID_STUDIO_DATA_DIR')
    if override:
        return Path(override).expanduser().resolve()
    project = Path(__file__).resolve().parents[2]
    if (project / 'pyproject.toml').is_file() and (project / 'local').is_dir():
        return project / 'local'
    if platform.system() == 'Darwin':
        return Path.home() / 'Library/Application Support/Orchid Studio'
    if platform.system() == 'Windows':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Orchid Studio'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'orchid-studio'


def host_path():
    override = os.environ.get('ORCHID_STUDIO_HOST')
    if override:
        return Path(override).expanduser().resolve()
    return data_dir() / 'Orchid Studio Pistil.app/Contents/MacOS/OrchidStudioPistil'
