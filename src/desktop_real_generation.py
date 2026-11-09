"""Real AI tactics: save coach fragments feed the original engine's AI preparation."""
import copy
import hashlib
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import desktop_generation_protocol

PROFILE='source-direct-duel-v1'
FRAGMENTS='staff_fragments'
MANAGER_JOB=16
MAX_ROSTER=23


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def folder(lib,key):
    return lib.folder(key)/'real_generation'


def _python():
    return os.environ.get('FM27_SAVE_PYTHON') or sys.executable


def _source(lib,key):
    root=lib.folder(key)
    selected=root/'selected_source.json'
    return read(selected)['path'] if selected.exists() else read(root/'dataset.json')['source']


def _run(script,args,log_path,timeout):
    command=[_python(),str(Path(__file__).with_name(script)),*[str(value)for value in args]]
    with log_path.open('wb')as stream:
        return subprocess.run(command,env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'},
            stdout=stream,stderr=stream,timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def ensure(lib,key):
    """Prepared league coaches and players, cached by save digest."""
    root=lib.folder(key);data=lib.index_data(root);out=folder(lib,key);out.mkdir(parents=True,exist_ok=True)
    source=_source(lib,key)
    with Path(source).open('rb')as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=data['source_sha256']:
            raise ValueError('来源存档已更新，请重新读取存档后再生成真实AI战术')
    inputs=out/'generation_inputs.json'
    usable=False
    if inputs.exists():
        try:usable=read(inputs).get('source_sha256')==data['source_sha256']
        except (OSError,ValueError):usable=False
    if not usable:
        result=_run('desktop_generation_inputs.py',(source,out),out/'inputs.log',300)
        if result.returncode:raise ValueError('真实AI战术源数据准备失败，见 real_generation/inputs.log')
    fragments=out/'staff_fragments.json'
    usable=False
    if fragments.exists():
        try:usable=read(fragments).get('source_sha256')==data['source_sha256']
        except (OSError,ValueError):usable=False
    if not usable:
        result=_run('desktop_real_generation_prepare.py',(source,out),out/'prepare.log',300)
        if result.returncode:raise ValueError('真实AI战术教练档案准备失败，见 real_generation/prepare.log')
    expected=read(fragments)
    if not expected.get('human_ready'):
        raise ValueError('你的主教练档案无法从存档定位：'+str(expected.get('human_error')or'未知原因'))
    stamp={'source_sha256':data['source_sha256'],'fragments_sha256':hashlib.sha256(fragments.read_bytes()).hexdigest()}
    cache=out/'staff_native.json'
    if cache.exists():
        try:
            value=read(cache)
            if value.get('binding')==stamp:return {'inputs':read(inputs),'staff':value['staff'],'staff_native_binding':stamp}
        except (OSError,ValueError):pass
    rows=lib.native([],root,'real_generation_staff',{'FM27_STAFF_FRAGMENT_DIRECTORY':str(out/FRAGMENTS)})
    native={str(row['selector']):row for row in rows if row.get('event')=='staff_body_read'}
    staff={}
    for row in expected['rows']:
        selector=str(row['person_selector']);entry=native.get(selector)
        if not entry or not entry.get('accepted') or entry.get('error'):
            raise ValueError('教练档案未通过原版读回：'+selector)
        if entry['profile_hex']!=row['profile_hex'] or entry['native_d4_to_f4_hex'][22:38]!=row['codes_hex']:
            raise ValueError('教练档案与原版读回不一致：'+selector)
        staff[selector]={'profile_hex':entry['profile_hex'],'native_d4_to_f4_hex':entry['native_d4_to_f4_hex'],
            'generation_trait_pairs':entry['generation_trait_pairs'],'human':bool(row.get('human')),'uid':row.get('uid')}
    lib.write(cache,{'binding':stamp,'staff':staff})
    return {'inputs':read(inputs),'staff':staff,'staff_native_binding':stamp}


def manager(inputs,club_uid,human):
    rows=[s for s in inputs.get('staff')or [] if s.get('club_uid')==club_uid
          and (s.get('job')or {}).get('raw')==MANAGER_JOB and s.get('has_contract')
          and bool(s.get('is_human_manager'))==bool(human)]
    rows.sort(key=lambda s:(0 if s.get('team_slot')==0 else 1,s.get('uid')or 0))
    return rows[0] if rows else None


def roster(inputs,club_uid):
    players=[p for p in inputs.get('players')or [] if p.get('club_uid')==club_uid and p.get('unique_id') is not None]
    if len(players)<11:raise ValueError('球队不足11名已解析球员')
    players.sort(key=lambda p:(-(p.get('ability')or {}).get('current')or 0,p.get('unique_id')or 0))
    chosen=players[:MAX_ROSTER]
    if not any(is_goalkeeper(p) for p in chosen):
        keepers=[p for p in players if is_goalkeeper(p)]
        if not keepers:raise ValueError('球队没有可确认的门将')
        chosen=chosen[:-1]+[keepers[0]]
    return chosen


def is_goalkeeper(player):
    return (player.get('positions')or {}).get('gk',0)>=14


def _team(lib,side,name,players,tactic_name):
    result=copy.deepcopy(lib.app.DEFAULT['teams'][side])
    for index,player in enumerate(players):
        values,profile=lib.player_values(player)
        result['players'][index].update(name=player.get('name'),source_uid=player.get('unique_id'),
            attributes=values,native_profile=profile)
    for slot in range(len(players),len(result['players'])):
        result['players'][slot].pop('source_uid',None)
        result['players'][slot]['name']='未入比赛名单'
    result.update(name=name,tactic_name=tactic_name,lineup=list(range(11)),roster_size=len(players),
        captains=[],takers={key:[]for key in lib.app.TAKER_KEYS})
    return result


def _side_record(inputs,club,coach,native,human,players):
    nation=(inputs.get('nations')or {}).get(str(club.get('nation_id')))
    if type(nation)is not int:raise ValueError('球队国家原生编号缺失')
    profile=bytes.fromhex(native['profile_hex'])
    extra=bytes.fromhex(native['native_d4_to_f4_hex'])
    codes=extra[11:19]
    personality=coach['personality']
    traits=native['generation_trait_pairs']
    influence=75 if human else 75+struct.unpack_from('<H',extra,6)[0]//10+max(1,min(20,(profile[51]+2)//5))
    uids=[player['unique_id']for player in players]
    record=bytearray(struct.pack('<4I',int(club['unique_id']),int(coach['unique_id']),
        int(club.get('reputation')or 0),len(uids)))
    record+=profile
    record+=bytes(codes[index]for index in (0,1,3,2,4,5,7,6))
    record+=bytes(int(personality[key])for key in ('professionalism','loyalty','sportsmanship','temperament','pressure','ambition','adaptability'))
    record+=bytes([int(coach['age'])])
    record+=struct.pack('<23I',*(uids+[0]*(MAX_ROSTER-len(uids))))
    record+=extra[:10]+extra[26:33]+bytes([influence])+struct.pack('<H',len(traits))
    record+=bytes(value for pair in traits for value in pair)
    if len(record)>272:raise ValueError('教练参数与名单超出原生生成容量')
    record+=bytes(272-len(record))
    record+=struct.pack('<4I',1 if human else 0,nation,0xffffffff,0xffffffff)
    return record


def preview(lib,key,own_club,opponent_club):
    prepared=ensure(lib,key)
    inputs=prepared['inputs'];staff=prepared['staff']
    own_club=int(own_club);opponent_club=int(opponent_club)
    clubs={club['uid']:club for club in inputs.get('clubs')or []}
    if own_club not in clubs or opponent_club not in clubs:
        raise ValueError('所选球队不在你当前执教的联赛，无法读取当前教练与名单')
    own_coach=manager(inputs,own_club,True)
    opponent_coach=manager(inputs,opponent_club,False)
    if own_coach is None:raise ValueError('存档中缺少玩家主教练')
    if opponent_coach is None:raise ValueError('该队缺少可核实的现任主教练')
    own_native=staff.get(str(own_coach.get('person_selector')))
    opponent_native=staff.get(str(opponent_coach.get('person_selector')))
    if own_native is None or opponent_native is None:raise ValueError('双方主教练档案尚未通过原版读回')
    own_players=roster(inputs,own_club)
    opponent_players=roster(inputs,opponent_club)
    payload=bytearray(b'FM27DUL1')
    payload+=_side_record(inputs,clubs[own_club],own_coach,own_native,True,own_players)
    payload+=_side_record(inputs,clubs[opponent_club],opponent_coach,opponent_native,False,opponent_players)
    own_team=_team(lib,0,clubs[own_club].get('short_name')or clubs[own_club].get('name')or'你的球队',own_players,'我的球队 · 真实AI战术预览')
    opponent_team=_team(lib,1,clubs[opponent_club].get('short_name')or clubs[opponent_club].get('name')or'对手',opponent_players,'本场原生AI生成')
    scenario=copy.deepcopy(lib.app.DEFAULT);scenario['teams']=[own_team,opponent_team]
    scenario['native_generation']={'profile':desktop_generation_protocol.PROFILE,'payload_hex':payload.hex()}
    config=lib.app.encode_scenario(scenario,absolute=True)
    digest=hashlib.sha256(config).hexdigest()
    root=folder(lib,key);cfg=root/f'preview_{digest[:16]}.bin';cfg.write_bytes(config)
    name='real_generation_preview_'+digest[:16]
    rows=lib.native(['--fixture',str(lib.app.ROOT/'fm27_native/fixtures/match.pkm'),
        '--scenario-file',str(cfg),'--seed','0','--inspect-fixture'],lib.folder(key),name)
    plans=[row for row in rows if row.get('event')=='source_generation_readback']
    if len(plans)!=2:raise ValueError('原版引擎未返回完整的双方战术回读，见 '+name+'.jsonl')
    plan=next(row for row in plans if row.get('side')==1)
    lib.apply_plan(opponent_team,plan)
    indices={player.get('source_uid'):index for index,player in enumerate(opponent_team['players'][:opponent_team['roster_size']])}
    try:opponent_team['lineup']=[indices[uid]for uid in plan['lineup_source_uids']]
    except KeyError:raise ValueError('原版战术首发与名单不一致')
    return {'team':opponent_team,'native_plan':plan,
        'payload_sha256':hashlib.sha256(payload).hexdigest(),'config_sha256':digest,
        'own_club':own_club,'opponent_club':opponent_club,
        'own_coach':own_coach.get('name'),'opponent_coach':opponent_coach.get('name'),
        'own_roster':[player['unique_id']for player in own_players],
        'opponent_roster':[player['unique_id']for player in opponent_players]}
