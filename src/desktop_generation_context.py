"""Source identities for a fresh desktop duel, distinct from historical fixtures.

Save-local keys are retained for joins; only native database identities may enter
MATCH_TEAM. This export does not imply that rules/weather have been converted.
"""
import hashlib
import json
from pathlib import Path

PROFILE='source-duel-context-v1'


def collect(save,inputs,table):
    from desktop_save_worker import plain
    nations={n.nation_id:n.database_id for n in save.nations()}
    competition=next((plain(c)for c in save.competitions()if c.id==inputs['league']['competition_id']),None)
    if not competition or competition['database_id']is None:
        raise ValueError('League native competition identity unresolved')
    players={p['unique_id']:p for p in inputs['players']}
    rows=[]
    for t in table['records']:
        c=next(c for c in inputs['clubs']if any(v['team_id']==t['team_id']and v['slot']==0 for v in c['teams']))
        if c['unique_id']is None or c['nation_id']not in nations or c['fa_nation_id']not in nations:
            raise ValueError('Club native identity or nation unresolved')
        captains=[]
        for field in ('captain_person_reference','vice_captain_person_reference'):
            ref=t[field]
            uid=inputs['player_selectors'].get(str(ref))
            p=players.get(uid)
            captains.append({'reference':ref,'native_uid':uid if p and p['club_uid']==c['uid']else None,
                             'current_club_member':bool(p and p['club_uid']==c['uid'])})
        rows.append({'team_id':t['team_id'],'club_local_uid':c['uid'],'club_native_uid':c['unique_id'],
                     'team_native_uid':t['unique_id'],
                     'nation_local_id':c['nation_id'],'nation_native_uid':nations[c['nation_id']],
                     'fa_nation_native_uid':nations[c['fa_nation_id']],
                     'reputation':t['native_reputation'],'captains':captains})
    return {'profile':PROFILE,'source_sha256':inputs['source_sha256'],'date':inputs['date'],
            'competition':competition,'league':inputs['league'],'teams':rows,
            'context_complete':False,'pending':['native_match_rules','fresh_duel_environment','human_coach_conversion'],
            'admitted_to_desktop':False}


def export(folder):
    import desktop_save_compat
    desktop_save_compat.install()
    import fmsave
    from fmsave import _version
    from desktop_generation_team_table import from_save
    from desktop_storage import bounded_output
    _version.FM27_FRAME_DECOMPRESSED_CAP=768*1024**2
    _version.FM27_TOTAL_DECOMPRESSED_CAP=1536*1024**2
    folder=Path(folder);bounded_output(folder)
    inputs=json.loads((folder/'generation_inputs.json').read_text(encoding='utf8'))
    source=Path(inputs['source']);before=source.stat()
    with source.open('rb')as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=inputs['source_sha256']:raise ValueError('Source save changed; reimport required')
    wanted={t['team_id']for c in inputs['clubs']for t in c['teams']if t['slot']==0}
    with fmsave.open(source)as save:
        with save._context.section('game_db')as db:
            table=from_save(save,db,wanted)
            context=collect(save,inputs,table)
    after=source.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('Source changed during read')
    context['table']={k:table[k]for k in ('count','header_offset','end')}
    table['source_sha256']=digest
    (folder/'source_team_table.json').write_text(json.dumps(table,ensure_ascii=False),encoding='utf8')
    target=folder/'duel_context.json';temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(target)
    return {'source_sha256':digest,'clubs':len(context['teams']),'competition':context['competition'],
            'nation_native_uids':sorted({t['nation_native_uid']for t in context['teams']}),
            'table':context['table'],'context_complete':False}


if __name__=='__main__':
    import sys
    print(json.dumps(export(sys.argv[1]),ensure_ascii=False),flush=True)
