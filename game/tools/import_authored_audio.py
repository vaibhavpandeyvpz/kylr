"""Retain selected provider audio as reproducible library sources, without URL credentials."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selections',type=Path)
    parser.add_argument('--library',type=Path,default=Path('../library/sounds'))
    parser.add_argument('--replace',action='store_true',help='Replace only the selected existing recordings')
    args = parser.parse_args()
    for kind in ['speech','music']:
        base = args.library/kind
        manifest_path = base/'source_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'provider':'ElevenLabs','flow_id':'PpP3eGPZzyLlN8qecqLt','recordings':[]}
        recordings = {(c['bank'],c['key']):c for c in manifest['recordings']}
        for job in json.loads(args.selections.read_text(encoding='utf-8')):
            if (job['type']=='music') != (kind=='music'): continue
            for key in ['bank','key']:
                if not re.fullmatch(r'[a-z0-9_]+',job[key]): raise ValueError('Invalid recording key')
            identity = (job['bank'],job['key'])
            if identity in recordings and not args.replace: continue
            source = Path('source')/job['bank']/(job['key']+'.mp3')
            target = base/source
            response = requests.get(job['url'],timeout=45)
            response.raise_for_status()
            if not response.content: raise ValueError('Empty recording')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(response.content)
            clip = {k:job[k] for k in ['bank','key','prompt','node_id','generation_id','duration_secs','candidate_ids'] if k in job}
            for key in ['voice_id','voice_name','duration','model_id','flow_id']:
                if key in job: clip[key]=job[key]
            clip.update(source=source.as_posix(),sha256=hashlib.sha256(response.content).hexdigest())
            recordings[identity]=clip
        manifest['recordings']=list(recordings.values())
        base.mkdir(parents=True,exist_ok=True)
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        print(kind,len(recordings),'source recordings retained')


if __name__=='__main__': main()
