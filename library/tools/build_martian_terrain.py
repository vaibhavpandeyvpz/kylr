"""Bake the Ramparts height field with the pinned Terrain3D authoring SDK."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
from setup_terrain3d import install
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'models/maps/ramparts'))
from crater_field import generate
output=ROOT/'.local/planetary';record=generate(output)
sdk=install()
(sdk/'project.godot').write_text('config_version=5\n[application]\nconfig/name="Martian terrain authoring"\n')
shutil.copyfile(ROOT/'tools/bake_planetary_terrain.gd',sdk/'bake.gd')
executable=os.environ.get('GODOT') or shutil.which('godot')
assert executable,'Set GODOT to the official engine executable'
for args in [['--editor','--import','--quit'],['--script','bake.gd','--',str(output),'ramparts']]:
    subprocess.run([executable,'--headless','--path',str(sdk),*args],check=True)
assert (output/'ramparts_baked.json').exists()
print('MARTIAN_TERRAIN3D_BAKED',record['min_height'],record['max_height'])
