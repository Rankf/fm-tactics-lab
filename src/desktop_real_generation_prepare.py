"""Save-side fragments for real AI generation; no career TEAM table involved."""
import hashlib
import json
import sys
from pathlib import Path


def _human(folder):
    try:
        import desktop_generation_human
        return desktop_generation_human.export(folder)
    except Exception as error:
        return {'error':str(error)}


def prepare(source,folder):
    import desktop_save_compat
    desktop_save_compat.install()
    import fmsave
    from fmsave import _version
    from desktop_storage import bounded_output
    _version.FM27_FRAME_DECOMPRESSED_CAP=768*1024**2
    _version.FM27_TOTAL_DECOMPRESSED_CAP=1536*1024**2
    source=Path(source);folder=Path(folder);bounded_output(folder);folder.mkdir(parents=True,exist_ok=True)
    inputs=json.loads((folder/'generation_inputs.json').read_text(encoding='utf8'))
    if inputs['source_sha256']!=hashlib.sha256(Path(inputs['source']).read_bytes()).hexdigest():
        raise ValueError('来源存档已改变，请重新读取')
    target=folder/'staff_fragments';target.mkdir(exist_ok=True)
    rows=[]
    with fmsave.open(source)as save:
        with save._context.section('game_db')as db:
            for staff in inputs['staff']:
                profile=staff.get('generation_profile')
                if not profile:continue
                selector=staff.get('person_selector')
                if type(selector)is not int:continue
                header=profile['header_offset'];profile_offset=profile['profile_offset']
                start=header+13;end=profile_offset+52+4096
                if not (start<profile_offset<end<=len(db)):raise ValueError('教练档案边界无效')
                raw=bytes(db[start:end])
                (target/f'{selector}.bin').write_bytes(raw)
                rows.append({'person_selector':selector,'human':False,'uid':staff.get('uid'),
                    'profile_hex':profile['raw_52_bytes_hex'],'codes_hex':profile['formation_codes_hex'],
                    'raw_sha256':hashlib.sha256(raw).hexdigest()})
    human=_human(folder)
    human_row=None
    if 'error' not in human:
        selector=human['selector'];profile=human['profile']
        source_path=folder/'human_staff_fragments'/f'{selector}.bin'
        raw=source_path.read_bytes();(target/f'{selector}.bin').write_bytes(raw)
        human_row={'person_selector':selector,'human':True,'uid':human['native_uid'],
            'profile_hex':profile['raw_52_bytes_hex'],'codes_hex':profile['formation_codes_hex'],
            'raw_sha256':hashlib.sha256(raw).hexdigest()}
        rows.append(human_row)
    value={'source_sha256':inputs['source_sha256'],'rows':rows,'human_ready':human_row is not None,
           'human_error':human.get('error')}
    (folder/'staff_fragments.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    return {'source_sha256':value['source_sha256'],'fragments':len(rows),'human_ready':value['human_ready']}


if __name__=='__main__':
    print(json.dumps(prepare(sys.argv[1],sys.argv[2]),ensure_ascii=False),flush=True)
