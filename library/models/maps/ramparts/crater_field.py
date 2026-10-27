"""Deterministic height and deposit fields for Terrain3D's Martian crater bake."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
from layout import settings


def smooth(v):
    t=np.clip(v,0,1);return t*t*(3-2*t)


def field(x,z):
    recipe=settings()['crater'];radius=recipe['diameter_m']/2;depth=recipe['depth_m'];peak=recipe['rim_height_m']
    r=np.hypot(x,z);a=np.arctan2(z,x)
    scales=np.array([0,.69,.8,.88,.94,1,1.06,1.14,1.24,1.38,1.62,2,3.2,4])
    levels=np.array([-depth,-depth,-13,-9.5,-4.5,2,7,peak*.65,peak,peak*.65,10,4,1,0])
    base=np.interp(r/radius,scales,levels)
    ridge=.9+.18*np.sin(a*3+.7)+.12*np.sin(a*7+2.4)+.07*np.sin(a*13)
    mountain=smooth((r-radius)/9)*(1-smooth((r-160)/65))
    height=base*(1-mountain+mountain*ridge)
    erosion=np.sin(a*23+r*.07)*np.sin(a*9-r*.05)
    height+=mountain*np.minimum(np.maximum(base,0)*.09,2)*erosion
    gullies=(.5+.5*np.sin(a*19+1.7*np.sin(r*.075)))**5
    height-=mountain*4.5*gullies
    fracture=np.sin(x*.39+1.4*np.sin(z*.13))*np.sin(z*.34+.8*np.sin(x*.11))
    height+=mountain*1.7*fracture
    shelves=(np.floor(np.maximum(height,0)/2.6)*2.6-height)*.22*mountain
    height+=shelves
    dune_zone=smooth((r-112)/12)*(1-smooth((r-175)/25))
    wind=x*.83+z*.56+2*np.sin(z*.027)
    ripples=(.5+.5*np.sin(wind*.62+1.2*np.sin(z*.05)))**2.6
    height+=dune_zone*(ripples*1.7-.3)
    height+=smooth((r-55)/18)*.3*np.sin(x*.16+z*.09)*np.sin(z*.2-x*.055)
    height=np.maximum(height,-depth)
    slope=np.hypot(*np.gradient(height)) if height.ndim==2 else np.zeros_like(height)
    exposure=smooth((slope-.15)/.7)
    dust=.65*(1-exposure*.7)+.12*np.sin(x*.07-z*.05)
    dunes=.05+dune_zone*(.7+.25*np.sin(x*.025+z*.04))
    bedrock=.1+exposure*.8+smooth((np.sin(x*.12+z*.07)-.2)/.6)*.55
    rubble=.07+smooth((np.sin(x*.16-z*.11+np.sin(z*.17))-.1)/.7)*.8
    strata=.05+exposure*1.1+mountain*.35
    sediment=smooth((-height-.5)/8)*1.5
    weights=np.maximum(np.stack([dust,dunes,bedrock,rubble,strata,sediment],axis=-1),.01)**4
    weights/=weights.sum(axis=-1,keepdims=True)
    return height.astype('<f4'),weights.astype('float32')


def generate(output):
    from PIL import Image
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    x,z=np.meshgrid(np.arange(512)-256,np.arange(512)-256)
    height,weights=field(x,z);height.tofile(output/'ramparts.rf')
    target=Path(__file__).resolve().parents[4]/'game/assets/textures/martian_soil'
    target.mkdir(parents=True,exist_ok=True)
    for i in range(2):
        image=Image.fromarray(np.rint(weights[...,i*3:i*3+3]*255).astype('uint8'))
        image.save(output/f'ramparts_weights{i}.png');image.save(target/f'ramparts_weights{i}.png')
    record=dict(resolution=512,origin=-256,spacing=1,outer_lod=2,single_grid=True,min_height=float(height.min()),max_height=float(height.max()),
                crater=settings()['crater'],height_sha256=hashlib.sha256(height.tobytes()).hexdigest())
    (output/'ramparts.json').write_text(json.dumps(record,indent=2)+'\n')
    manifest_path=target/'manifest.json';manifest=json.loads(manifest_path.read_text())
    manifest['terrain']=record;manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    return record
