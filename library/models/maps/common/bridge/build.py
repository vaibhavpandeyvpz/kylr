"""Serial standalone bridge pipeline using the supported headless Blender."""
import argparse,subprocess,os,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BLENDER=os.environ.get('BLENDER_EXECUTABLE') or shutil.which('blender')
def run(script,*args):
 folder=ROOT/'target/bridge';folder.mkdir(parents=True,exist_ok=True)
 log=folder/(Path(script).stem+'.log')
 with log.open('w') as out:
  result=subprocess.run([BLENDER,'--background','--factory-startup','--python',str(HERE/script),*args],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
 text=log.read_text(errors='replace')
 if result.returncode or 'Traceback' in text:raise RuntimeError(str(log)+'\n'+text[-3000:])
 print('BRIDGE',script,'PASS',flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['build','validate','preview','all'],default='all');args=parser.parse_args()
 if not BLENDER:parser.error('Blender 5.2 is required: add it to PATH or set BLENDER_EXECUTABLE.')
 if args.stage in ('all','build'):run('model.py');run('collision.py','--','--no-render')
 if args.stage in ('all','validate'):run('validate.py')
 if args.stage in ('all','preview'):run('preview.py')
