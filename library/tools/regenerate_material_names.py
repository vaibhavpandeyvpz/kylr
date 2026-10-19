"""Regenerate classified Blender/GLB/FBX deliveries without rebuilding geometry.

Run with headless Blender; each asset's Python source owns its classifier map.
Existing validated geometry, UVs, skinning and clips are checked on delivery.
No preview rendering is performed.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'models'))
from material_uv import refresh_asset
from material_classes import metadata

arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
folders = [ROOT / item for item in arguments] if arguments else sorted({
    source.parent for source in (ROOT / 'models').rglob('model.py')
    if (source.parent / (source.parent.name + '.blend')).exists()
})
results = []
for index, folder in enumerate(folders, 1):
    print(f'MATERIAL_DELIVERY {index}/{len(folders)} {folder.relative_to(ROOT)}', flush=True)
    refresh_asset(folder, classify_only=True)
    metadata(folder)
    results.append(str(folder.relative_to(ROOT)))
    print(f'MATERIAL_DELIVERY_OK {folder.relative_to(ROOT)}', flush=True)
    (ROOT.parent / 'game/reports/material-name-deliveries.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
report = ROOT.parent / 'game/reports/material-name-deliveries.json'
report.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
print(f'MATERIAL_DELIVERIES_COMPLETE {len(results)}', flush=True)
