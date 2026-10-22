"""Derive repeatable gas relief maps from the authored scalar billow texture."""
from pathlib import Path
import hashlib
import json
import sys
import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from texture_io import write_png

source = HERE/'source/rocket_cloud_height_source.png'
image = bpy.data.images.load(str(source))
image.colorspace_settings.name = 'Non-Color'
width, height = image.size
assert width == height and width >= 1024
pixels = np.array(image.pixels[:], dtype=np.float32).reshape(height, width, 4)[::-1]
field = pixels[:, :, :3].mean(axis=2)
assert np.isfinite(field).all() and np.ptp(field) > .5
# A scalar source supplies density, relief and roughness consistently. Maps are
# linear RGBA data; their alpha channels are material data, never transparency.
albedo_height = np.ones_like(pixels)
albedo_height[:, :, :3] = (.075 + field[:, :, None]*.27)*np.array([.94, .97, 1.0])
albedo_height[:, :, 3] = field
dx = (np.roll(field, -1, axis=1)-np.roll(field, 1, axis=1))*width*.035
dy = (np.roll(field, 1, axis=0)-np.roll(field, -1, axis=0))*height*.035
normal = np.stack((-dx, -dy, np.ones_like(field)), axis=2)
normal /= np.linalg.norm(normal, axis=2, keepdims=True)
normal_roughness = np.ones_like(pixels)
normal_roughness[:, :, :3] = normal*.5+.5
normal_roughness[:, :, 3] = .78+.2*(1-field)
manifest = {'generator': 'export_rocket_cloud.py', 'source': 'source/'+source.name,
            'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'size': [width, height], 'textures': {}, 'texture_samples': {},
            'channels': {'rocket_cloud_albedo_height.png': 'linear soot albedo RGB; density/height A',
                         'rocket_cloud_normal_roughness.png': 'OpenGL tangent normal RGB; roughness A'}}
destination = HERE.parents[3]/'game/assets/models/effects/combat_effects'
for name, values in [('rocket_cloud_albedo_height.png', albedo_height),
                     ('rocket_cloud_normal_roughness.png', normal_roughness)]:
    path = HERE/name
    write_png(path, values)
    (destination/name).write_bytes(path.read_bytes())
    manifest['textures'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['texture_samples'][name] = [
        {'pixel': [x,y], 'rgba8': np.rint(np.clip(values[y,x],0,1)*255).astype(int).tolist()}
        for x,y in [(0,0),(width//3,height//3),(width//2,height//2),(width-1,height-1)]]
data = json.dumps(manifest, indent=2)+'\n'
(HERE/'rocket_cloud_rig.json').write_text(data)
(destination/'rocket_cloud_rig.json').write_text(data)
print('ROCKET_CLOUD_EXPORT_PASS', width, height)
