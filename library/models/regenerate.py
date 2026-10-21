"""Regenerate the library's complete asset previews and videos.

Run from library with .venv/Scripts/python.exe models/regenerate.py.
GPU renders run serially to fit laptop VRAM. Rebuild colliders explicitly with
--stage colliders only when geometry changes. Outputs and logs are generated.
"""
import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = os.environ.get('BLENDER_EXECUTABLE') or shutil.which('blender') or 'blender'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('previews','showcases','colliders','all'), default='all')
    parser.add_argument('--only', nargs='*')
    parser.add_argument('--blender', default=BLENDER)
    args = parser.parse_args()
    if not shutil.which(args.blender):
        parser.error('Blender 5.2 is required: add it to PATH, set BLENDER_EXECUTABLE or pass --blender.')
    folders = sorted(p.parent for p in (ROOT/'models').glob('*/*/model.py'))
    if args.only:
        missing = set(args.only) - {p.name for p in folders}
        if missing: parser.error('Unknown assets: ' + ', '.join(sorted(missing)))
        folders = [p for p in folders if p.name in args.only]
    stages = ('previews','showcases') if args.stage=='all' else (args.stage,)
    names = dict(previews='preview.py',showcases='animate.py',colliders='collision.py')
    target = ROOT/'target'/'regeneration'
    target.mkdir(parents=True,exist_ok=True)
    records=[]
    for stage in stages:
        for folder in folders:
            script = folder/names[stage]
            if not script.exists(): continue
            log = target/f'{folder.name}_{stage}.log'
            started=time.time()
            print(f'{stage}: {folder.name} started',flush=True)
            command=[args.blender,'--background','--factory-startup','--python',
                     str(ROOT/'models'/'nvidia_render.py'),'--',str(script)]
            with log.open('w',encoding='utf8') as stream:
                process=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            output=log.read_text(encoding='utf8',errors='replace')
            ok=process.returncode==0 and 'Traceback' not in output and 'Error:' not in output
            records.append(dict(asset=folder.name,stage=stage,ok=ok,seconds=round(time.time()-started,1),log=str(log)))
            (target/f'{args.stage}_report.json').write_text(json.dumps(records,indent=2),encoding='utf8')
            print(f'{stage}: {folder.name} {"PASS" if ok else "FAIL"} ({records[-1]["seconds"]}s)',flush=True)
            if not ok: print(output[-2000:],flush=True)
    if not all(r['ok'] for r in records): raise SystemExit(1)

if __name__=='__main__': main()
