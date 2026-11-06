"""Actual local engine identity, static compatibility and stable batch inputs."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import subprocess

LEASES = []


def close_leases():
    for stream in LEASES:
        stream.close()
    LEASES.clear()


def require_available(status):
    if not status.get('can_simulate'):
        raise ValueError('暂不能模拟：'+status.get('message','请设置游戏目录并检查诊断'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def lease(path):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        stream = open(msvcrt.open_osfhandle(handle, 0), 'rb')
    except BaseException:
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)
        raise
    LEASES.append(stream)


def initialize(root):
    close_leases()
    os.environ.pop('FM27_EXPECTED_DLL_SHA256', None)
    native = root / 'fm27_native'
    game = Path(os.environ['FM27_GAME_ROOT']) if os.environ.get('FM27_GAME_ROOT') else native
    plugins = game / 'fm_Data/Plugins/x86_64' if os.environ.get('FM27_GAME_ROOT') else native/'libs'
    dll = plugins/'game_plugin.dll' if os.environ.get('FM27_GAME_ROOT') else native/'game_plugin.dll'
    files = {'game_plugin.dll':dll, 'icudt65l.dat':game/'icudt65l.dat',
             'shared/data/simatch.fmf':game/'shared/data/simatch.fmf',
             'shared/data/simatchshared.fmf':game/'shared/data/simatchshared.fmf'}
    for name in ['icuuc65.dll','icuin65.dll','icudt65.dll','EOSSDK-Win64-Shipping.dll',
                 'PartyWin.dll','PlayFabMultiplayerWin.dll','steam_api64.dll']:
        files['libs/'+name] = plugins/name
    status={'policy':'graded-adapter-compatibility-v2','compatible':False,'can_simulate':False,
            'disposition':'blocked','selected_game_root':str(game.resolve()),
            'actual_dll_sha256':None,'resource_fingerprint':None,
            'whole_file_sha_is_admission_gate':False,'whole_engine_behavior_equivalence_proven':False}
    try:
        missing=[name for name,path in files.items() if not path.is_file()]
        if missing:
            return {**status,'reason':'missing_resources','missing_files':missing,
                    'message':'请选择完整的游戏安装目录；缺少：'+', '.join(missing)}
        for path in files.values():
            lease(path)
        env = os.environ.copy()
        env.pop('FM27_EXPECTED_DLL_SHA256', None)
        diagnostic_error=None
        try:
            checked = subprocess.run([str(native/'FM27Simulator.exe'),'--check-image',str(dll)],
                                     env=env, capture_output=True, timeout=30,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            rows=[]
            for line in checked.stdout.decode('utf8',errors='replace').splitlines():
                try: rows.append(json.loads(line))
                except ValueError: pass
            diagnostic_error=checked.stderr.decode('utf8',errors='replace')[:2000]
        except (OSError,subprocess.TimeoutExpired) as error:
            rows=[];diagnostic_error=str(error)
        validation = next((r for r in rows if r.get('event')=='native_engine_compatibility'),None)
        if validation and not (validation.get('compatible') or validation.get('trial_allowed')):
            close_leases()
            return {**status,'reason':validation.get('reason'),'diagnostics':rows,
                    'message':'关键接口或布局不匹配：'+str(validation.get('reason'))+'，位置 '+hex(validation.get('rva',0))}
        actual = sha(dll)
        entries = [{'path':name,'sha256':actual if name=='game_plugin.dll' else sha(path)} for name,path in sorted(files.items())]
        fingerprint = hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        profile = json.loads((native/'engine_compat_profile.json').read_text(encoding='utf8'))
        os.environ['FM27_EXPECTED_DLL_SHA256'] = actual
        verified=bool(validation and validation.get('compatible'))
        return {**status,'profile':validation.get('profile') if validation else None,
                'compatible':verified,'can_simulate':True,'trial_allowed':not verified,
                'disposition':'verified' if verified else 'unverified',
                'reason':validation.get('reason') if validation else 'preflight_unavailable',
                'message':'引擎关键接口检查通过' if verified else '此版本尚未验证，可试运行；每场仍须通过原生完赛、比分和统计校验。',
                'diagnostics':rows,'diagnostic_error':diagnostic_error,
                'actual_dll_sha256':actual,'resource_fingerprint':fingerprint,
                'reference_dll_sha256':profile['reference_sha256'],
                'original_build_verified':actual==profile['reference_sha256'],
                'whole_file_sha_is_admission_gate':False,'selected_game_root':str(game.resolve()),
                'files':entries,'whole_engine_behavior_equivalence_proven':False}
    except (OSError,ValueError) as error:
        close_leases()
        return {**status,'reason':'resource_access_failed','message':'无法读取游戏资源：'+str(error)}
