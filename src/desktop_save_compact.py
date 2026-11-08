"""Bounded diagnostic reader for the observed revision-10 compact team table.

These records are partial tactical state, not complete simulator inputs. In
particular, the opaque suffix and phase headers must not be interpreted as
team/personal instructions or a cross-phase player permutation.
"""
import struct

REVISION = b'\x0a\0\0\0\0'
ROW_BYTES = 243
PROFILE = 'fm27-compact-counted-revision10-v1'


class CompactTableError(ValueError):
    pass


def read_table(data, count_offset):
    """Read exactly the declared u16 count; never resynchronize after a bad row."""
    if type(count_offset) is not int or count_offset < 0 or count_offset + 2 > len(data):
        raise CompactTableError('compact table count outside section')
    count = struct.unpack_from('<H', data, count_offset)[0]
    start = count_offset + 2
    end = start + count * ROW_BYTES
    if count == 0 or end > len(data):
        raise CompactTableError('compact table count exceeds section')
    rows = []
    teams = set()
    for index in range(count):
        at = start + index * ROW_BYTES
        row = data[at:at + ROW_BYTES]
        if row[:5] != REVISION or row[9] != 0:
            raise CompactTableError(f'unsupported compact row header at {at}')
        team, = struct.unpack_from('<I', row, 5)
        if team in teams:
            raise CompactTableError(f'duplicate compact team {team}')
        teams.add(team)
        phases = []
        headers = []
        for base in (14, 50):
            if row[base] != 3 or any(row[base + 3 + slot * 3] != 5 for slot in range(11)):
                raise CompactTableError(f'unsupported compact phase at {at + base}')
            headers.append(row[base:base + 3].hex())
            phases.append([struct.unpack_from('<H', row, base + 4 + slot * 3)[0] for slot in range(11)])
        rows.append({
            'record_offset': at, 'offset': at + 5, 'team_id': team,
            'opponent_team_id': struct.unpack_from('<I', row, 10)[0],
            'phase_headers': headers, 'packed_cells': phases,
            'player_selectors': list(struct.unpack_from('<26I', row, 86)),
            # Preserve this field without asserting shirt-number semantics.
            # In the old regex, its first byte was incorrectly required to be 1.
            'post_selector_bytes_hex': row[190:216].hex(),
            'opaque_tail_hex': row[216:].hex(),
            'complete_tactic': False, 'admitted_to_simulator': False,
        })
    return {'profile': PROFILE, 'count_offset': count_offset, 'count': count,
            'start': start, 'end': end, 'record_bytes': ROW_BYTES, 'records': rows,
            'admitted_to_simulator': False}


def find_table(data, preceding_team_ids, following_prefix=b'\x13\x00\x22\x44\x00'):
    """Locate a unique complete counted table, rather than isolated team hits.

    The following opaque prefix is an observed boundary control, not a decoded
    section header. Other formats require a separately verified profile.
    Only headers with room for the entire declared table are attempted. A row
    error rejects that candidate; no valid-looking subset is returned.
    """
    if not following_prefix:
        raise CompactTableError('a verified following boundary is required')
    if not preceding_team_ids or len(set(preceding_team_ids)) != len(preceding_team_ids):
        raise CompactTableError('independent preceding team references are required')
    prefix = struct.pack('<I', len(preceding_team_ids)) + b''.join(
        struct.pack('<I', team) + b'\0' for team in preceding_team_ids)
    found = []
    at = 2
    while True:
        at = data.find(REVISION, at)
        if at < 0:
            break
        count = struct.unpack_from('<H', data, at - 2)[0]
        end = at + count * ROW_BYTES
        if (count and at - 2 >= len(prefix) and
                data[at - 2 - len(prefix):at - 2] == prefix and
                data[end:end + len(following_prefix)] == following_prefix):
            try:
                candidate = read_table(data, at - 2)
            except CompactTableError:
                pass
            else:
                # A single coincidental row is not sufficient table evidence.
                if candidate['count'] >= 11:
                    found.append(candidate)
        at += len(REVISION)
    if len(found) != 1:
        raise CompactTableError(f'expected one complete compact table, found {len(found)}')
    return found[0]
