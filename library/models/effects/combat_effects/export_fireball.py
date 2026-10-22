"""Validate and deliver the original bitmap source without altering its pixels."""
from pathlib import Path
import hashlib
import json
import shutil
import bpy
import numpy as np

HERE = Path(__file__).resolve().parent

def export(name):
    source = HERE/'source'/(name+'.png')
    image = bpy.data.images.load(str(source))
    width,height = image.size
    assert width == height and width >= 1024
    rgba = np.array(image.pixels[:],dtype=np.float32).reshape(height,width,4)[::-1]
    assert np.isfinite(rgba).all()
    occupied = []
    for frame in range(16):
        row,col = divmod(frame,4)
        x0,x1 = round(col*width/4),round((col+1)*width/4)
        y0,y1 = round(row*height/4),round((row+1)*height/4)
        alpha = rgba[y0:y1,x0:x1,3]
        occupied.append(int(np.count_nonzero(alpha>.01)))
        assert occupied[-1]>128,(name,frame,'empty frame')
        assert max(alpha[0].max(),alpha[-1].max(),alpha[:,0].max(),alpha[:,-1].max())<=.01,(name,frame,'clipped cell')
    destination = HERE/(name+'.png')
    shutil.copyfile(source,destination)
    (HERE/(name+'_rig.json')).write_text(json.dumps({
        'source':'source/'+name+'.png','generator':'OpenAI built-in imagegen',
        'preparation':'export_fireball.py; pixel-preserving validation and copy',
        'atlas_size':[width,height],'tile_size':width/4,'grid':[4,4],'frames':16,
        'scientific_validation':False,'occupied_pixels':occupied,
        'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()
    },indent=2)+'\n')
    bpy.data.images.remove(image)
    print('[effect atlas]',name,'validated sixteen nonempty, unclipped frames',width,height)


for atlas in ('fireball_atlas','flak_dust_atlas','fire_contact_atlas'):
    export(atlas)
