"""Retain native source values while still checking newly edited instructions."""
import copy,hashlib,hmac,json,secrets

def key(app):
    path=app.RUNS.parent/'native-source-plan.key'
    if not path.exists():
        try:
            with path.open('xb')as stream:stream.write(secrets.token_bytes(32))
        except FileExistsError:pass
    value=path.read_bytes()
    if len(value)!=32:raise ValueError('原生方案校验密钥无效，请重新读取存档')
    return value

def payload(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()

def sign(app,team):
    value=copy.deepcopy({k:team[k]for k in ('phases','instructions')})
    team['native_source_plan']={'value':value,'signature':hmac.new(key(app),payload(value),hashlib.sha256).hexdigest()}

def baseline(app,team):
    proof=team.get('native_source_plan')
    if proof is None:return None
    if not isinstance(proof,dict)or set(proof)!={'value','signature'}:raise ValueError('原生方案来源校验无效，请重新导入')
    expected=hmac.new(key(app),payload(proof['value']),hashlib.sha256).hexdigest()
    if not isinstance(proof['signature'],str)or not hmac.compare_digest(expected,proof['signature']):
        raise ValueError('原生方案来源校验失败，请重新导入存档战术')
    return proof['value']

def cell(source,phase,current):
    if source is None:return None
    # The signed assignment belongs to its position, regardless of which player fills it.
    return next((original for original in source['phases'][phase]
                 if all(original.get(k)==current.get(k) for k in ('position','role','duty'))),None)
