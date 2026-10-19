"""Refresh native preview metadata after material classification; no rendering."""
import sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'models'))
from material_classes import policy, scene_metadata

count = 0
for source in sorted((ROOT / 'models').rglob('model.py')):
    folder = source.parent
    blend = folder / (folder.name + '.blend')
    if not blend.exists():
        continue
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene_metadata(policy(folder))
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    count += 1
print('MATERIAL_METADATA_NORMALIZED', count, flush=True)
