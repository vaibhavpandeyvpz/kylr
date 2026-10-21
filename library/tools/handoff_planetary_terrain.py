"""Copy validated map exports without embedding unused terrain fallback textures."""
from pathlib import Path
import copy
import hashlib
import json
import shutil
from handoff_lunar_materials import read,encode,geometry,compact

ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT.parent/'game/assets/models/maps'


def strip_textures(value):
    if isinstance(value,dict):
        for key in list(value):
            if key.endswith('Texture'):del value[key]
            else:strip_textures(value[key])
    elif isinstance(value,list):
        for item in value:strip_textures(item)


def handoff(map_id):
    source=ROOT/'models/maps'/map_id
    destination=GAME/map_id
    records=[]
    for suffix in ('','_col','_scenery','_scenery_col'):
        path=source/(map_id+suffix+'.glb')
        document,binary=read(path)
        before=geometry(document,binary)
        strip_textures(document.get('materials',[]))
        binary=compact(document,binary)
        assert geometry(document,binary)==before,'Map geometry changed during texture compaction'
        target=destination/path.name;target.write_bytes(encode(document,binary))
        records.append({'file':target.relative_to(ROOT.parent).as_posix(),'geometry_sha256':before,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    for suffix in ('_rig.json','_scenery_rig.json'):
        shutil.copyfile(source/(map_id+suffix),destination/(map_id+suffix))
    return records


if __name__=='__main__':
    records=[]
    for map_id in ('faceoff','skyfall'):records.extend(handoff(map_id))
    (ROOT/'.local/planetary/handoff.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
    print('PLANETARY_HANDOFF',len(records),'geometry-preserving exports')
