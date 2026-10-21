"""Generate height fields and bake them through the pinned Terrain3D SDK."""
from pathlib import Path
import argparse
import importlib.util
import hashlib
import json
import os
import shutil
import subprocess
import sys
from setup_terrain3d import install

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'models/maps/common'))
from planetary_field import generate


def build(map_id,godot=None):
    sdk=install()
    output=ROOT/'.local/planetary'
    # Layout.py remains the placement source; generated GLBs are never queried.
    folder=ROOT/'models/maps'/map_id
    sys.path.insert(0,str(folder))
    spec=importlib.util.spec_from_file_location('terrain_layout_'+map_id,folder/'layout.py')
    layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
    values=layout.data();markers=values[0] if map_id=='faceoff' else values[1]
    record=generate(map_id,markers,output)
    destination=ROOT.parent/'game/assets/textures/planetary'
    destination.mkdir(parents=True,exist_ok=True)
    for index in range(2):shutil.copyfile(output/f'{map_id}_weights{index}.png',destination/f'{map_id}_weights{index}.png')
    manifest_path=destination/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for index in range(2):
        name=f'{map_id}_weights{index}.png'
        manifest['files'][name]=hashlib.sha256((destination/name).read_bytes()).hexdigest()
    manifest.setdefault('maps',{})[map_id]={'min_height_m':record['min_height'],'max_height_m':record['max_height'],'height_sha256':hashlib.sha256((output/(map_id+'.rf')).read_bytes()).hexdigest(),'qa_points':record['qa_points']}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (sdk/'project.godot').write_text('config_version=5\n[application]\nconfig/name="Planetary terrain authoring"\n',encoding='utf-8')
    shutil.copyfile(ROOT/'tools/bake_planetary_terrain.gd',sdk/'bake.gd')
    engine=Path(godot or os.environ.get('GODOT_EXECUTABLE') or ROOT.parent/'engine/bin/godot.windows.editor.x86_64.console.exe')
    for arguments in [['--editor','--import','--quit'],['--script','bake.gd','--',str(output),map_id]]:
        subprocess.run([str(engine),'--headless','--path',str(sdk),*arguments],check=True)
    assert (output/(map_id+'_baked.json')).exists()
    print('PLANETARY_FIELD',map_id,record['min_height'],record['max_height'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('map',choices=['faceoff','skyfall','all'])
    parser.add_argument('--godot',help='Custom engine executable; defaults to GODOT_EXECUTABLE or the workspace engine')
    args=parser.parse_args()
    for map_id in (['faceoff','skyfall'] if args.map=='all' else [args.map]): build(map_id,args.godot)
