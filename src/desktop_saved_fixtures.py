"""Exact stored TAC objects, explicitly distinguished from full-match AI inputs."""
import copy
import hashlib
import json
import os
import re
import subprocess
import desktop_static_plans
import sys
from functools import lru_cache
from pathlib import Path

PROFILE='saved-fixture-native-v1'

@lru_cache(maxsize=8)
def cached_read(path,mtime,size):
    return json.loads(path.read_text(encoding='utf8'))

def read(path):
    if path.name in {'dataset.json','saved_fixture_index.json','saved_player_selectors.json','player_index.json','club_registry.json'}:
        stat=path.stat()
        return cached_read(path,stat.st_mtime_ns,stat.st_size)
    return json.loads(path.read_text(encoding='utf8'))

def index(lib,folder):
    lib.check_binding(folder)
    data=read(folder/'dataset.json')
    receipt=folder/'saved_fixture_source.json'
    if not receipt.exists() or read(receipt).get('source_sha256')!=data['source_sha256'] or 'selectors_sha256' not in read(receipt):
        source=read(folder/'selected_source.json')['path'] if (folder/'selected_source.json').exists() else data['source']
        with (folder/'saved_fixture_export.log').open('wb') as log:
            p=subprocess.run([os.environ.get('FM27_SAVE_PYTHON',sys.executable),str(Path(__file__).with_name('desktop_save_worker.py')),source,str(folder),'--saved-tactics'],
                stdout=log,stderr=log,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW,env={**os.environ,'PYTHONUTF8':'1'})
        if p.returncode:raise ValueError('存档比赛记录导出失败，见 saved_fixture_export.log')
    source=read(receipt)
    for name,field in [('saved_fixture_section.bin','section_sha256'),('saved_player_selectors.json','selectors_sha256')]:
        if lib.app.desktop_engine.sha(folder/name)!=source[field]:raise ValueError('存档比赛记录或球员索引哈希不一致')
    binding=read(folder/'native_binding.json')
    stamp={'profile':PROFILE,'source':source,'engine':binding}
    cache=folder/'saved_fixture_index.json'
    if cache.exists():
        value=read(cache)
        if value.get('binding')==stamp:return value
    rows=lib.native([],folder,'saved_fixture_walk',{'FM27_SAVE_SECTION_PROBE':str(folder/'saved_fixture_section.bin')})
    endings=[r for r in rows if r.get('event')=='section_walk_end']
    if len(endings)!=1 or endings[0]['remaining']!=0 or endings[0]['offset']!=(folder/'saved_fixture_section.bin').stat().st_size:
        raise ValueError('存档比赛记录未通过原版读取器完整边界校验')
    records=[r for r in rows if r.get('event')=='saved_fixture_walked']
    value={'binding':stamp,'records':records}
    lib.write(cache,value)
    return value

def candidate_key(row,side):
    return 'stored:'+str(row['offset'])+':'+str(side)

def team(lib,key,candidate,side,own_team):
    if not re.fullmatch(r'stored:\d+:[01]',candidate) or type(side)is not int or side not in (0,1):raise ValueError('未知存储方案')
    folder=lib.folder(key)
    rows=index(lib,folder)['records']
    row=next((r for r in rows if candidate_key(r,side)==candidate),None)
    if row is None or not row['plans'][side]:raise ValueError('此存储方案不属于当前存档')
    selectors=read(folder/'saved_player_selectors.json')
    ids=[selectors.get(str(s)) for s in row['rosters'][side]]
    registry=lib.club_registry(folder,read(folder/'dataset.json'))
    tid=row['home_team_id' if side==0 else 'away_team_id']
    club=next((c for c in registry if any(t['team_id']==tid and t.get('slot')==0 for t in c['teams'])),None)
    if club is None:raise ValueError('方案未关联到唯一一线队')
    result=copy.deepcopy(lib.app.DEFAULT['teams'][1])
    lib.apply_plan(result,row['plans'][side])
    desktop_static_plans.roster(lib,key,club['uid'],result,ids)
    result.update(name=club.get('short_name') or club['name'],tactic_name='存档保存模板 '+str(row['offset']))
    # No opposition input exists in these TAC objects. Use an explicit neutral
    # policy rather than inheriting the unrelated carrier's opposition settings.
    neutral=lib.app.unpack_oi(0x80000)
    result['opposition']={'players':[copy.deepcopy(neutral) for _ in result['opposition']['players']],
        'positions':{p:copy.deepcopy(neutral) for p in result['opposition']['positions']}}
    own_index={p.get('source_uid'):i for i,p in enumerate(own_team['players'][:own_team.get('roster_size',26)]) if p.get('source_uid') is not None}
    other=[selectors.get(str(s)) for s in row['rosters'][1-side]]
    for cells in result['phases']:
        for cell in cells:
            target=cell['target_player']
            if target!=255:cell['target_player']=own_index.get(other[target],255) if target<len(other) else 255
    return result

def discover(lib,key,own,existing):
    folder=lib.folder(key);value=index(lib,folder)
    registry=lib.club_registry(folder,read(folder/'dataset.json'))
    clubs={t['team_id']:c for c in registry for t in c['teams'] if t.get('slot')==0}
    selectors=read(folder/'saved_player_selectors.json');players=read(folder/'player_index.json')
    options={};failures=[]
    for row in value['records']:
        for side in (0,1):
            club=clubs.get(row['home_team_id' if side==0 else 'away_team_id'])
            if club is None or club['uid'] in existing|{own} or club['uid'] in options or not row['plans'][side]:continue
            ids=[selectors.get(str(s)) for s in row['rosters'][side]]
            try:
                test=copy.deepcopy(lib.app.DEFAULT['teams'][1]);lib.apply_plan(test,row['plans'][side])
                options[club['uid']]=(row,side,club,ids)
            except ValueError:continue
    lib.write(folder/f'opponent_progress_{own}.json',{'stage':f'正在读取{len(options)}支新增球队的真实球员属性'})
    lib.ensure_rosters(folder,set(options))
    result=[]
    for uid,(row,side,club,ids) in options.items():
        candidate=candidate_key(row,side)
        try:
            decoded=team(lib,key,candidate,side,lib.app.DEFAULT['teams'][0])
            scenario=copy.deepcopy(lib.app.DEFAULT);scenario['teams'][1]=decoded;lib.app.validate_scenario(scenario)
            result.append({'key':candidate,'fixture_key':candidate,'club_uid':uid,'name':decoded['name'],'side':side,
                'member':'play_fixture_manager @'+str(row['offset']),'date':None,'available':True,'direct_fixture':False,
                'source_kind':'saved_template','roster_policy':'current_save_approximate','cache_roster_count':len(ids),'match_roster_count':decoded['roster_size'],
                'excluded_substitute_uids':ids[decoded['roster_size']:],
                'source':'存档保存模板：原版完整TAC含球队/个人指令和双阶段映射；非实战AI指令。名单使用当前球队近似阵容。对手针对性指令中立，定位球采用统一对战规则；日期未核实。'})
        except Exception as error:failures.append({'member':candidate,'club_uid':uid,'error':str(error)})
    return {'opponents':result,'records':len(value['records']),'failures':failures}
