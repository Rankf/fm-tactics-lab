import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import desktop_coach_presets
import desktop_save_export
import desktop_save_mode
import fm27_fmf

SOURCE={'save_id':'0123456789abcdef','source':'C:/saves/career.fm','source_sha256':'a'*64,
        'date':'2027-01-15','build':'27.1.0'}
TAC_PLAN_HEADER=b'\x22'+struct.pack('<H',68)+b'\x1b'

def sample_plan(seed,size=96):
    base=hashlib.sha256(str(seed).encode()).digest()
    return TAC_PLAN_HEADER+(base*((size+len(base)-1)//len(base)))[:size]

def archive(seed,name='战术',size=96):
    return fm27_fmf.tactics_archive(sample_plan(seed,size),name)

def item(club_uid,club,target,tactic_name,payload,report=None):
    return {'club_uid':club_uid,'club':club,'target':target,'tactic_name':tactic_name,
            'payload':payload,'report':report or {'native_roundtrip_verified':True}}

class FmfPlanTests(unittest.TestCase):
    def test_roundtrip_preserves_plan_across_block_boundaries(self):
        for size in [1,7,8,100,65535,65536,65537,200000]:
            plan=sample_plan(size,size)
            self.assertEqual(fm27_fmf.tactics_plan(fm27_fmf.tactics_archive(plan,'测试战术')),plan)

    def test_rejects_invalid_archives(self):
        payload=archive(1)
        start=len(fm27_fmf.HEADER)+17;content=start+12
        cases=[('bytes', 'not bytes'),('short',payload[:20]),('magic',b'\x00'+payload[1:]),
               ('content',payload[:content]+bytes([payload[content]^1])+payload[content+1:]),
               ('truncated',payload[:-1])]
        for label,value in cases:
            with self.subTest(label=label),self.assertRaises(ValueError):
                fm27_fmf.tactics_plan(value)

    def test_rejects_declared_content_size_mismatch(self):
        payload=bytearray(archive(2));start=len(fm27_fmf.HEADER)+17
        struct.pack_into('<I',payload,start+5,len(sample_plan(2))+1)
        with self.assertRaises(ValueError):fm27_fmf.tactics_plan(bytes(payload))

class SafeComponentTests(unittest.TestCase):
    def test_replaces_windows_illegal_characters(self):
        value=desktop_save_export.safe_component('a<b>c:d"e/f\\g|h?i*j','球队1')
        self.assertFalse(any(c in value for c in '<>:"/\\|?*'))
        self.assertEqual(value,'a_b_c_d_e_f_g_h_i_j')

    def test_fallback_for_empty_or_traversal_names(self):
        for value in ['',None,'   ','...','..','/','..\\..']:
            self.assertTrue(desktop_save_export.safe_component(value,'球队9'))
        self.assertNotIn('/',desktop_save_export.safe_component('../../evil','球队1'))
        self.assertNotIn('\\',desktop_save_export.safe_component('..\\..\\evil','球队1'))

    def test_reserved_device_names_are_prefixed(self):
        for name in ['CON','con','PRN','NUL','COM1','LPT9','CON.fmf']:
            value=desktop_save_export.safe_component(name,'球队1')
            self.assertEqual(value[0],'_')
            self.assertNotIn(value.split('.',1)[0].casefold(),{'con','prn','aux','nul'})

    def test_trims_edges_and_limits_length(self):
        self.assertEqual(desktop_save_export.safe_component(' 战术. ','球队1'),'战术')
        self.assertLessEqual(len(desktop_save_export.safe_component('战术'*100,'球队1')),60)

class ExportWriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_root=ROOT/'build/test-temp';cls.temp_root.mkdir(parents=True,exist_ok=True)

    def setUp(self):
        self.holder=tempfile.TemporaryDirectory(dir=self.temp_root);self.base=Path(self.holder.name)

    def tearDown(self):
        self.holder.cleanup()

    def test_writes_files_manifest_and_embedded_plans(self):
        items=[item(1,'甲队','stored:0','控球',archive(1)),
               item(1,'甲队','stored:1','反击',archive(2)),
               item(2,'乙队','coach:77','高压',archive(3))]
        result=desktop_save_export.write(self.base,SOURCE,items)
        root=Path(result['directory'])
        self.assertEqual(root.parent,self.base.resolve())
        self.assertRegex(root.name,r'^FM27存档战术-\d{8}-\d{6}$')
        self.assertEqual(result['profile'],'saved-tactic-export-v1')
        self.assertEqual(result['failures'],[])
        self.assertEqual(len(result['files']),3)
        self.assertTrue((root/'甲队'/'控球.fmf').is_file())
        self.assertTrue((root/'甲队'/'反击.fmf').is_file())
        self.assertTrue((root/'乙队'/'高压.fmf').is_file())
        self.assertTrue((root/'导出说明.txt').is_file())
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf8'))
        self.assertEqual(manifest['profile'],result['profile'])
        self.assertEqual(manifest['source'],SOURCE)
        self.assertEqual(manifest['files'],result['files'])
        self.assertTrue(manifest['created']and manifest['notice'])
        plans={0:sample_plan(1),1:sample_plan(2),2:sample_plan(3)}
        for index,entry in enumerate(result['files']):
            written=(root/entry['file']).read_bytes()
            self.assertEqual(hashlib.sha256(written).hexdigest(),entry['sha256'])
            self.assertEqual(len(written),entry['size'])
            self.assertEqual(entry['plan_sha256'],hashlib.sha256(plans[index]).hexdigest())
            self.assertEqual(entry['plan_size'],len(plans[index]))
            self.assertEqual(fm27_fmf.tactics_plan(written),plans[index])
            self.assertTrue(entry['report']['native_roundtrip_verified'])
        self.assertEqual({e['target'] for e in result['files']},{'stored:0','stored:1','coach:77'})

    def test_duplicate_names_and_club_folders_are_deduplicated(self):
        items=[item(1,'同队','stored:0','Tactic',archive(1)),
               item(1,'同队','stored:1','tactic',archive(2)),
               item(1,'同队','stored:2','TACTIC',archive(3)),
               item(2,'同队','coach:9','Tactic',archive(4))]
        result=desktop_save_export.write(self.base,SOURCE,items)
        root=Path(result['directory'])
        self.assertTrue((root/'同队'/'Tactic.fmf').is_file())
        self.assertTrue((root/'同队'/'tactic2.fmf').is_file())
        self.assertTrue((root/'同队'/'TACTIC3.fmf').is_file())
        self.assertTrue((root/'同队2'/'Tactic.fmf').is_file())
        names=[e['file'] for e in result['files'] if e['club_uid']==1]
        self.assertEqual(len({name.casefold()for name in names}),3)

    def test_export_directory_gets_numeric_suffix(self):
        with mock.patch.object(desktop_save_export,'_stamp',return_value='20260101-120000'):
            first=desktop_save_export.write(self.base,SOURCE,[item(1,'甲队','stored:0','控球',archive(1))])
            second=desktop_save_export.write(self.base,SOURCE,[item(1,'甲队','stored:0','控球',archive(1))])
        self.assertEqual(Path(first['directory']).name,'FM27存档战术-20260101-120000')
        self.assertEqual(Path(second['directory']).name,'FM27存档战术-20260101-120000-2')

    def test_symlinked_export_directory_is_not_followed(self):
        if not hasattr(Path,'symlink_to'):self.skipTest('当前平台不支持符号链接')
        outside=self.base/'external';outside.mkdir()
        with mock.patch.object(desktop_save_export,'_stamp',return_value='20260101-130000'):
            (self.base/'FM27存档战术-20260101-130000').symlink_to(outside,target_is_directory=True)
            try:result=desktop_save_export.write(self.base,SOURCE,[item(1,'甲队','stored:0','控球',archive(1))])
            except OSError:self.skipTest('当前平台不允许创建符号链接')
        self.assertEqual(Path(result['directory']).name,'FM27存档战术-20260101-130000-2')
        self.assertEqual(list(outside.iterdir()),[])

    def test_rejects_invalid_payload_without_leaving_output(self):
        payload=bytearray(archive(1));payload[0]=0
        with self.assertRaises(ValueError):
            desktop_save_export.write(self.base,SOURCE,[item(1,'甲队','stored:0','控球',bytes(payload))])
        self.assertEqual(list(self.base.iterdir()),[])

    def test_rejects_more_than_max_files(self):
        items=[item(1,'甲队',f'stored:{i}',f'战术{i}',archive(i)) for i in range(desktop_save_export.MAX_FILES+1)]
        with self.assertRaises(ValueError):desktop_save_export.write(self.base,SOURCE,items)
        self.assertEqual(list(self.base.iterdir()),[])

    def test_rejects_missing_or_relative_directory(self):
        with self.assertRaises(ValueError):
            desktop_save_export.write(self.base/'missing',SOURCE,[item(1,'甲队','stored:0','控球',archive(1))])
        with self.assertRaises(ValueError):
            desktop_save_export.write('relative/path',SOURCE,[item(1,'甲队','stored:0','控球',archive(1))])

    def test_escaped_names_stay_inside_export_directory(self):
        items=[item(1,'..\\..\\逃逸','stored:0','../../evil',archive(1))]
        result=desktop_save_export.write(self.base,SOURCE,items)
        root=Path(result['directory']).resolve()
        self.assertEqual([p.name for p in self.base.iterdir()],[root.name])
        self.assertFalse((self.base.parent/'evil.fmf').exists())
        for path in root.rglob('*'):
            self.assertTrue(str(path.resolve()).startswith(str(root)))

    def test_cleans_up_when_writing_fails(self):
        real=desktop_save_export._atomic;calls=[]
        def failing(path,payload):
            calls.append(path)
            if len(calls)==2:raise OSError('磁盘写入失败')
            return real(path,payload)
        with mock.patch.object(desktop_save_export,'_atomic',side_effect=failing):
            with self.assertRaises(OSError):
                desktop_save_export.write(self.base,SOURCE,[item(1,'甲队','stored:0','控球',archive(1)),
                    item(1,'甲队','stored:1','反击',archive(2))])
        self.assertEqual(list(self.base.iterdir()),[])


class _Engine:
    def sha(self,path):return hashlib.sha256(str(path).encode()).hexdigest()

class _App:
    def __init__(self,root):
        self.RUNS=root/'runs';self.RUNS.mkdir(parents=True)
        self.NATIVE=root/'native';self.NATIVE.mkdir()
        self.desktop_engine=_Engine();self.ENGINE_COMPATIBILITY={'resource_fingerprint':'test'}

class SaveLibraryExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_root=ROOT/'build/test-temp';cls.temp_root.mkdir(parents=True,exist_ok=True)

    def setUp(self):
        self.holder=tempfile.TemporaryDirectory(dir=self.temp_root);self.root=Path(self.holder.name)
        self.app=_App(self.root);self.lib=desktop_save_mode.SaveLibrary(self.app)

    def tearDown(self):
        desktop_save_mode.dataset.cache_clear();self.holder.cleanup()

    def save(self,tactics,clubs=({'uid':1,'name':'甲队','short_name':'甲'},{'uid':2,'name':'乙队','short_name':'乙'})):
        key='0123456789abcdef';folder=self.lib.root/key;folder.mkdir(parents=True)
        data={'source':SOURCE['source'],'source_sha256':SOURCE['source_sha256'],'date':SOURCE['date'],
              'build':SOURCE['build'],'clubs':list(clubs),'tactics':tactics,'fixtures':[],
              'selections':[],'caches':[],'managed':[]}
        (folder/'dataset.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
        desktop_save_mode.dataset.cache_clear()
        return key,folder

    def test_stored_tactics_lists_only_parsed_first_team_plans(self):
        key,folder=self.save([
            {'name':'主战术','club_uid':1,'team_slot':0,'raw_plan':'tactic_0.bin'},
            {'name':'未解析','club_uid':1,'team_slot':0},
            {'name':'青年队','club_uid':1,'team_slot':1,'raw_plan':'tactic_1.bin'},
            {'name':'对手战术','club_uid':2,'team_slot':0,'raw_plan':'tactic_2.bin'}])
        self.assertEqual(self.lib.stored_tactics(key,1),
            [{'key':'stored:0','index':0,'name':'主战术','available':True}])
        self.assertEqual([t['key']for t in self.lib.stored_tactics(key,2)],['stored:3'])
        self.assertFalse((folder/'rosters').exists())

    def test_export_targets_reports_reading_and_composes_complete_result(self):
        key,_=self.save([{'name':'主战术','club_uid':1,'team_slot':0,'raw_plan':'tactic_0.bin'}])
        with mock.patch.object(self.lib,'begin_opponents',return_value={'status':'reading','stage':'正在读取同联赛教练偏好'}):
            self.assertEqual(self.lib.export_targets(key,1),{'status':'reading','stage':'正在读取同联赛教练偏好'})
        with mock.patch.object(self.lib,'begin_opponents',return_value={'status':'error','stage':'教练偏好读取失败'}):
            self.assertEqual(self.lib.export_targets(key,1),{'status':'error','stage':'教练偏好读取失败'})
        report={'opponents':[{'key':'coach:77','club_uid':2,'name':'乙队','available':True,
                    'source':'教练偏好预设 · 王教练 · 高位逼抢','coach':{'preset_name':'高位逼抢'}}],
                'same_league_clubs':5,
                'failures':[{'club_uid':3,'name':'丙队','error':'主教练缺失'}],
                'unrecovered_clubs':[{'club_uid':3,'name':'丙队','reason':'教练偏好预设尚不可用'},
                                     {'club_uid':4,'name':'丁队','reason':'教练偏好预设尚不可用'}]}
        with mock.patch.object(self.lib,'begin_opponents',return_value={'status':'complete'}),\
             mock.patch.object(self.lib,'inspect_opponents',return_value=report):
            value=self.lib.export_targets(key,1)
        self.assertEqual(value['status'],'complete')
        self.assertEqual(value['own']['club_uid'],1)
        self.assertEqual([t['key']for t in value['own']['tactics']],['stored:0'])
        self.assertEqual(value['opponents'],[{'key':'coach:77','club_uid':2,'name':'乙队','tactic_name':'高位逼抢',
            'source':'教练偏好预设 · 王教练 · 高位逼抢','available':True}])
        self.assertEqual(value['same_league_clubs'],5)
        self.assertEqual([f['club_uid']for f in value['failures']],[3,4])

    def test_export_tactics_writes_payloads_and_keeps_failures(self):
        key,_=self.save([
            {'name':'主战术','club_uid':1,'team_slot':0,'raw_plan':'tactic_0.bin'},
            {'name':'未解析','club_uid':1,'team_slot':0}])
        self.app.DEFAULT={'schema':3,'fixture':'bundled_match_pkm','rules':'lab',
            'teams':[{'name':'甲','tactic_name':''},{'name':'乙','tactic_name':''}]}
        self.app.validate_scenario=lambda scenario:scenario
        self.app.export_fmf=lambda data:{'file_base64':base64.b64encode(archive(10+data['side'])).decode(),
            'report':{'native_roundtrip_verified':True,'notice':'已核验'}}
        self.lib.parsed_plan=lambda key,index:{}
        self.lib.apply_plan=lambda team,plan:None
        directory=self.root/'out';directory.mkdir()
        coach={'teams':[{'team_id':77,'club_uid':2,'name':'乙队'}]}
        with mock.patch.object(desktop_coach_presets,'ensure',return_value=coach),\
             mock.patch.object(desktop_coach_presets,'preset_tactic',
                 return_value={'name':'乙队','tactic_name':'教练偏好预设 · 高位逼抢'}):
            result=self.lib.export_tactics(key,1,['stored:0','stored:1','coach:77'],str(directory))
        root=Path(result['directory'])
        self.assertEqual(sorted(e['target']for e in result['files']),['coach:77','stored:0'])
        self.assertEqual([f['target']for f in result['failures']],['stored:1'])
        self.assertIn('不是已解析',result['failures'][0]['error'])
        by_target={e['target']:e for e in result['files']}
        self.assertEqual(fm27_fmf.tactics_plan((root/by_target['stored:0']['file']).read_bytes()),sample_plan(10))
        self.assertEqual(fm27_fmf.tactics_plan((root/by_target['coach:77']['file']).read_bytes()),sample_plan(11))
        self.assertTrue((root/'manifest.json').is_file())

    def test_export_tactics_validation_and_all_failed_error(self):
        key,_=self.save([{'name':'主战术','club_uid':1,'team_slot':0,'raw_plan':'tactic_0.bin'}])
        directory=str(self.root/'out')
        for targets in [[],['stored:0','stored:0'],['unknown:1'],[1]]:
            with self.subTest(targets=targets),self.assertRaises(ValueError):
                self.lib.export_tactics(key,1,targets,directory)
        self.lib.parsed_plan=lambda key,index:(_ for _ in ()).throw(ValueError('原版引擎不可用'))
        self.lib.apply_plan=lambda team,plan:None
        with self.assertRaises(ValueError)as caught:
            self.lib.export_tactics(key,1,['stored:0'],directory)
        self.assertIn('全部导出失败',str(caught.exception))
        self.assertFalse((self.root/'out').exists())

    def test_export_tactics_keeps_coach_failure_metadata(self):
        key,_=self.save([{'name':'主战术','club_uid':1,'team_slot':0,'raw_plan':'tactic_0.bin'},
                         {'name':'次战术','club_uid':1,'team_slot':0,'raw_plan':'tactic_1.bin'}])
        self.app.DEFAULT={'teams':[{'name':'甲','tactic_name':''},{'name':'乙','tactic_name':''}]}
        self.app.validate_scenario=lambda scenario:scenario
        self.app.export_fmf=lambda data:{'file_base64':base64.b64encode(archive(20+data['side'])).decode(),
            'report':{'native_roundtrip_verified':True}}
        self.lib.parsed_plan=lambda key,index:{}
        self.lib.apply_plan=lambda team,plan:None
        directory=self.root/'out';directory.mkdir()
        coach={'teams':[{'team_id':77,'club_uid':2,'name':'乙队','preset_name':'高位逼抢'}]}
        with mock.patch.object(desktop_coach_presets,'ensure',return_value=coach),\
             mock.patch.object(desktop_coach_presets,'preset_tactic',side_effect=ValueError('原装预设内容已改变')):
            result=self.lib.export_tactics(key,1,['stored:0','coach:77'],str(directory))
        self.assertEqual([e['target']for e in result['files']],['stored:0'])
        failure=result['failures'][0]
        self.assertEqual((failure['target'],failure['club_uid'],failure['club']),('coach:77',2,'乙队'))
        self.assertEqual(failure['tactic_name'],'教练偏好预设 · 高位逼抢')
        self.assertIn('原装预设内容已改变',failure['error'])

if __name__=='__main__':
    unittest.main()
