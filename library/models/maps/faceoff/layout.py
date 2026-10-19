"""Faceoff placements from the audited 75 m Figma frame; native prop axes."""
import json,math,re
from pathlib import Path
HERE=Path(__file__).resolve().parent;MODELS=HERE.parents[1]
ARCH={'cistern','container','container_long','hangar','lodge','habitat_pod','shelter','hub','bastion','laboratory'}
ENV={'storage_rack','lunar_rover','weather_sensor','solar_tower','lunar_lander','beacon_lantern','barrel','pole_light','satellite'}
ALIASES={'emp':'emp_gun','rocket_pack':'rocket_launcher','wather_sensor':'weather_sensor'}
def slug(text):return '_'.join(text.lower().replace('-',' ').split())
def data():
    tree=json.loads((HERE/'figma_inspection.json').read_text());nodes={n[0]:n for n in tree['rows']};markers=[];holes=[]
    for ident,label,kind,parent,w,h,t in tree['rows']:
        if kind not in ('RECTANGLE','ELLIPSE') or label=='Bleed':continue
        path=[];p=parent
        while p in nodes:node=nodes[p];path.insert(0,node[1]);p=node[3]
        center=[t[0][2]+t[0][0]*w/2+t[0][1]*h/2-tree['origin'][0][2],t[1][2]+t[1][0]*w/2+t[1][1]*h/2-tree['origin'][1][2]]
        x=(center[0]-3750)/100;y=(3750-center[1])/100;yaw=-math.atan2(t[1][0],t[0][0]);z=0
        zone='A' if 'Zone A' in path else 'B' if 'Zone B' in path else 'common'
        level='upper' if 'First Floor' in path else 'ground';role='prop';weapon=None
        asset=ALIASES.get(slug(re.sub(r'\s+\d+$','',label)),slug(re.sub(r'\s+\d+$','',label)))
        building=next((slug(p) for p in reversed(path) if slug(p) in ARCH),None)
        lower=label.lower()
        if lower.startswith(('ammo pickup','ammo pack')):
            role='ammo';weapon=ALIASES.get(slug(label.split(' - ')[-1]),slug(label.split(' - ')[-1]));asset=weapon
        elif lower.startswith('weapon pickup'):
            role='weapon';weapon=ALIASES.get(slug(label.split(' - ')[-1].split(' (')[0]),slug(label.split(' - ')[-1].split(' (')[0]));asset='item_cradle' if 'cradle' in lower else 'weapon_holder'
        elif 'core pickup' in lower:role='shield' if lower.startswith('shield') else 'energy';asset='item_cradle' if 'cradle' in lower else 'item_table'
        elif lower.startswith('spawn point'):role='spawn';asset='stasis_chamber' if 'stasis' in lower else 'spawn_point'
        elif lower.startswith('flag'):role='flag_base';asset='ctf_flag'
        elif lower.startswith('pulse gun'):role='pulse_gun';asset='pulse_gun'
        elif lower.startswith('jump pad'):role='jump_pad';asset='jump_pad'
        elif lower.startswith('portal'):role='portal';asset='portal_gate'
        elif lower.startswith('repair station'):role='repair_station';asset='repair_station'
        elif lower=='jumbotron':role='jumbotron';asset='jumbotron';z=10
        category='architecture' if asset in ARCH else 'environments' if asset in ENV or asset=='jumbotron' else 'weapons' if role=='ammo' else 'gameplay'
        if building and category!='architecture':
            metadata=json.loads((MODELS/'architecture'/building/(building+'_rig.json')).read_text())
            z=metadata.get('upper_floor_m',{}).get('elevation',0) if level=='upper' else metadata['architecture_dimensions']['rooms'][0]['floor_m']
        marker=dict(name=f'{zone}-{asset}-{ident.replace(":","_")}',role=role,asset=asset,category=category,weapon=weapon,zone=zone,level=level,deck=building or 'common',building=building,
            position_blender=[x,y,z],position_godot=[x,z,-y],rotation_blender=[0,0,yaw],figma_node=ident,label=label,wall_mounted=False,cutout_m=[0,0])
        if role=='portal':marker['pair_label']=label
        if role=='pulse_gun':marker['team']=0 if zone=='A' else 1
        markers.append(marker)
    # Some Figma pickups overlap a cargo container without being parented to it.
    # Resolve those hosts from their native footprint before rotating placements.
    for item in markers:
        if item['asset']!='item_cradle' or item['building']:continue
        candidates=[]
        for host in markers:
            if host['category']!='architecture' or host['asset'] not in ('container','container_long'):continue
            metadata=json.loads((MODELS/'architecture'/host['asset']/(host['asset']+'_rig.json')).read_text())
            x,y,z=host['position_blender'];ix,iy,_=item['position_blender'];a=host['rotation_blender'][2]
            dx,dy=ix-x,iy-y;lx=math.cos(a)*dx+math.sin(a)*dy;ly=-math.sin(a)*dx+math.cos(a)*dy
            bounds=metadata['bounds_m']
            if bounds['lo'][0]<=lx<=bounds['hi'][0] and bounds['lo'][1]<=ly<=bounds['hi'][1]:
                candidates.append((dx*dx+dy*dy,host,metadata,z))
        if candidates:
            _,host,metadata,z=min(candidates,key=lambda c:c[0])
            item['building']=host['asset'];item['deck']=host['asset']
            item['position_blender'][2]=z+metadata['architecture_dimensions']['rooms'][0]['floor_m']
    # Common props face the lunar centre; contained placements rotate with hosts.
    buildings={m['asset']:m for m in markers if m['category']=='architecture'}
    for asset,host in buildings.items():
        x,y,_=host['position_blender'];old=host['rotation_blender'][2]
        # The pod's Figma footprint is drawn rear-to-front relative to native -Y.
        # Resolve that host axis before facing the centre, keeping ammo in front
        # and the cradle behind it instead of rotating their positions 180 degrees.
        if asset=='habitat_pod':old+=math.pi
        angle=math.atan2(-x,y) if host['zone']=='common' and math.hypot(x,y)>1e-6 else old
        delta=angle-old;host['rotation_blender'][2]=angle
        for item in markers:
            if item['building']!=asset or item['category']=='architecture':continue
            ix,iy,iz=item['position_blender'];dx,dy=ix-x,iy-y
            bounds=json.loads((MODELS/'architecture'/asset/(asset+'_rig.json')).read_text())['bounds_m']
            local_x=math.cos(old)*dx+math.sin(old)*dy;local_y=-math.sin(old)*dx+math.cos(old)*dy
            if item['level']=='ground' and not (bounds['lo'][0]<=local_x<=bounds['hi'][0] and bounds['lo'][1]<=local_y<=bounds['hi'][1]):iz=0
            item['position_blender']=[x+math.cos(delta)*dx-math.sin(delta)*dy,y+math.sin(delta)*dx+math.cos(delta)*dy,iz]
            item['rotation_blender'][2]+=delta
        if asset in ('container','container_long'):host['open_actions']=['rear_open'] if asset=='container' else ['front_open','rear_open']
    for item in markers:
        x,y,z=item['position_blender'];item['position_godot']=[x,z,-y]
        # Native racks face -Y; their +Y backs belong against the lab's +X wall.
        if item['asset']=='storage_rack' and item['building']=='laboratory':item['rotation_blender'][2]+=math.pi/2
        if ((item['category']=='architecture') or (item['zone']=='common' and not item['building'] and item['role']!='jumbotron')) and math.hypot(x,y)>1e-6:item['rotation_blender'][2]=math.atan2(-x,y)
        if item['asset'] not in ('spawn_point','weapon_holder','item_table','jump_pad'):continue
        meta=json.loads((MODELS/'gameplay'/item['asset']/(item['asset']+'_rig.json')).read_text());cut=meta['cutout_m']
        w,h=(2,2) if item['asset']=='spawn_point' else (1,1);item['cutout_m']=[w,h]
        offset=sum(cut.get('y',[0,0]))/2;a=item['rotation_blender'][2]
        holes.append(dict(marker=item['name'],building=item['building'],center=[x-math.sin(a)*offset,y+math.cos(a)*offset,z],size=[w,h],depth=cut['depth'],yaw=a))
    expanded=[]
    for item in markers:
        if item['role']!='ammo':expanded.append(item);continue
        x,y,z=item['position_blender'];a=item['rotation_blender'][2]
        for side,delta in [('L',-.1),('R',.1)]:
            copy=dict(item);copy['name']+='-'+side;copy['position_blender']=[x+math.cos(a)*delta,y+math.sin(a)*delta,z];copy['position_godot']=[copy['position_blender'][0],z,-copy['position_blender'][1]];expanded.append(copy)
    for host in expanded:
        if host['category']=='architecture' and any(h['building']==host['asset'] for h in holes):
            host['asset_suffix']='_architecture_'+host['asset'];host['source_asset']=host['asset'];host['source_category']='architecture';host['category']='maps';host['asset']='faceoff'
    expanded.append(dict(name='lunar-scenery',role='prop',asset='faceoff',category='maps',asset_suffix='_scenery',
        zone='common',building=None,level='common',position_blender=[0,0,0],position_godot=[0,0,0],rotation_blender=[0,0,0],
        figma_node='143:891',load_at_start=True,budget_excluded=True))
    return expanded,holes
