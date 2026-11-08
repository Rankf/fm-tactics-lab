"""Read same-career neighbouring saves; identity and fixture anchors are required."""
import hashlib,json,os,subprocess,sys,re,shutil
from pathlib import Path
import desktop_cache_index
from desktop_save_worker import fixture_anchor

PROFILE='same-career-neighbour-saves-v1'
_cache={}

def read(path):return json.loads(path.read_text(encoding='utf8'))

def source_catalog(path):
    value=read(path) if path.exists() else {}
    return {key:[p for p in value.get(key,[]) if isinstance(p,str)] for key in ('saves','imports')}

def remember(lib,source=None,imported=None):
    path=lib.root/'source_catalog.json'
    with lib.lock:
        catalog=source_catalog(path)
        for kind,value in (('saves',source),('imports',imported)):
            if value is not None:
                resolved=str(Path(value).resolve())
                if resolved not in catalog[kind]:catalog[kind].append(resolved)
        lib.write(path,catalog)

def inventory(folder,data,library_root=None):
    source=Path(read(folder/'selected_source.json')['path'] if (folder/'selected_source.json').exists() else data['source'])
    files=sorted((p for p in source.parent.glob('*.fm') if p.resolve()!=source.resolve()),key=lambda p:p.stat().st_mtime_ns,reverse=True)[:8] if source.is_file() else []
    imports=[]
    if library_root is not None:
        path=library_root/'source_catalog.json';catalog=source_catalog(path)
        files.extend(Path(p) for p in catalog['saves'] if Path(p).is_file() and Path(p).resolve()!=source.resolve())
        imports=[Path(p) for p in catalog['imports'] if Path(p).is_file()]
        imports.extend(p/'dataset.json' for p in library_root.iterdir() if p.is_dir() and re.fullmatch('[0-9a-f]{16}',p.name) and (p/'dataset.json').exists())
    seen=set();result=[]
    for kind,paths in (('save',files),('imported',imports)):
        for path in paths:
            path=path.resolve()
            if str(path) in seen:continue
            seen.add(str(path))
            if kind=='imported':
                with path.open('rb') as stream:prefix=stream.read(8192)
                match=re.search(rb'"source_sha256"\s*:\s*"([0-9a-f]{64})"',prefix)
                if match is None or match[1].decode()==data['source_sha256']:continue
            stat=path.stat();result.append({'kind':kind,'path':str(path),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns})
    return result

def import_cached(lib,path,target,request,data):
    prior=read(path)
    if prior['build'].split('.')[0]!=data['build'].split('.')[0]:raise ValueError('不同代游戏的导入历史')
    people={(m['manager_staff_uid'],m['manager_name']) for m in prior['managed']}
    if not people.intersection(tuple(p) for p in request['human_identity']):raise ValueError('其他生涯的导入历史')
    anchors={fixture_anchor(f) for f in prior['fixtures']};anchors.discard(None)
    common=len(anchors.intersection(tuple(a) for a in request['anchors']))
    if common<3:raise ValueError('导入历史缺少独立比赛锚点')
    for entry in prior['caches']:
        if not re.fullmatch('[0-9a-f]{64}',entry['key']) or entry['path']!=entry['key']+'.pkm':raise ValueError('导入历史的输入路径无效')
        payload=path.parent/entry['path']
        if lib.app.desktop_engine.sha(payload)!=entry['key']:raise ValueError('导入历史输入已改变')
        shutil.copy2(payload,target/entry['path'])
    value={'profile':'same-career-match-source-v1','primary_sha256':data['source_sha256'],'source':prior['source'],'source_sha256':prior['source_sha256'],
        'date':prior['date'],'build':prior['build'],'human_identity':list(people),'matching_fixture_anchors':common,
        'clubs':prior['clubs'] if all('teams'in c and 'unique_id'in c for c in prior['clubs']) else lib.club_registry(target.parent.parent,data),
        'caches':prior['caches'],'warnings':[],'origin_kind':'prior_import','imported_dataset':str(path)}
    lib.write(target/'source.json',value)

def entries(lib,folder,data):
    source=Path(read(folder/'selected_source.json')['path'] if (folder/'selected_source.json').exists() else data['source'])
    catalog=inventory(folder,data,lib.root)
    cache_key=(str(folder),data['source_sha256'],json.dumps(catalog,sort_keys=True))
    if cache_key in _cache:return _cache[cache_key]
    candidates=catalog
    own={m['club_uid'] for m in data['managed']};anchors=[]
    for f in data['fixtures']:
        if not own.intersection((f.get('home_club_uid'),f.get('away_club_uid'))):continue
        anchor=fixture_anchor(f)
        if anchor is not None:anchors.append(anchor)
    request={'source_sha256':data['source_sha256'],'game':'FM'+data['build'].split('.')[0],
        'human_identity':[[m['manager_staff_uid'],m['manager_name']] for m in data['managed']],'anchors':anchors}
    results=[];audit=[];accepted={}
    for item in candidates:
        path=Path(item['path']);stat=path.stat();identity={'path':str(path),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns,'primary_sha256':data['source_sha256']}
        # A rolling backup must not overwrite an already imported date's proof.
        token=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20]
        target=folder/'recovery_sources'/token
        for previous in (folder/'recovery_sources').glob('*/identity.json'):
            if read(previous)==identity:target=previous.parent;break
        target.mkdir(parents=True,exist_ok=True)
        receipt=target/'source.json';stamp=target/'identity.json'
        if not stamp.exists() or read(stamp)!=identity or not receipt.exists():
            lib.write(target/'request.json',request)
            if item['kind']=='imported':
                try:import_cached(lib,path,target,request,data)
                except (OSError,ValueError,KeyError) as error:
                    audit.append({'source':str(path),'accepted':False,'error':str(error)});continue
                lib.write(stamp,identity);accepted[str(receipt)]=target;continue
            with (target/'reader.log').open('wb') as log:
                p=subprocess.run([os.environ.get('FM27_SAVE_PYTHON',sys.executable),str(Path(__file__).with_name('desktop_save_worker.py')),str(path),str(target),'--recovery-source',str(target/'request.json')],
                    stdout=log,stderr=log,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW,env={**os.environ,'PYTHONUTF8':'1'})
            if p.returncode:
                audit.append({'source':str(path),'accepted':False,'error':read(target/'selective_reader_error.json') if (target/'selective_reader_error.json').exists() else 'reader failed'});continue
            lib.write(stamp,identity)
        accepted[str(receipt)]=target
    # Retain verified immutable inputs when a rolling source is later replaced
    # or removed. Their original source hashes remain in the experiment.
    for receipt in (folder/'recovery_sources').glob('*/source.json'):
        saved=read(receipt)
        if saved.get('profile')== 'same-career-match-source-v1' and saved.get('primary_sha256')==data['source_sha256']:
            accepted[str(receipt)]=receipt.parent
    for receipt,target in accepted.items():
        saved=read(Path(receipt))
        if saved.get('primary_sha256')!=data['source_sha256'] or saved['build'].split('.')[0]!=data['build'].split('.')[0]:continue
        links=desktop_cache_index.fixture_links([])
        clubs=saved['clubs']
        if not all('teams'in c and 'unique_id'in c for c in clubs):clubs=lib.club_registry(folder,data)
        for club in clubs:
            for team in club['teams']:links[team['team_id']].add(club['unique_id'])
        audit.append({'source':saved['source'],'accepted':True,'source_sha256':saved['source_sha256'],'date':saved['date'],'anchors':saved['matching_fixture_anchors']})
        for entry in saved['caches']:
            payload=target/entry['path']
            if not re.fullmatch('[0-9a-f]{64}',entry['key']) or entry['path']!=entry['key']+'.pkm':
                audit.append({'source':saved['source'],'accepted':False,'error':'备份输入路径无效'});continue
            if not payload.is_file() or lib.app.desktop_engine.sha(payload)!=entry['key']:
                audit.append({'source':saved['source'],'accepted':False,'member':entry.get('member'),'error':'备份比赛缓存缺失或哈希不一致'});continue
            results.append({**entry,'path':str(payload.relative_to(folder)),
                'source_save':{'path':saved['source'],'sha256':saved['source_sha256'],'date':saved['date'],'build':saved['build']},
                'indexed_clubs':desktop_cache_index.clubs(payload.read_bytes(),links)})
    lib.write(folder/'recovery_source_audit.json',{'profile':PROFILE,'sources':audit})
    if len(_cache)>=4:_cache.clear()
    _cache[cache_key]=results
    return results
