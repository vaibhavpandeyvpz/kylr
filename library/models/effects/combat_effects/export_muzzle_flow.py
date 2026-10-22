"""Derive matching emissive gas material maps from the authored flame flow."""
from pathlib import Path
import hashlib
import json
import sys
import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from texture_io import write_png

source = HERE/'source/muzzle_flow_source.png'
image = bpy.data.images.load(str(source))
image.colorspace_settings.name = 'Non-Color'
width, height = image.size
assert width == height and width >= 1024
pixels = np.array(image.pixels[:], dtype=np.float32).reshape(height,width,4)[::-1]
density = pixels[:,:,:3].mean(axis=2)
assert np.isfinite(density).all() and np.ptp(density) > .7
color = np.stack((density, density**1.7*.9, density**3*.65, density),axis=2)
dx = (np.roll(density,-1,axis=1)-np.roll(density,1,axis=1))*width*.012
dy = (np.roll(density,1,axis=0)-np.roll(density,-1,axis=0))*height*.012
normal = np.stack((-dx,-dy,np.ones_like(density)),axis=2)
normal /= np.linalg.norm(normal,axis=2,keepdims=True)
relief = np.concatenate((normal*.5+.5,(.75+.24*(1-density))[:,:,None]),axis=2)
manifest = {'generator':'export_muzzle_flow.py','source':'source/'+source.name,
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'size':[width,height],'textures':{},'texture_samples':{},
            'channels':{'muzzle_albedo_density.png':'linear hot-gas color RGB; density A',
                        'muzzle_normal_roughness.png':'OpenGL tangent normal RGB; roughness A'}}
destination = HERE.parents[3]/'game/assets/models/effects/combat_effects'
for name, values in [('muzzle_albedo_density.png',color),('muzzle_normal_roughness.png',relief)]:
    path = HERE/name
    write_png(path,values)
    (destination/name).write_bytes(path.read_bytes())
    manifest['textures'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['texture_samples'][name] = [
        {'pixel':[x,y],'rgba8':np.rint(np.clip(values[y,x],0,1)*255).astype(int).tolist()}
        for x,y in [(0,0),(width//3,height//3),(width//2,height//2),(width-1,height-1)]]
data = json.dumps(manifest,indent=2)+'\n'
(HERE/'muzzle_flow_rig.json').write_text(data)
(destination/'muzzle_flow_rig.json').write_text(data)
print('MUZZLE_FLOW_EXPORT_PASS',width,height)
