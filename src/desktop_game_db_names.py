"""Competition and nation display names from the FM27 installation's language database."""
from pathlib import Path
import hashlib
import json
import os
import struct
import time

BLOCK_MAGIC = b'\x03\x01tad.'
FRAME_MAGIC = b'\x28\xb5\x2f\xfd'
MAX_DECOMPRESSED_BYTES = 8 * 1024 ** 2
MAX_TEXT_BYTES = 4096
MIN_OVERLAP_RATIO = 0.5
CACHE_DIRECTORY = 'game_db_names'
NATION_FIELDS = (0xff, 0xff, None, 0x00)
COMPETITION_FIELDS = (0xff, 0xff, 0x00)
# Every record starts with the id, then its text fields: nations
# (name, short name, code, adjective), competitions (name, short name, code).
NAME_FIELD = 0


def _unavailable(detail):
    return {'competitions': {}, 'nations': {}, 'source': 'unavailable', 'detail': detail}


def _zstd():
    try:
        from backports import zstd
        return zstd
    except (ImportError, RuntimeError):
        pass
    try:
        from fmsave._container import zstd
        return zstd
    except ImportError:
        from compression import zstd
        return zstd


def _ids(values):
    return {value for value in values or () if type(value) is int}


def _read_text(stream, offset, terminator):
    if offset + 4 > len(stream):
        raise ValueError('名称表在字段长度前被截断')
    length = struct.unpack_from('<I', stream, offset)[0]
    offset += 4
    end = offset + length
    if length > MAX_TEXT_BYTES:
        raise ValueError('名称表文本长度异常')
    if end > len(stream):
        raise ValueError('名称表在字段文本中被截断')
    try:
        value = stream[offset:end].decode('utf8')
    except UnicodeDecodeError as error:
        raise ValueError('名称表文本不是 UTF-8') from error
    offset = end
    if terminator is not None:
        if offset >= len(stream):
            raise ValueError('名称表在字段终止符前被截断')
        if stream[offset] != terminator:
            raise ValueError('名称表字段终止标记异常')
        offset += 1
    return value, offset


def _read_block(stream, offset, fields):
    if offset + 12 > len(stream):
        raise ValueError('名称表块头被截断')
    if stream[offset:offset + 6] != BLOCK_MAGIC:
        raise ValueError('名称表块标记异常')
    offset += 8  # block magic and u16 schema
    count = struct.unpack_from('<I', stream, offset)[0]
    offset += 4
    if count < 1 or count * 12 > len(stream) - offset:
        raise ValueError('名称表记录数异常')
    records = []
    for _ in range(count):
        if offset + 4 > len(stream):
            raise ValueError('名称表在记录 id 前被截断')
        record_id = struct.unpack_from('<I', stream, offset)[0]
        offset += 4
        values = []
        for terminator in fields:
            value, offset = _read_text(stream, offset, terminator)
            values.append(value)
        records.append((record_id, values))
    return records, offset


def _overlap(names, requested):
    if not requested:
        return 1.0
    return len(names & requested) / len(requested)


def _require_overlap(records, requested, label):
    ratio = _overlap({record_id for record_id, _ in records}, requested)
    if ratio < MIN_OVERLAP_RATIO:
        # A shifted or misread table parses as unrelated u32 ids, so the save's
        # editor ids practically never overlap one that is not the expected table.
        raise ValueError(f'{label}名称表与存档 database_id 重叠不足（{ratio:.0%}）')


def parse_name_tables(stream, competition_ids, nation_ids):
    """Read the nations and competitions blocks, keeping only the requested ids.

    Raises:
        ValueError: The stream is truncated, malformed, or its ids do not come
            from the tables the save's database ids are keyed on.
    """
    competition_ids = _ids(competition_ids)
    nation_ids = _ids(nation_ids)
    start = stream.find(BLOCK_MAGIC)
    if start < 0:
        raise ValueError('名称表块标记缺失')
    nations, offset = _read_block(stream, start, NATION_FIELDS)
    competitions, _ = _read_block(stream, offset, COMPETITION_FIELDS)
    _require_overlap(nations, nation_ids, '国家')
    _require_overlap(competitions, competition_ids, '比赛')
    return {'competitions': {record_id: values[NAME_FIELD] for record_id, values in competitions if record_id in competition_ids},
            'nations': {record_id: values[NAME_FIELD] for record_id, values in nations if record_id in nation_ids}}


def _decompress_frames(raw, limit):
    zstd = _zstd()
    view = memoryview(raw)
    chunks = []
    total = 0
    offset = 0
    while total < limit:
        offset = raw.find(FRAME_MAGIC, offset)
        if offset < 0:
            break
        try:
            size = zstd.get_frame_size(view[offset:])
            if size <= 0 or offset + size > len(raw):
                raise ValueError('invalid frame size')
            data = zstd.ZstdDecompressor().decompress(view[offset:offset + size], max_length=limit - total)
        except Exception:
            # A frame that does not decode is skipped; the next magic is tried.
            offset += 1
            continue
        chunks.append(data)
        total += len(data)
        offset += size
    return b''.join(chunks)


def _lang_db_path(game_root):
    if not game_root:
        return None
    database = Path(game_root) / 'shared/data/database/db'
    try:
        folders = list(database.iterdir())
    except OSError:
        return None
    candidates = []
    for folder in folders:
        try:
            version = int(folder.name)
        except ValueError:
            continue
        path = folder / (folder.name + '_fm') / 'lang_db.dat'
        if path.is_file():
            candidates.append((version, path))
    return max(candidates)[1] if candidates else None


def _file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _cache_key(digest, competition_ids, nation_ids):
    selection = json.dumps([sorted(competition_ids), sorted(nation_ids)], separators=(',', ':'))
    return f"{digest[:16]}-{hashlib.sha256(selection.encode('utf8')).hexdigest()[:16]}.json"


def _cache_directory(cache_root):
    root = cache_root if cache_root is not None else os.environ.get('FM27_DESKTOP_DATA')
    return Path(root) / CACHE_DIRECTORY if root else None


def _int_map(value):
    if not isinstance(value, dict):
        return None
    result = {}
    for key, name in value.items():
        if not isinstance(name, str):
            return None
        try:
            result[int(key)] = name
        except (TypeError, ValueError):
            return None
    return result


def _read_cache(path):
    try:
        value = json.loads(path.read_text(encoding='utf8'))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict) or value.get('source') != 'game_db':
        return None
    competitions = _int_map(value.get('competitions'))
    nations = _int_map(value.get('nations'))
    if competitions is None or nations is None:
        return None
    return {'competitions': competitions, 'nations': nations, 'source': 'game_db',
            'detail': str(value.get('detail') or '')}


def _write_cache(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf8')
    for attempt in range(21):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 20:
                raise
            time.sleep(.025)


def resolve(game_root, competition_database_ids, nation_database_ids, cache_root=None):
    """Return the names of the requested database ids, or empty maps when unavailable.

    cache_root is the desktop data root (FM27_DESKTOP_DATA by default); results
    are cached under its game_db_names directory and keyed on the language
    database's content and the requested id sets.
    """
    try:
        competition_ids = _ids(competition_database_ids)
        nation_ids = _ids(nation_database_ids)
        path = _lang_db_path(game_root)
        if path is None:
            return _unavailable('未找到 FM27 游戏安装数据库 lang_db.dat')
        digest = _file_digest(path)
        directory = _cache_directory(cache_root)
        cache = directory / _cache_key(digest, competition_ids, nation_ids) if directory else None
        if cache is not None:
            cached = _read_cache(cache)
            if cached is not None:
                return cached
        names = parse_name_tables(_decompress_frames(path.read_bytes(), MAX_DECOMPRESSED_BYTES),
                                  competition_ids, nation_ids)
        result = {'competitions': names['competitions'], 'nations': names['nations'], 'source': 'game_db',
                  'detail': f'FM27 {path.parent.parent.name}/lang_db.dat'}
        if cache is not None:
            try:
                _write_cache(cache, result)
            except OSError:
                pass
        return result
    except Exception as error:
        return _unavailable(str(error) or error.__class__.__name__)
