"""Source-backed computer state graph. Lossy records never become full TACs."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from desktop_save_compact import read_table

PROFILE='native-counted-ai-state-v1'

def read(path):return json.loads(path.read_text(encoding='utf8'))

def inspect(lib,key):
    folder=lib.folder(key);data=read(folder/'dataset.json');receipt=folder/'ai_source.json'
    if not receipt.exists() or read(receipt).get('source_sha256')!=data['source_sha256']:
        source=read(folder/'selected_source.json')['path'] if (folder/'selected_source.json').exists() else data['source']
        with (folder/'ai_export.log').open('wb') as log:
            p=subprocess.run([os.environ.get('FM27_SAVE_PYTHON',sys.executable),str(Path(__file__).with_name('desktop_save_worker.py')),source,str(folder),'--ai-tactics'],
                env={**os.environ,'PYTHONUTF8':'1'},stdout=log,stderr=log,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
        if p.returncode:raise ValueError('电脑战术表导出失败，见 ai_export.log')
    source=read(receipt);section=folder/'ai_tactics_section.bin';selectors_path=folder/'ai_player_selectors.json'
    if lib.app.desktop_engine.sha(section)!=source['section_sha256'] or lib.app.desktop_engine.sha(selectors_path)!=source['selectors_sha256']:raise ValueError('电脑战术表或球员引用索引已改变')
    lib.check_binding(folder);binding={'profile':PROFILE,'source':source['source_sha256'],'section':source['section_sha256'],'engine':read(folder/'native_binding.json')}
    cache=folder/'ai_team_state_index.json'
    if cache.exists() and read(cache).get('binding')==binding:return read(cache)
    events=lib.native([],folder,'ai_table_walk',{'FM27_AI_TACTICS_SECTION':str(section)})
    complete=[e for e in events if e.get('event')=='ai_section_complete'];boundaries=[e for e in events if e.get('event')=='ai_table_boundary']
    if len(complete)!=1 or len(boundaries)!=1 or complete[0]['remaining'] or complete[0]['offset']!=section.stat().st_size:raise ValueError('电脑战术表未通过完整边界读取')
    boundary=boundaries[0];table=read_table(section.read_bytes(),boundary['offset'])
    if table['end']!=boundary['end'] or table['count']!=boundary['count']:raise ValueError('原生边界与结构化解析不一致')
    registry=lib.club_registry(folder,data);clubs={t['team_id']:{'club_uid':c['uid'],'unique_id':c['unique_id'],'team_slot':t['slot'],'name':c.get('short_name') or c['name']} for c in registry for t in c['teams']}
    selectors=read(selectors_path);full_refs=[e for e in events if e.get('event')=='ai_manager_team_ref']
    managers={}
    for m in source['managers']:
        if m['team_id'] is not None:managers.setdefault(m['team_id'],[]).append(m)
    for record in table['records']:
        record['club']=clubs.get(record['team_id']);record['opponent']=clubs.get(record['opponent_team_id'])
        record['players']=[{'selector':s,'unique_id':selectors.get(str(s)) if s not in (0,0xffffffff) else None,'empty':s in (0,0xffffffff)} for s in record['player_selectors']]
        record['managers']=managers.get(record['team_id'],[])
        record['full_plan_references']=[r for r in full_refs if r['team_id']==record['team_id']]
        record['unresolved_fields']=['personal_instruction_overrides','phase_player_permutation','full_team_instruction_bits']
    value={'binding':binding,'profile':PROFILE,'record_count':table['count'],'boundary':boundary,'complete_section':complete[0],
        'full_plan_references':full_refs,'records':table['records'],'admitted_to_simulator':False,
        'reason':'Original compact serialization is many-to-one: different valid PI overrides and phase permutations produce identical compact records.'}
    lib.write(cache,value);return value
