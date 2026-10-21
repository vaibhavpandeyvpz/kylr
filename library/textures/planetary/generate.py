"""ImageGen-derived periodic mineral PBR layers: albedo/height and OpenGL normal/roughness.

Image-generated original albedo sources supply mineral detail. Conservative
image-derived microrelief produces OpenGL normals and roughness; it is not scanned height.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[2]/'game/assets/textures/planetary'
SIZE=2048
TILE_METRES=4.0
LAYERS={
    'dust':(.0025,.95),
    'basalt':(.018,.87),
    'bedrock':(.018,.91),
    'rubble':(.015,.94),
    'compacted':(.004,.9),
    'scorch':(.005,.85),
}


def write_import(path):
    sidecar=path.with_suffix(path.suffix+'.import')
    if sidecar.exists():
        text=sidecar.read_text(encoding='utf-8')
        import re
        for key,value in [('compress/mode','2'),('compress/high_quality','true'),('compress/normal_map','2'),('mipmaps/generate','true')]:
            text=re.sub(r'^'+re.escape(key)+r'=.*$',key+'='+value,text,flags=re.MULTILINE)
    else:
        resource='res://'+path.relative_to(GAME.parents[2]).as_posix()
        text=f'[remap]\nimporter="texture"\ntype="CompressedTexture2D"\n[deps]\nsource_file="{resource}"\n[params]\ncompress/mode=2\ncompress/high_quality=true\ncompress/normal_map=2\nmipmaps/generate=true\nprocess/fix_alpha_border=false\n'
    # Packed normal alpha is roughness. Normal-map compression must not discard it.
    sidecar.write_text(text,encoding='utf-8')


def layer(name):
    # Reuse the canonical regolith boundary/periodic filtering contract.
    import importlib.util
    spec=importlib.util.spec_from_file_location('regolith_pbr',HERE.parent/'lunar_surface/generate.py')
    shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
    with Image.open(HERE/'sources'/f'{name}_albedo.png') as image:
        base=np.asarray(image.convert('RGB').resize((SIZE,SIZE),Image.Resampling.LANCZOS),dtype=np.float32)/255
    channels=[shared.periodic(base[:,:,c]) for c in range(3)]
    # Remove broad illumination drift while retaining mineral-scale variation.
    albedo=np.clip(np.stack([c-shared.blur(c,SIZE/8)+c.mean() for c in channels],axis=-1),0,1)
    luminance=albedo @ np.array([.2126,.7152,.0722])
    detail=shared.blur(luminance,1.0)-shared.blur(luminance,48)
    relative=np.clip(detail/max(float(detail.std()),.01),-2.5,2.5)/2.5
    relief,roughness=LAYERS[name]
    # Image-derived microrelief is an authored approximation, not scan height.
    height=relative*relief
    spacing=TILE_METRES/SIZE
    dx=(np.roll(height,-1,1)-np.roll(height,1,1))/(2*spacing)
    dy=(np.roll(height,-1,0)-np.roll(height,1,0))/(2*spacing)
    normal=np.stack([-dx,dy,np.ones_like(dx)],axis=-1)
    normal/=np.linalg.norm(normal,axis=-1,keepdims=True)
    ah=np.concatenate([albedo,(relative*.45+.5)[...,None]],axis=-1)
    nr=np.concatenate([normal*.5+.5,np.clip(roughness-relative*.06,.68,.99)[...,None]],axis=-1)
    return ah,nr


def generate():
    GAME.mkdir(parents=True,exist_ok=True)
    records={}
    for name in LAYERS:
        for suffix,value in zip(['albedo_height','normal_roughness'],layer(name)):
            image=Image.fromarray(np.rint(np.clip(value,0,1)*255).astype('uint8'),'RGBA')
            path=GAME/f'{name}_{suffix}.png';image.save(path,optimize=True)
            write_import(path)
            records[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        print('PLANETARY_PBR',name,flush=True)
    previous=json.loads((GAME/'manifest.json').read_text(encoding='utf-8')) if (GAME/'manifest.json').exists() else {}
    for path in GAME.glob('*_weights*.png'):records[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (GAME/'manifest.json').write_text(json.dumps(dict(resolution=SIZE,tile_metres=TILE_METRES,layers=list(LAYERS),source_sha256={name:hashlib.sha256((HERE/'sources'/f'{name}_albedo.png').read_bytes()).hexdigest() for name in LAYERS},files=records,maps=previous.get('maps',{})),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__': generate()
