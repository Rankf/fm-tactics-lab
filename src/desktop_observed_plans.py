"""Explicitly imported native observations; never label them saved preset links."""
import copy,hashlib,json,re,struct
from pathlib import Path
import desktop_static_plans

PROFILE='observed-native-plan-v1'

def read(path):return json.loads(path.read_text(encoding='utf8'))

def inventory(folder):
    return [{'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted((folder/'observed_plans').glob('*.json'))]

def register(lib,key,capture,side,date,source_sha256):
    """Import an existing observation only after matching source/player identities."""
    folder=lib.folder(key);data=read(folder/'dataset.json');lib.check_binding(folder)
    if data['source_sha256']!=source_sha256:raise ValueError('采集方案与目标存档摘要不符')
    raw=Path(capture).read_bytes();digest=hashlib.sha256(raw).hexdigest();capture_data=json.loads(raw)
    if capture_data.get('origin')!='viewable_client+0xf8':raise ValueError('需要实际模拟对象的完整方案，不能使用赛前空白输入')
    original=next(t for t in capture_data['teams'] if t['side']==side)
    native_club=struct.unpack_from('<I',bytes.fromhex(original['head_hex']),0x2c)[0]
    registry=lib.club_registry(folder,data)
    clubs=[c for c in registry if c['unique_id']==native_club]
    if len(clubs)!=1:raise ValueError('采集球队未关联到唯一源球队')
    club=clubs[0]['uid'];owners=read(folder/'player_index.json')
    actors=[a['uid'] for a in original['actors']]
    if len(actors)<11 or len(set(actors))!=len(actors) or any(owners.get(str(u))!=club for u in actors):
        raise ValueError('采集球员身份未全部关联到当前球队')
    plan={k:copy.deepcopy(original['tactic'][k]) for k in ('team_bits','mentality','mapping','phases')}
    trial=copy.deepcopy(lib.app.DEFAULT['teams'][1]);lib.apply_plan(trial,plan)
    desktop_static_plans.roster(lib,key,club,trial,actors)
    scenario=copy.deepcopy(lib.app.DEFAULT);scenario['teams'][1]=trial;lib.app.validate_scenario(scenario)
    other=next(t for t in capture_data['teams'] if t['side']!=side)
    value={'profile':PROFILE,'source_sha256':source_sha256,'capture_sha256':digest,'origin':capture_data['origin'],
           'date':date,'club_uid':club,'native_club_uid':native_club,'plan':plan,'preferred_uids':actors,
           'opponent_uids':[a['uid']for a in other['actors']],
           'coach_uid':struct.unpack_from('<I',bytes.fromhex(original['manager_head_hex']),0x50)[0],
           'source_kind':'observed_native','preset_reference_proven':False,
           'engine_dll_sha256':lib.app.ENGINE_DLL_SHA256}
    destination=folder/'observed_plans';destination.mkdir(exist_ok=True)
    lib.write(destination/(digest+'.json'),value)
    return digest

def records(lib,key):
    folder=lib.folder(key);data=read(folder/'dataset.json');result=[]
    for path in sorted((folder/'observed_plans').glob('*.json')):
        row=read(path)
        if row.get('profile')!=PROFILE or row.get('source_sha256')!=data['source_sha256']:raise ValueError('实用采集方案来源不符')
        if row.get('engine_dll_sha256')!=lib.app.ENGINE_DLL_SHA256:raise ValueError('实用采集方案引擎版本不符')
        if path.stem!=row['capture_sha256']:raise ValueError('实用采集方案标识不符')
        result.append(row)
    return result

def opponents(lib,key,own):
    names={c['uid']:c.get('short_name')or c['name']for c in read(lib.folder(key)/'dataset.json')['clubs']}
    return [{'key':'observed:'+r['capture_sha256'],'fixture_key':'observed:'+r['capture_sha256'],
             'club_uid':r['club_uid'],'name':names[r['club_uid']],'side':0,'available':True,
             'source_kind':'observed_native','date':r['date'],'member':r['origin'],
             'source':'FM 实际比赛采集方案 · '+r['date']+'；静态复用，属性取当前存档，非预设引用恢复。',
             'cache_roster_count':len(r['preferred_uids']),'match_roster_count':min(23,len(r['preferred_uids'])),
             'excluded_substitute_uids':[],'preset_reference_proven':False}
            for r in records(lib,key) if r['club_uid']!=own]

def team(lib,key,candidate,own_team):
    if not re.fullmatch('observed:[0-9a-f]{64}',candidate):raise ValueError('无效实用方案标识')
    row=next((r for r in records(lib,key)if r['capture_sha256']==candidate.split(':')[1]),None)
    if row is None:raise ValueError('实用方案不属于当前存档')
    result=copy.deepcopy(lib.app.DEFAULT['teams'][1]);lib.apply_plan(result,row['plan'])
    desktop_static_plans.roster(lib,key,row['club_uid'],result,row['preferred_uids'])
    data=read(lib.folder(key)/'dataset.json');club=next(c for c in data['clubs']if c['uid']==row['club_uid'])
    result.update(name=club.get('short_name')or club['name'],tactic_name='实用采集方案 '+row['date'])
    neutral=lib.app.unpack_oi(0x80000)
    result['opposition']={'players':[copy.deepcopy(neutral)for _ in result['opposition']['players']],
                          'positions':{p:copy.deepcopy(neutral)for p in result['opposition']['positions']}}
    current={p.get('source_uid'):i for i,p in enumerate(own_team['players'][:own_team.get('roster_size',26)])if p.get('source_uid')is not None}
    for cells in result['phases']:
        for cell in cells:
            i=cell['target_player']
            if i!=255:cell['target_player']=current.get(row['opponent_uids'][i],255)if i<len(row['opponent_uids'])else 255
    return result
