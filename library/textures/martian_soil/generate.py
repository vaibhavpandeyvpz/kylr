"""Six periodic Martian albedo/height and OpenGL normal/roughness layers."""
from pathlib import Path
import hashlib
import importlib.util
import json
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[2]/'game/assets/textures/martian_soil'
SIZE=2048
TILE_METRES=4.0
LAYERS={'dust':(.003,.95),'dunes':(.008,.94),'bedrock':(.018,.9),
        'rubble':(.016,.94),'strata':(.022,.9),'sediment':(.005,.87)}


def generate():
    spec=importlib.util.spec_from_file_location('periodic_regolith',HERE.parent/'lunar_surface/generate.py')
    shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
    spec=importlib.util.spec_from_file_location('layer_import',HERE.parent/'planetary/generate.py')
    imports=importlib.util.module_from_spec(spec);spec.loader.exec_module(imports)
    GAME.mkdir(parents=True,exist_ok=True);records={};sources={}
    for name,(relief,roughness) in LAYERS.items():
        source=HERE/'sources'/f'{name}_albedo.png'
        base=np.asarray(Image.open(source).convert('RGB').resize((SIZE,SIZE),Image.Resampling.LANCZOS),dtype=np.float32)/255
        channels=[shared.periodic(base[:,:,c]) for c in range(3)]
        albedo=np.clip(np.stack([c-shared.blur(c,SIZE/8)+c.mean() for c in channels],axis=-1),0,1)
        luminance=albedo @ np.array([.2126,.7152,.0722])
        detail=shared.blur(luminance,1)-shared.blur(luminance,48)
        relative=np.clip(detail/max(float(detail.std()),.01),-2.5,2.5)/2.5
        height=relative*relief;spacing=TILE_METRES/SIZE
        dx=(np.roll(height,-1,1)-np.roll(height,1,1))/(2*spacing)
        dy=(np.roll(height,-1,0)-np.roll(height,1,0))/(2*spacing)
        normal=np.stack([-dx,dy,np.ones_like(dx)],axis=-1);normal/=np.linalg.norm(normal,axis=-1,keepdims=True)
        ah=np.concatenate([albedo,(relative*.45+.5)[...,None]],axis=-1)
        nr=np.concatenate([normal*.5+.5,np.clip(roughness-relative*.06,.68,.99)[...,None]],axis=-1)
        for suffix,value in [('albedo_height',ah),('normal_roughness',nr)]:
            path=GAME/f'{name}_{suffix}.png'
            Image.fromarray(np.rint(np.clip(value,0,1)*255).astype('uint8')).save(path,optimize=True)
            imports.write_import(path)
            # The shared importer discovers its own asset root; correct the source root here.
            sidecar=path.with_suffix('.png.import');text=sidecar.read_text()
            resource='res://'+path.relative_to(GAME.parents[2]).as_posix()
            import re
            text=re.sub(r'source_file="[^"]+"',f'source_file="{resource}"',text)
            sidecar.write_text(text)
            records[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        sources[name]=hashlib.sha256(source.read_bytes()).hexdigest()
        print('MARTIAN_PBR',name,flush=True)
    previous=json.loads((GAME/'manifest.json').read_text()) if (GAME/'manifest.json').exists() else {}
    (GAME/'manifest.json').write_text(json.dumps(dict(layers=list(LAYERS),resolution=SIZE,tile_metres=TILE_METRES,
        source_sha256=sources,files=records,terrain=previous.get('terrain',{}),
        relief='Conservative image-derived microrelief, not scanned displacement'),indent=2)+'\n')

if __name__=='__main__':generate()
