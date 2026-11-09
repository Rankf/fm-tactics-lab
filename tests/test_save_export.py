import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import desktop_coach_presets
import desktop_game_db_names
import desktop_save_compat
import desktop_save_export
import desktop_save_mode
import fm27_fmf
import fm27_tactic_pool

SOURCE={'save_id':'0123456789abcdef','source':'C:/saves/career.fm','source_sha256':'a'*64,
        'date':'2027-01-15','build':'27.1.0'}
TAC_PLAN_HEADER=b'\x22'+struct.pack('<H',68)+b'\x1b'

def sample_plan(seed,size=96):
    base=hashlib.sha256(str(seed).encode()).digest()
    return TAC_PLAN_HEADER+(base*((size+len(base)-1)//len(base)))[:size]

def archive(seed,name='战术',size=96):
    return fm27_fmf.tactics_archive(sample_plan(seed,size),name)

def item(club_uid,club,target,tactic_name,payload,coach='主教练',index=1,report=None):
    stem=f'{club}-{coach}-第{index}套战术'
    return {'club_uid':club_uid,'club':club,'coach':coach,'index':index,'name':stem,
            'target':target,'tactic_name':stem,'payload':payload,
            'report':report or {'native_roundtrip_verified':True}}

class FmfPlanTests(unittest.TestCase):
    def test_roundtrip_preserves_plan_across_block_boundaries(self):
        for size in [1,7,8,100,65535,65536,65537,200000]:
            plan=sample_plan(size,size)
            self.assertEqual(fm27_fmf.tactics_plan(fm27_fmf.tactics_archive(plan,'测试战术')),plan)

    def test_rejects_invalid_archives(self):
        payload=archive(1)
        start=len(fm27_fmf.HEADER)+17;content=start+12
        cases=[('bytes','not bytes'),('short',payload[:20]),('magic',b'\x00'+payload[1:]),
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

    def test_tactic_file_name_uses_club_coach_and_index(self):
        self.assertEqual(desktop_save_export.tactic_file_name('德比郡','韦恩·鲁尼',2),'德比郡-韦恩·鲁尼-第2套战术')
        self.assertEqual(desktop_save_export.tactic_file_name('','',0),'俱乐部-主教练-第1套战术')
        self.assertLessEqual(len(desktop_save_export.tactic_file_name('甲'*80,'乙'*80,1)),60)

class ExportWriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_root=ROOT/'build/test-temp';cls.temp_root.mkdir(parents=True,exist_ok=True)

    def setUp(self):
        self.holder=tempfile.TemporaryDirectory(dir=self.temp_root);self.base=Path(self.holder.name)

    def tearDown(self):
        self.holder.cleanup()

    def test_writes_flat_files_manifest_and_embedded_plans(self):
        items=[item(1,'甲队','stored:0','控球',archive(1),index=1),
               item(1,'甲队','stored:1','反击',archive(2),index=2),
               item(2,'乙队','coach:77','高压',archive(3),coach='乙帅')]
        result=desktop_save_export.write(self.base,SOURCE,items)
        root=Path(result['directory'])
        self.assertEqual(root.parent,self.base.resolve())
        self.assertRegex(root.name,r'^FM27存档战术-\d{8}-\d{6}$')
        self.assertEqual(result['profile'],'saved-tactic-export-v2')
        self.assertEqual(result['failures'],[])
        self.assertEqual(len(result['files']),3)
        self.assertTrue((root/'甲队-主教练-第1套战术.fmf').is_file())
        self.assertTrue((root/'甲队-主教练-第2套战术.fmf').is_file())
        self.assertTrue((root/'乙队-乙帅-第1套战术.fmf').is_file())
        self.assertTrue((root/'导出说明.txt').is_file())
        self.assertFalse(any(path.is_dir() for path in root.iterdir()))
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
            self.assertEqual((entry['club'],entry['coach'],entry['index']),([('甲队','主教练',1),('甲队','主教练',2),('乙队','乙帅',1)][index]))
        self.assertEqual({e['target'] for e in result['files']},{'stored:0','stored:1','coach:77'})

    def test_duplicate_file_names_are_deduplicated(self):
        same=item(1,'同队','stored:0','Tactic',archive(1))
        result=desktop_save_export.write(self.base,SOURCE,
            [same,{**same,'target':'stored:1','payload':archive(2)},{**same,'target':'stored:2','payload':archive(3)}])
        root=Path(result['directory'])
        self.assertTrue((root/'同队-主教练-第1套战术.fmf').is_file())
        self.assertTrue((root/'同队-主教练-第1套战术2.fmf').is_file())
        self.assertTrue((root/'同队-主教练-第1套战术3.fmf').is_file())
        self.assertEqual(len({entry['file'].casefold()for entry in result['files']}),3)

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
            try:(self.base/'FM27存档战术-20260101-130000').symlink_to(outside,target_is_directory=True)
            except OSError:self.skipTest('当前平台不允许创建符号链接')
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
        items=[item(1,'..\\..\\逃逸','../../evil',archive(1),archive(1),coach='../../evil',index=1)]
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
                    item(1,'甲队','stored:1','反击',archive(2),index=2)])
        self.assertEqual(list(self.base.iterdir()),[])

class CoachVariantTests(unittest.TestCase):
    def catalog(self):
        return {'styles':[{'id':0,'style_code':100},{'id':1,'style_code':200}],
                'formations':[{'code':10,'positions':[1,2,3]},{'code':20,'positions':[4,5,6]}],
                'templates':[
                    {'index':0,'style_code':100,'name':'控球甲','phases':[[{'position':1},{'position':2},{'position':3}],
                        [{'position':1},{'position':2},{'position':3}]]},
                    {'index':1,'style_code':100,'name':'控球乙','phases':[[{'position':1},{'position':2},{'position':3}],
                        [{'position':1},{'position':2},{'position':3}]]},
                    {'index':2,'style_code':100,'name':'控球乙阵','phases':[[{'position':4},{'position':5},{'position':6}],
                        [{'position':4},{'position':5},{'position':6}]]}]}

    def test_primary_and_secondary_produce_distinct_presets(self):
        options=desktop_coach_presets.variants(self.catalog(),0,10,20)
        self.assertEqual([option['index']for option in options],[1,2])
        self.assertEqual(options[0]['preset']['index'],0)
        self.assertEqual(options[1]['preset']['index'],2)
        self.assertTrue(options[0]['exact']);self.assertTrue(options[1]['exact'])
        self.assertEqual((options[0]['formation_code'],options[1]['formation_code']),(10,20))

    def test_same_secondary_keeps_single_tactic(self):
        self.assertEqual(len(desktop_coach_presets.variants(self.catalog(),0,10,10)),1)
        self.assertEqual(len(desktop_coach_presets.variants(self.catalog(),0,10,99)),1)

    def test_unmapped_primary_is_rejected(self):
        with self.assertRaises(ValueError):desktop_coach_presets.variants(self.catalog(),0,99,10)

class _Engine:
    def sha(self,path):return hashlib.sha256(str(path).encode()).hexdigest()

class _App:
    def __init__(self,root):
        self.RUNS=root/'runs';self.RUNS.mkdir(parents=True)
        self.NATIVE=root/'native';self.NATIVE.mkdir()
        self.desktop_engine=_Engine();self.ENGINE_COMPATIBILITY={'resource_fingerprint':'test'}

def tactic_cells():
    return [{'position':'GK'if index==0 else'DC','role':'GK'if index==0 else'DC','duty':'0',
             'instructions':{},'target_player':255,'target_position':0}for index in range(11)]

def preset_team(extra='0'):
    return {'name':'对手','tactic_name':'教练偏好预设','mentality':4,'instructions':{'1':0},
            'native_extra_team_bits':extra,'phases':[tactic_cells(),tactic_cells()]}

class SaveLibraryLeagueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_root=ROOT/'build/test-temp';cls.temp_root.mkdir(parents=True,exist_ok=True)

    def setUp(self):
        self.holder=tempfile.TemporaryDirectory(dir=self.temp_root);self.root=Path(self.holder.name)
        self.app=_App(self.root);self.lib=desktop_save_mode.SaveLibrary(self.app)
        self.names=mock.patch.object(desktop_game_db_names,'resolve',
            return_value={'competitions':{101:'测试甲级联赛',102:'测试乙级联赛'},
                          'nations':{5:'英格兰',6:'法国'},'source':'game_db'})
        self.names.start()

    def tearDown(self):
        self.names.stop();desktop_save_mode.dataset.cache_clear();self.holder.cleanup()

    def save(self):
        key='0123456789abcdef';folder=self.lib.root/key;folder.mkdir(parents=True)
        data={'schema':4,'source':SOURCE['source'],'source_sha256':SOURCE['source_sha256'],'date':SOURCE['date'],
              'build':SOURCE['build'],'tactics':[],'fixtures':[],'selections':[],'caches':[],
              'managed':[{'club_uid':1}],
              'clubs':[{'uid':1,'name':'甲队','short_name':'甲','nation_id':14}],
              'leagues':[{'key':'17:200:2026','competition_id':17,'stage_id':200,'season':2026,
                          'club_uids':[1,2,3,4],'fixture_count':24,'first_date':'2026-08-01','last_date':'2027-05-01'}],
              'league_clubs':{'1':{'name':'甲队','short_name':'甲','nation_id':14,'first_team_id':11,'club_unique_id':101},
                              '2':{'name':'乙队','short_name':'乙','nation_id':14,'first_team_id':12,'club_unique_id':102},
                              '3':{'name':'丙队','short_name':'丙','nation_id':20,'first_team_id':13,'club_unique_id':103},
                              '4':{'name':'丁队','short_name':'丁','nation_id':14,'first_team_id':14,'club_unique_id':104}},
              'nations':{'14':5,'20':6},'competitions':{'17':101}}
        (folder/'dataset.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
        self.lib.check_binding(folder)
        desktop_save_mode.dataset.cache_clear()
        return key,folder

    def team(self,club_uid,name,variants=((1,10,True),(2,20,True))):
        return {'club_uid':club_uid,'name':name,'coach_name':f'{name}主教练','available':True,
                'variants':[{'index':index,'preset_index':index,'preset_sha256':hashlib.sha256(str(index).encode()).hexdigest(),
                             'preset_name':f'预设{index}','formation':f'阵型{code}','formation_code':code,'exact':exact,
                             'position_difference':0}for index,code,exact in variants],'error':None}

    def test_league_catalog_names_leagues_and_nations(self):
        key,_=self.save()
        catalog=self.lib.league_catalog(key)
        self.assertEqual(catalog['name_source'],'game_db')
        self.assertEqual(catalog['save'],{'id':key,'source':SOURCE['source'],'date':SOURCE['date'],'build':SOURCE['build']})
        self.assertEqual(catalog['leagues'],[{'key':'17:200:2026','competition_id':17,'name':'测试甲级联赛',
            'nation':'英格兰','club_count':4,'season':2026,'first_date':'2026-08-01','last_date':'2027-05-01'}])

    def test_league_catalog_requires_new_cache(self):
        key,folder=self.save()
        data=json.loads((folder/'dataset.json').read_text(encoding='utf8'));data.pop('leagues')
        (folder/'dataset.json').write_text(json.dumps(data),encoding='utf8');desktop_save_mode.dataset.cache_clear()
        with self.assertRaises(ValueError):self.lib.league_catalog(key)

    def test_league_library_lists_teams_and_variants(self):
        key,_=self.save()
        ensured={'teams':[self.team(2,'乙队'),self.team(3,'丙队')],'failures':[{'club_uid':4,'name':'丁队','error':'主教练缺失'}]}
        with mock.patch.object(desktop_coach_presets,'ensure',return_value=ensured)as ensure:
            self.lib.build_league_report(key,'17:200:2026')
        ensure.assert_called_once()
        self.assertEqual(ensure.call_args.kwargs['clubs'],[2,3,4])
        value=self.lib.league_library(key,'17:200:2026')
        self.assertEqual(value['status'],'complete')
        self.assertEqual(value['league']['name'],'测试甲级联赛')
        self.assertEqual([(row['club_uid'],row['coach_name'],row['available'])for row in value['teams']],
            [(4,None,False),(3,'丙队主教练',True),(2,'乙队主教练',True)])
        self.assertEqual([variant['index']for variant in next(row for row in value['teams']if row['club_uid']==2)['variants']],[1,2])
        self.assertEqual(value['failures'],[{'club_uid':4,'name':'丁队','error':'主教练缺失'}])

    def test_export_names_files_by_club_coach_and_index(self):
        key,_=self.save()
        ensured={'teams':[self.team(2,'乙队'),self.team(3,'丙队')],'failures':[{'club_uid':4,'name':'丁队','error':'主教练缺失'}]}
        directory=self.root/'out';directory.mkdir()
        self.app.DEFAULT={'teams':[{'name':'甲'},{'name':'乙'}]}
        self.app.validate_scenario=lambda value:value
        with mock.patch.object(desktop_coach_presets,'ensure',return_value=ensured),\
             mock.patch.object(self.lib,'preset_plan',side_effect=lambda key,index,sha:sample_plan(index)):
            result=self.lib.export_league_tactics(key,'17:200:2026',str(directory))
        root=Path(result['directory'])
        self.assertEqual(sorted(entry['file']for entry in result['files']),
            ['丙队-丙队主教练-第1套战术.fmf','丙队-丙队主教练-第2套战术.fmf',
             '乙队-乙队主教练-第1套战术.fmf','乙队-乙队主教练-第2套战术.fmf'])
        self.assertEqual(len(result['failures']),1)
        self.assertEqual(result['failures'][0]['club_uid'],4)
        self.assertEqual(result['league']['name'],'测试甲级联赛')
        for entry in result['files']:
            self.assertEqual(fm27_fmf.tactics_plan((root/entry['file']).read_bytes()),sample_plan(entry['index']))
            self.assertEqual((entry['club'],entry['coach'],entry['index']),
                (entry['file'].split('-')[0],entry['file'].split('-')[1],1 if '第1套' in entry['file']else 2))
        with mock.patch.object(desktop_coach_presets,'ensure',return_value={'teams':[],'failures':[]}):
            with self.assertRaises(ValueError)as caught:
                self.lib.export_league_tactics(key,'17:200:2026',str(directory))
        self.assertIn('没有可导出',str(caught.exception))

    def test_export_requires_directory(self):
        key,_=self.save()
        with mock.patch.object(desktop_coach_presets,'ensure',return_value={'teams':[self.team(2,'乙队')],'failures':[]}):
            for value in [None,'relative/path',str(self.root/'missing')]:
                with self.subTest(directory=value),self.assertRaises(ValueError):
                    self.lib.export_league_tactics(key,'17:200:2026',value)

    def test_preset_plan_is_cached_per_installation_preset(self):
        key,_=self.save()
        plan=sample_plan(7)
        exports=[]
        def export_fmf(data):
            exports.append(data)
            return {'file_base64':base64.b64encode(fm27_fmf.tactics_archive(plan,'FM27 预设战术')).decode(),
                    'report':{'native_roundtrip_verified':True,'sha256':'c'*64}}
        self.app.export_fmf=export_fmf
        self.app.DEFAULT={'teams':[{'name':'甲'},{'name':'乙'}]}
        self.app.validate_scenario=lambda value:value
        with mock.patch.object(desktop_coach_presets,'preset_by_index_team',return_value=preset_team()):
            first=self.lib.preset_plan(key,1,'d'*64)
            second=self.lib.preset_plan(key,1,'d'*64)
        self.assertEqual(first,plan);self.assertEqual(second,plan);self.assertEqual(len(exports),1)
        self.assertEqual(exports[0]['name'],'FM27 预设战术')

    def test_import_pool_keeps_duplicates_and_names_by_tactic(self):
        key,_=self.save()
        scenario={'teams':[{'name':'甲'},{'name':'乙'}]}
        self.app.validate_scenario=lambda value:value
        ensured={'teams':[self.team(2,'乙队',variants=((1,10,True),)),self.team(3,'丙队',variants=((1,10,True),))],'failures':[]}
        with mock.patch.object(desktop_coach_presets,'ensure',return_value=ensured),\
             mock.patch.object(desktop_coach_presets,'preset_by_index_team',return_value=preset_team(extra='3')):
            value=self.lib.import_league_tactics_pool(key,'17:200:2026',scenario)
        pool=value['scenario']['away_tactic_pool']
        self.assertEqual([entry['name']for entry in pool['entries']],
            ['丙队-丙队主教练-第1套战术','乙队-乙队主教练-第1套战术'])
        self.assertEqual(len(pool['entries']),2)
        self.assertEqual(value['imported'],[{'club_uid':3,'club':'丙队','coach':'丙队主教练','index':1,
            'name':'丙队-丙队主教练-第1套战术'},{'club_uid':2,'club':'乙队','coach':'乙队主教练','index':1,
            'name':'乙队-乙队主教练-第1套战术'}])
        self.assertNotIn('away_tactic_pool',scenario)
        with mock.patch.object(desktop_coach_presets,'ensure',return_value=ensured),\
             mock.patch.object(desktop_coach_presets,'preset_by_index_team',return_value=preset_team(extra='3')):
            again=self.lib.import_league_tactics_pool(key,'17:200:2026',value['scenario'])
        self.assertEqual(len(again['scenario']['away_tactic_pool']['entries']),4)

    def test_import_pool_enforces_capacity_before_adding(self):
        key,_=self.save()
        entries=[{'name':f'已有{number}','weight':1,'tactic':fm27_tactic_pool.entry_from_team(preset_team(),name=f'已有{number}')['tactic']}
                 for number in range(fm27_tactic_pool.MAX_ENTRIES)]
        scenario={'teams':[{'name':'甲'},{'name':'乙'}],
            'away_tactic_pool':{'profile':fm27_tactic_pool.PROFILE,'enabled':False,'entries':entries,
                'uniform':{'enabled':True,'attribute_value':15}}}
        self.app.validate_scenario=lambda value:value
        ensured={'teams':[self.team(2,'乙队',variants=((1,10,True),))],'failures':[]}
        with mock.patch.object(desktop_coach_presets,'ensure',return_value=ensured),\
             mock.patch.object(desktop_coach_presets,'preset_by_index_team',return_value=preset_team()):
            with self.assertRaises(ValueError)as caught:
                self.lib.import_league_tactics_pool(key,'17:200:2026',scenario)
        self.assertIn('最多保存',str(caught.exception))
        self.assertEqual(len(scenario['away_tactic_pool']['entries']),fm27_tactic_pool.MAX_ENTRIES)

class ReusableSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_root=ROOT/'build/test-temp';cls.temp_root.mkdir(parents=True,exist_ok=True)

    def setUp(self):
        self.holder=tempfile.TemporaryDirectory(dir=self.temp_root);self.root=Path(self.holder.name)
        self.app=_App(self.root);self.lib=desktop_save_mode.SaveLibrary(self.app)

    def tearDown(self):
        desktop_save_mode.dataset.cache_clear();self.holder.cleanup()

    def test_requires_schema_4(self):
        digest='b'*64;folder=self.lib.root/'fedcba9876543210';folder.mkdir(parents=True)
        data={'source':SOURCE['source'],'source_sha256':digest,'reader_compatibility_profile':desktop_save_compat.PROFILE,
              'first_team_counts':{},'caches':[],'tactics':[],'clubs':[],'schema':3}
        self.lib.write(folder/'progress.json',{'status':'complete'})
        self.lib.write(folder/'dataset.json',data)
        self.assertIsNone(self.lib.reusable_source(digest))
        data['schema']=4
        self.lib.write(folder/'dataset.json',data)
        (folder/'player_index.json').write_text('{}',encoding='utf8');(folder/'rosters').mkdir()
        desktop_save_mode.dataset.cache_clear()
        self.assertEqual(self.lib.reusable_source(digest),folder)

if __name__=='__main__':
    unittest.main()
