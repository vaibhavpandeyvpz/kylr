"""Deterministic lunar landforms and geological masks, in Godot world metres."""
from pathlib import Path
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
RESOLUTION = 512
ORIGIN = -256


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def foundations(markers):
    """Native rotated footprints and fixture approaches keep their zero plane."""
    result = []
    for marker in markers:
        architecture = marker.get('source_category', marker['category']) == 'architecture'
        if marker['position_blender'][2] > .6 and not architecture:
            continue
        if marker['role'] == 'jumbotron':
            continue
        x, y, _ = marker['position_blender']
        if architecture:
            asset = marker.get('source_asset', marker['asset'])
            metadata = json.loads((ROOT/'models/architecture'/asset/(asset+'_rig.json')).read_text(encoding='utf-8'))
            bounds = metadata['bounds_m']
            lo, hi = bounds['lo'], bounds['hi']
            result.append(dict(x=x,z=-y,yaw=marker['rotation_blender'][2],lo=lo[:2],hi=hi[:2],margin=1.0))
        else:
            result.append(dict(x=x,z=-y,radius=1.8 if marker['role'] in ('spawn','repair_station','portal','jump_pad') else 1.0))
    return result


def field(map_id, x, z, seats=()):
    radius = np.hypot(x,z)
    angle = np.arctan2(z,x)
    # Broad asymmetric ejecta ridges, with several breaches in the skyline.
    crest = 82 + 9*np.sin(angle*3+.4) + 5*np.sin(angle*7-1.3)
    rim = np.exp(-((radius-crest)/14)**2) * (16+6*np.sin(angle*5+.6)+3*np.sin(angle*11))
    outer = smooth((radius-40)/30)
    broad = (np.sin(x*.071+np.sin(z*.033))*np.cos(z*.061)+.35*np.sin((x-z)*.17))
    if map_id == 'faceoff':
        u=(x-z)/math.sqrt(2); v=(x+z)/math.sqrt(2)
        lobes=np.exp(-((u-11)/8)**2)+np.exp(-((u+11)/8)**2)
        banks=3.2*lobes*(np.exp(-((v-16)/6)**2)+np.exp(-((v+16)/6)**2))
        channels=-1.4*np.exp(-(u/22)**4)*(np.exp(-((v-25)/5)**2)+np.exp(-((v+25)/5)**2))
        scar=-.85*np.exp(-((u/7)**2+((v+10)/5)**2))
        relief=(banks+channels+scar+.12*broad)*smooth((radius-4)/5)
        height=relief*(1-outer)+rim+.65*broad*outer*smooth((240-radius)/50)
        # Signed distance to each real footprint; broad grading avoids lips.
        seating=np.ones_like(radius)
        nearest=np.full_like(radius,1000.0)
        disturbance=np.zeros_like(radius)
        for seat in seats:
            dx=x-seat['x']; dz=z-seat['z']
            if 'radius' in seat:
                distance=np.hypot(dx,dz)-seat['radius']
            else:
                c=math.cos(seat['yaw']);s=math.sin(seat['yaw'])
                lx=c*dx-s*dz;ly=-s*dx-c*dz
                distance=np.maximum.reduce([seat['lo'][0]-lx,lx-seat['hi'][0],seat['lo'][1]-ly,ly-seat['hi'][1]])-seat['margin']
            nearest=np.minimum(nearest,distance)
            seating=np.minimum(seating,smooth(distance/(2.5 if 'lo' in seat else 1.75)))
            disturbance=np.maximum(disturbance,1-smooth(np.maximum(distance,0)/6))
        height=np.sign(height)*np.minimum(np.abs(height)*seating,np.maximum(nearest,0)*.6)
    else:
        basin=-3.0*np.exp(-(radius/52)**4)
        scar=-5*np.exp(-((x+8)**2+(z-5)**2)/130)-3*np.exp(-((x-25)**2+(z+15)**2)/70)
        fissure=-1.8*np.exp(-((z-.3*x-4*np.sin(x*.05))/2.8)**2)*np.exp(-(x/48)**4)
        height=basin+scar+fissure+rim+(.8+outer)*broad*smooth((240-radius)/50)
        disturbance=np.zeros_like(radius)
    # Fractured bedrock shelves break the smooth bowl silhouette. They stay
    # outside Faceoff's walk boundary and clear of Skyfall's floating decks.
    shelves=np.zeros_like(radius)
    for cx,cz,rx,rz,turn,rise in [(-51,-20,11,8,.3,5),(48,25,12,7,.7,6),(-22,54,14,8,-.4,5),
                                 (24,-55,15,8,-.4,6),(-62,47,18,11,.8,7),(63,-48,18,10,.8,6),
                                 (-85,-15,20,12,.2,8),(87,18,22,12,.2,7),(-30,-83,21,12,-.4,7),(30,83,20,13,-.4,8)]:
        dx=x-cx;dz=z-cz;c=math.cos(turn);s=math.sin(turn)
        u=(c*dx+s*dz)/rx;v=(-s*dx+c*dz)/rz
        shape=np.maximum.reduce([np.abs(u),np.abs(v),np.abs(u+v)*.65])
        shelves=np.maximum(shelves,np.clip((1.1-shape)/.45,0,1)*rise)
    shelves*=smooth((np.maximum(np.abs(x),np.abs(z))-39)/6) if map_id=='faceoff' else smooth((radius-60)/10)
    height+=shelves
    height*=smooth((245-radius)/20)
    # Six height/slope-aware PBR weights; no lighting painted into albedo.
    slope=np.hypot(*np.gradient(height)) if height.ndim==2 and min(height.shape)>1 else np.zeros_like(height)
    exposure=smooth((slope-.12)/.5)
    basalt=np.clip(np.abs(broad)*.25+exposure*1.6+smooth((height-2)/8)*.35,0,2)
    bedrock=np.clip(np.abs(np.sin(x*.057+z*.091))*.3+smooth(shelves/6)*.9,0,1.2)
    rubble=np.clip(np.exp(-((radius-crest+12)/10)**2)*.55+np.maximum(-height,0)*.06,0,.65)
    compacted=disturbance*.65
    scorch=np.exp(-((x+8)**2+(z-5)**2)/90)*(.38 if map_id=='skyfall' else .08)
    others=np.stack([basalt,bedrock,rubble,compacted,scorch],axis=-1)
    dust=.8*(1-exposure*.8)
    weights=np.concatenate([dust[...,None],others],axis=-1)
    weights/=weights.sum(axis=-1,keepdims=True)
    return height.astype('<f4'),weights.astype('float32')


def generate(map_id, markers, output):
    from PIL import Image
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    x,z=np.meshgrid(np.arange(RESOLUTION)+ORIGIN,np.arange(RESOLUTION)+ORIGIN)
    seats=foundations(markers) if map_id=='faceoff' else []
    height,weights=field(map_id,x,z,seats)
    height.tofile(output/(map_id+'.rf'))
    for index in range(2):
        image=np.rint(weights[...,index*3:index*3+3]*255).astype('uint8')
        Image.fromarray(image).save(output/f'{map_id}_weights{index}.png')
    central=height[226:287,226:287]
    qa=[]
    for flat in (central.argmin(),central.argmax()):
        row,column=np.unravel_index(flat,central.shape)
        qa.append([int(column-30),float(central[row,column]),int(row-30)])
    record=dict(resolution=RESOLUTION,origin=ORIGIN,spacing=1.0,min_height=float(height.min()),max_height=float(height.max()),foundations=seats,qa_points=qa)
    (output/(map_id+'.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return record
