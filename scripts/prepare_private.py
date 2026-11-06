"""Prepare ignored runtime inputs from an existing, user-owned tool workspace."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = (
    'fm27_native/editor_manual_default.json',
    'fm27_native/editor_advanced_snapshot.json',
    'fm27_native/editor_setpieces_default.json',
    'fm27_native/fixtures/match.pkm',
    'fm27_research/setpiece_enum_catalog.json',
)
RELEASE_SHA256 = 'b18594de3fcfecbb520e73c86555e122eb899dbadc2ff3402dd0f839329f1614'
PAYLOAD_SHA256 = '8ec66ee7528d0ad60161207b93fedee2ec5cf97dc73af9314d719c289070fc6d'


def prepare_release(executable):
    """Read the known release's embedded data without executing the EXE."""
    raw = Path(executable).read_bytes()
    if hashlib.sha256(raw).hexdigest() != RELEASE_SHA256:
        raise ValueError('Expected the original v1103.2 release EXE; SHA256 mismatch')
    start, end = raw.find(b'PK\x03\x04'), raw.rfind(b'PK\x05\x06')
    if start < 0 or end < start or end + 22 > len(raw):
        raise ValueError('Embedded payload not found')
    comment_size = struct.unpack_from('<H', raw, end + 20)[0]
    payload = raw[start:end + 22 + comment_size]
    if hashlib.sha256(payload).hexdigest() != PAYLOAD_SHA256:
        raise ValueError('Embedded payload checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [('engine/' + name, ROOT / 'private/engine' / name) for name in ASSETS]
        members.append(('source/tactics_ui/catalog.json', ROOT / 'private/catalog.json'))
        for name, _ in members:
            archive.getinfo(name)
        for name, target in members:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    print('Prepared local inputs from verified v1103.2 EXE; executable was not run.')


def prepare(source, catalog):
    source, catalog = Path(source).resolve(), Path(catalog).resolve()
    paths = [(source / name, ROOT / 'private/engine' / name) for name in ASSETS]
    paths.append((catalog, ROOT / 'private/catalog.json'))
    missing = [str(src) for src, _ in paths if not src.is_file()]
    if missing:
        raise ValueError('Missing private inputs:\n' + '\n'.join(missing))
    for src, _ in paths:
        if src.suffix == '.json':
            json.loads(src.read_text(encoding='utf-8-sig'))
    for src, dest in paths:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    print('Private inputs staged under private/. Do not publish this directory.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-exe', type=Path, help='Original v1103.2 EXE downloaded from Releases')
    parser.add_argument('--assets-root', type=Path,
                        help='Existing engine workspace, not the game installation')
    parser.add_argument('--catalog', type=Path,
                        help='Matching tactics_ui/catalog.json from that tool version')
    args = parser.parse_args()
    if args.release_exe:
        if args.assets_root or args.catalog:
            parser.error('Use --release-exe alone, or --assets-root together with --catalog')
        prepare_release(args.release_exe)
    elif args.assets_root and args.catalog:
        prepare(args.assets_root, args.catalog)
    else:
        parser.error('Provide --release-exe, or both --assets-root and --catalog')


if __name__ == '__main__':
    main()
