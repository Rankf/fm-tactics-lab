"""Bounded static-save exports for source-backed original AI generation."""
import hashlib,json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).with_name('vendor')))


def fragments(folder):
    import desktop_save_compat;desktop_save_compat.install()
    import fmsave
    from fmsave import _version
    _version.FM27_FRAME_DECOMPRESSED_CAP=768*1024**2
    _version.FM27_TOTAL_DECOMPRESSED_CAP=1536*1024**2
    folder=Path(folder);d=json.loads((folder/'generation_inputs.json').read_text(encoding='utf8'))
    teams=json.loads((folder/'source_team_table.json').read_text(encoding='utf8'))['records']
    wanted={t['coach_person_reference']for t in teams};rows=[]
    target=folder/'staff_fragments';target.mkdir(exist_ok=True)
    source=Path(d['source']);before=source.stat()
    with source.open('rb')as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=d['source_sha256']:raise ValueError('Source changed before coaching fragment export')
    with fmsave.open(d['source'])as save:
        with save._context.section('game_db')as db:
            for s in d['staff']:
                if s['person_selector']not in wanted or s['is_human_manager']:continue
                p=s['generation_profile']
                if p is None:raise ValueError('Required AI coach profile unresolved')
                start=p['header_offset']+13;raw=bytes(db[start:p['profile_offset']+52+4096])
                (target/f"{s['person_selector']}.bin").write_bytes(raw)
                rows.append({'person_selector':s['person_selector'],'raw_sha256':hashlib.sha256(raw).hexdigest(),
                    'profile_hex':p['raw_52_bytes_hex'],'codes_hex':p['formation_codes_hex'],
                    'ability_and_reputation_words':list(struct.unpack_from('<5H',db,p['ability_offset']-6))})
    after=source.stat()
    if(before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Source changed during coaching fragment export')
    human=json.loads((folder/'human_staff_fragments.json').read_text(encoding='utf8'))
    if human['source_sha256']!=d['source_sha256']:raise ValueError('Human source mismatch')
    for row in human['rows']:
        raw=(folder/'human_staff_fragments'/f"{row['person_selector']}.bin").read_bytes()
        (target/f"{row['person_selector']}.bin").write_bytes(raw);rows.append(row)
    (folder/'staff_fragments.json').write_text(json.dumps({'source_sha256':d['source_sha256'],'rows':rows}),encoding='utf8')
    return len(rows)


def prepare(source,folder):
    from desktop_generation_inputs import export
    from desktop_generation_context import export as context
    from desktop_generation_human import export as human
    from desktop_storage import bounded_output
    folder=Path(folder);bounded_output(folder)
    result=export(source,folder);context(folder);human(folder)
    return {'source_sha256':result['source_sha256'],'staff':fragments(folder)}


if __name__=='__main__':print(json.dumps(prepare(sys.argv[1],sys.argv[2])),flush=True)
