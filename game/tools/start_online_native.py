"""Local Windows fallback when Docker/WSL is unavailable. No service installation."""
import hashlib, json, os, secrets, subprocess, sys, time, zipfile
from pathlib import Path
import requests
from pymongo import MongoClient

def start():
    root=Path(__file__).resolve().parents[1]
    state=root/'reports'/'online'
    state.mkdir(parents=True,exist_ok=True)
    version='8.0.20'
    target=state/'mongodb'
    executable=next(target.glob('**/bin/mongod.exe'),None) if target.exists() else None
    if executable is None:
        url=f'https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-{version}.zip'
        archive=state/f'mongodb-{version}.zip'
        expected=requests.get(url+'.sha256',timeout=30)
        expected.raise_for_status()
        print('Downloading MongoDB Community from its official distribution…',flush=True)
        response=requests.get(url,stream=True,timeout=60)
        response.raise_for_status()
        digest=hashlib.sha256()
        with archive.open('wb') as output:
            for chunk in response.iter_content(1024*1024): output.write(chunk); digest.update(chunk)
        if digest.hexdigest()!=expected.text.split()[0]: raise RuntimeError('MongoDB archive checksum mismatch')
        with zipfile.ZipFile(archive) as packed:
            for member in packed.infolist():
                path=(target/member.filename).resolve()
                if not path.is_relative_to(target.resolve()): raise RuntimeError('Invalid archive path')
            packed.extractall(target)
        executable=next(target.glob('**/bin/mongod.exe'))
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    database=state/'mongo-data'
    database.mkdir(exist_ok=True)
    mongo=MongoClient('mongodb://127.0.0.1:27017/kylr',serverSelectionTimeoutMS=1000)
    owned=[]
    try: mongo.admin.command('ping')
    except Exception:
        proc=subprocess.Popen([str(executable),'--bind_ip','127.0.0.1','--port','27017','--dbpath',str(database),'--logpath',str(state/'mongod.log')],creationflags=flags)
        owned.append({'kind':'mongo','pid':proc.pid})
        deadline=time.time()+20
        while time.time()<deadline:
            try: mongo.admin.command('ping'); break
            except Exception:
                if proc.poll() is not None: raise RuntimeError('MongoDB stopped; inspect reports/online/mongod.log')
                time.sleep(.2)
        mongo.admin.command('ping')
    secret_path=state/'native-secrets.json'
    if not secret_path.exists(): secret_path.write_text(json.dumps({'JWT_SECRET':secrets.token_hex(32),'CONTROL_TOKEN':secrets.token_hex(32)}),encoding='utf-8')
    secrets_config=json.loads(secret_path.read_text(encoding='utf-8'))
    env=dict(os.environ,**secrets_config,SCHEDULER='local',MONGO_URI='mongodb://127.0.0.1:27017/kylr',GAME_API_URL='http://127.0.0.1:8080',KYLR_API_BIND='127.0.0.1')
    try: running=requests.get('http://127.0.0.1:8080/healthz',timeout=1).ok
    except requests.RequestException: running=False
    if not running:
        with (state/'api.log').open('w',encoding='utf-8') as log:
            proc=subprocess.Popen([sys.executable,'-m','services.api.app'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
        owned.append({'kind':'api','pid':proc.pid})
        deadline=time.time()+20
        while time.time()<deadline:
            try:
                if requests.get('http://127.0.0.1:8080/healthz',timeout=1).ok: break
            except requests.RequestException: pass
            if proc.poll() is not None: raise RuntimeError('API stopped; inspect reports/online/api.log')
            time.sleep(.2)
        else: raise RuntimeError('API did not become healthy')
    (state/'native-processes.json').write_text(json.dumps(owned),encoding='utf-8')
    print('Local MongoDB and API ready at http://127.0.0.1:8080. Game servers launch on Play.',flush=True)

if __name__=='__main__': start()
