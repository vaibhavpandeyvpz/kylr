"""Pack generated flame/smoke scalar sources into repeatable VFX material maps."""
from pathlib import Path
import hashlib
import json
import sys
import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from texture_io import write_png

destination = HERE.parents[3]/'game/assets/models/effects/combat_effects'
manifest = {'generator': 'export_fireball_material.py', 'sources': {},
            'textures': {}, 'texture_samples': {}, 'channels': {}}
for kind in ('flame', 'smoke'):
    source = HERE/'source'/('fireball_'+kind+'_source.png')
    image = bpy.data.images.load(str(source))
    image.colorspace_settings.name = 'Non-Color'
    width, height = image.size
    assert width == height and width >= 1024
    rgba = np.array(image.pixels[:], dtype=np.float32).reshape(height,width,4)[::-1]
    field = rgba[:,:,:3].mean(axis=2)
    assert np.isfinite(field).all() and np.ptp(field) > .5
    manifest['sources'][source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    albedo = np.ones_like(rgba)
    if kind == 'flame':
        albedo[:,:,:3] = np.stack((.65+field*.35,.025+field**1.5*.38,.002+field**3*.04),axis=2)
    else:
        albedo[:,:,:3] = (.06+field[:,:,None]*.17)*np.array([.94,.97,1.0])
    albedo[:,:,3] = field
    dx = (np.roll(field,-1,axis=1)-np.roll(field,1,axis=1))*width*.012
    dy = (np.roll(field,1,axis=0)-np.roll(field,-1,axis=0))*height*.012
    normal = np.stack((-dx,-dy,np.ones_like(field)),axis=2)
    normal /= np.linalg.norm(normal,axis=2,keepdims=True)
    relief = np.concatenate((normal*.5+.5,(.8+.19*(1-field))[:,:,None]),axis=2)
    for suffix, values, channels in [('albedo_density',albedo,'linear albedo RGB; density/height A'),
                                     ('normal_roughness',relief,'OpenGL tangent normal RGB; roughness A')]:
        name = 'fireball_'+kind+'_'+suffix+'.png'
        path = HERE/name
        write_png(path,values)
        (destination/name).write_bytes(path.read_bytes())
        manifest['textures'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest['channels'][name] = channels
        manifest['texture_samples'][name] = [
            {'pixel':[x,y],'rgba8':np.rint(np.clip(values[y,x],0,1)*255).astype(int).tolist()}
            for x,y in [(0,0),(width//3,height//3),(width//2,height//2),(width-1,height-1)]]
data = json.dumps(manifest,indent=2)+'\n'
(HERE/'fireball_material_rig.json').write_text(data)
(destination/'fireball_material_rig.json').write_text(data)
print('FIREBALL_MATERIAL_EXPORT_PASS',len(manifest['textures']))
