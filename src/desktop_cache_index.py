"""Conservative index of the observed native cache team-reference records.

Unknown versions, conflicting pairs and unresolved team links MUST fall back to
the original reader. This index excludes unrelated entries, never certifies a
tactic or replaces native deserialization of an admitted opponent.
"""
import re
from collections import defaultdict

PROFILE='paired-team-reference-v1'
HEADER=bytes.fromhex('03016d6b702e00001b0000004c00000275261f00')
PAIR=re.compile(rb'\x03\x02(?P<t0>.{4})\x02(?P<c0>.{4})\x00\x00\x01.{4}(?P=c0)\x00'
                rb'\x03\x02(?P<t1>.{4})\x02(?P<c1>.{4})\x00\x00\x01.{4}(?P=c1)\x00\x0b\x02',re.S)

def fixture_links(fixtures):
    links=defaultdict(set)
    for row in fixtures:
        for side in ('home','away'):
            team=row.get(side+'_team_id');club=row.get(side+'_club_uid')
            if type(team)is int and type(club)is int:links[team].add(club)
    return links

def references(payload):
    if not payload.startswith(HEADER):return None
    pairs={tuple(int.from_bytes(m[name],'little')for name in ('t0','c0','t1','c1'))for m in PAIR.finditer(payload)}
    if len(pairs)!=1:return None
    t0,c0,t1,c1=next(iter(pairs))
    if t0==t1 or c0==c1:return None
    return [(t0,c0),(t1,c1)]

def clubs(payload, links):
    refs=references(payload)
    if refs is None:return None
    (t0,c0),(t1,c1)=refs
    if links.get(t0)!={c0} or links.get(t1)!={c1}:return None
    return [c0,c1]
