"""Run the source edition in a browser; Ctrl+C stops the loopback service."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from prepare_private import ASSETS

ROOT = Path(__file__).resolve().parents[1]


def stage_source(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / 'src').rglob('*'):
        if path.is_file() and path.suffix in {'.py', '.js', '.css', '.html'} and '__pycache__' not in path.parts:
            target = destination / path.relative_to(ROOT / 'src')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    shutil.copy2(ROOT / 'private/catalog.json', destination / 'tactics_ui/catalog.json')


def check_inputs():
    needed = [ROOT / 'private/engine' / name for name in ASSETS]
    needed += [ROOT / 'private/catalog.json',
               ROOT / 'private/engine/fm27_native/FM27Simulator.exe',
               ROOT / 'private/engine/fm27_native/engine_compat_profile.json']
    missing = [str(path.relative_to(ROOT)) for path in needed if not path.is_file()]
    if missing:
        raise ValueError('Prepare private assets and build native first. Missing:\n' + '\n'.join(missing))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', required=True, type=Path)
    parser.add_argument('--port', type=int, default=18765)
    args = parser.parse_args()
    if os.name != 'nt' or sys.version_info[:2] != (3, 12):
        raise SystemExit('This source edition requires Windows x64 and Python 3.12.')
    check_inputs()
    source = ROOT / 'build/source'
    stage_source(source)
    data = ROOT / 'data'
    data.mkdir(exist_ok=True)
    env = {key: value for key, value in os.environ.items() if not key.startswith('FM27_')}
    env.update(FM27_ENGINE_ROOT=str(ROOT / 'private/engine'), FM27_GAME_ROOT=str(args.game_root.resolve()),
               FM27_DESKTOP_DATA=str(data), PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    print(f'Open http://127.0.0.1:{args.port} after the service reports ready.', flush=True)
    try:
        subprocess.run([sys.executable, str(source / 'desktop_server.py'), '--port', str(args.port)],
                       env=env, check=True)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
