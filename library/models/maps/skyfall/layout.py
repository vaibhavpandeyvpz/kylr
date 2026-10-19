"""Skyfall's Figma-authored placements, independent of previous maps."""
import json,math,re,sys,itertools
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'common'));sys.path.insert(0,str(HERE.parent/'common/platform'))
from platform_placements import thruster_positions
from platform_layout import consolidate
HEIGHTS={'common':0,'lower':22,'higher':26,'roof':30}
ARCHITECTURE={'cistern','container_long','container','hangar','lodge','bastion','laboratory','habitat_pod','shelter','hub','bunker','lunar_dome'}
ENVIRONMENT={'barrel','storage_rack','lunar_rover','weather_sensor','solar_tower','lunar_lander','beacon_lantern','pole_light','satellite','terminal','workstation','roof_display_assembly','thruster','pillar'}
ALIASES={'wather_sensor':'weather_sensor','speedramp':'speed_ramp','flak_cannon':'flak_cannon','rocket_pack':'rocket_launcher','rocket_launcher':'rocket_launcher','lightning_gun':'lightning_gun','emp':'emp_gun','bio_rifle':'bio_rifle'}
def slug(text):return '_'.join(text.lower().replace('-',' ').split())
def data():
    rows=json.loads((HERE/'figma_layout.json').read_text())['placements']
    decks={};markers=[];cuts=[]
    for index,row in enumerate(rows):
        index=row.get('placement_index',index)
        if row['label']=='Jumbotron':continue
        path=row['path'];name=row['label'];lower=name.lower();tag='A' if path[0]=='Zone A' else 'B' if path[0]=='Zone B' else 'common'
        area=next((slug(p) for p in path if p.startswith(('Mainland','Island'))),'common')
        level=('roof' if any(p in ('Rooftop','1st Floor') for p in path) else
            'higher' if 'Higher ground' in path else 'lower' if tag!='common' else 'common')
        # Island 2 has a lower deck and one upper level; Island 1 and its bridge meet the lower mainland.
        if area=='island_2' and '1st Floor' in path:level='higher'
        key=f'{tag}_{area}_{level}'
        if name.startswith('Bridge'):key=f'{tag}_bridge_lower';level='lower'
        x=(row['center_px'][0]-3750)/100;y=(3750-row['center_px'][1])/100;z=HEIGHTS[level]
        yaw=-row['angle']
        w,h=[v/100 for v in row['size_px']]
        if name.startswith(('Platform','Bridge')):
            if abs(math.sin(yaw))>.9:w,h=h,w
            decks.setdefault(key,dict(name=key,z=z,rects=[],holes=[]))['rects'].append([x-w/2,y-h/2,x+w/2,y+h/2])
            modules=[]
            if name.startswith('Bridge'):
                modules=[('bridge',x-w/4,y,5,5),('bridge',x+w/4,y,5,5)] if w>h else [('bridge',x,y-h/4,5,5),('bridge',x,y+h/4,5,5)]
            elif '2x10' in name:
                modules=[('platform_lip_2x5',x,y-2.5,2,5),('platform_lip_2x5',x,y+2.5,2,5)]
            else:
                asset=slug(name);modules=[(asset,x,y,w,h)]
            for part,(asset,mx,my,mw,mh) in enumerate(modules):
                native_w,native_h=(5,5) if asset=='bridge' else map(int,asset.split('_')[-1].split('x'))
                heading=yaw
                if abs(mw-native_w)>.01:heading+=math.pi/2
                if asset=='bridge' and w>h:heading=math.pi/2
                rear_origin=asset.startswith('platform_lip') or asset=='bridge'
                ox=mx-math.sin(heading)*native_h/2 if rear_origin else mx
                oy=my+math.cos(heading)*native_h/2 if rear_origin else my
                markers.append(dict(name=f'{tag}-{asset}-{index}-{part}',role='platform',asset='skyfall',helper_family=asset,category='maps',weapon=None,
                    zone=tag,deck=key,level=level,position_blender=[ox,oy,z],position_godot=[ox,z,-oy],rotation_blender=[0,0,heading],
                    figma_node=row['figma_node'],mirrored_from=row.get('mirrored_from'),label=name,wall_mounted=False,cutout_m=[0,0],
                    underbody=False,module_rect=[mx-mw/2,my-mh/2,mx+mw/2,my+mh/2],asset_suffix=f'_module_{asset}_{key}_{index}_{part}'))
            continue
        if lower.startswith('hole'):
            if abs(math.sin(yaw))>.9:w,h=h,w
            cuts.append((key,[x,y,z],[w,h]));continue
        if lower.startswith('weapon pickup wall'):
            decks[key].setdefault('walls',[]).append([x,y,z,2,2,2])
            markers.append(dict(name=f'{tag}-weapon-wall-{index}',role='prop',asset='weapon_holder_wall',category='architecture',weapon=None,
                zone=tag,deck=key,level=level,position_blender=[x,y,z],position_godot=[x,z,-y],rotation_blender=[0,0,yaw],
                figma_node=row['figma_node'],label=name,wall_mounted=False,cutout_m=[0,0],load_at_start=True,budget_excluded=True))
            continue
        role='prop';asset=slug(re.sub(r'\s+\d+$','',name));asset=ALIASES.get(asset,asset);category='gameplay';weapon=None
        if lower.startswith(('ammo pickup','ammo pack')):
            role='ammo';weapon=ALIASES.get(slug(name.split(' - ')[-1]),slug(name.split(' - ')[-1]));asset=weapon;category='weapons'
        elif lower.startswith('weapon pickup'):
            role='weapon';weapon=ALIASES.get(slug(name.split(' - ')[-1].split(' (')[0]),slug(name.split(' - ')[-1].split(' (')[0]));asset='item_cradle' if 'cradle' in lower else 'weapon_holder'
        elif 'core pickup' in lower:
            role='shield' if lower.startswith('shield') else 'energy';asset='item_cradle' if 'cradle' in lower else 'item_table'
        elif lower.startswith('spawn point'):
            role='spawn';asset='stasis_chamber' if 'stasis chamber' in lower else 'spawn_point'
        elif lower.startswith('flag'):
            role='flag_base';asset='ctf_flag'
            z+=.1096605744 if tag=='A' else .1
        elif lower.startswith('jump pad'):role='jump_pad';asset='jump_pad'
        elif lower.startswith('portal'):role='portal';asset='portal_gate'
        elif lower.startswith('barricade'):role='barricade';asset='barricade';yaw+=math.pi/2
        elif lower.startswith('pressure plate'):role='pressure_plate';asset='pressure_plate';yaw+=math.pi/2
        elif lower.startswith('pulse gun'):role='pulse_gun';asset='pulse_gun'
        elif lower.startswith('pillar'):role='pillar';asset='pillar'
        elif lower.startswith('thruster'):role='thruster';asset='thruster';z-=.8
        elif lower.startswith('repair station'):role='repair_station';asset='repair_station'
        elif lower=='speedramp':role='speed_ramp';asset='speed_ramp'
        if asset in ARCHITECTURE:category='architecture'
        if asset in ENVIRONMENT:category='environments'
        if category=='architecture' and tag!='common':z=HEIGHTS['roof']
        # Props inside delivered buildings sit on their actual floor elevations.
        building=next((slug(p) for p in path if slug(p) in ARCHITECTURE),None)
        if building and category!='architecture':
            meta=json.loads((HERE.parents[1]/'architecture'/building/(building+'_rig.json')).read_text())
            dims=meta.get('architecture_dimensions',{})
            levels=dims.get('rooms',[])
            if 'First Floor' in path:z=HEIGHTS[level]+float(meta.get('upper_floor_m',{}).get('elevation',3.45))
            elif levels:z=HEIGHTS[level]+float(levels[0].get('floor_m',0))
        id=f'{tag}-{asset or role}-{index}'
        marker=dict(name=id,role=role,asset=asset,category=category,weapon=weapon,
            zone=tag,deck=key,level=level,position_blender=[x,y,z],position_godot=[x,z,-y],
            rotation_blender=[0,0,yaw],figma_node=row['figma_node'],mirrored_from=row.get('mirrored_from'),label=name,
            wall_mounted=False,cutout_m=[0,0])
        if role=='pulse_gun':marker['team']=0 if name.endswith(' A') else 1
        if role=='pillar':
            marker['upper_level']='roof' if level=='higher' else 'higher'
            marker['support_height_m']=2.2
            marker['support_open_time_s']=0.7166281755196307 # Native eased clip sampled between frames 21 and 22.
        if role=='portal':marker['pair_label']=name
        markers.append(marker)
    for m in markers:
        mainland_front='mainland_1' in m['deck'] and m['role'] not in ('platform','thruster','pillar','barricade','pressure_plate') and m['asset']!='weapon_holder_wall'
        terminal=m['asset']=='terminal' and m['zone']!='common'
        if m['role']=='portal' or m['asset'] in ('lunar_dome','bunker','stasis_chamber') or mainland_front or terminal:
            m['rotation_blender'][2]+=(-math.pi/2 if terminal and 'mainland_2' in m['deck'] else math.pi/2)
            m['placement_yaw_offset_deg']=90
    markers=consolidate(markers)
    for m in markers:
        if m['role']=='platform' and m['helper_family']=='platform':
            m['underbody']=any(p['role']=='thruster' and p['deck']==m['deck'] for p in markers)
    # Figma chooses the platform and thruster count. Native platform sockets
    # own the mounting position and axes; never reshape a chassis around map XY.
    for platform in [p for p in markers if p['role']=='platform' and p['underbody']]:
        mounts=[m for m in markers if m['role']=='thruster' and m['deck']==platform['deck']]
        family=platform['helper_family'];w,h=platform['size_m']
        native=thruster_positions(w,h)
        assert len(native)==len(mounts),(family,len(native),len(mounts))
        px,py,pz=platform['position_blender'];angle=platform['rotation_blender'][2]
        positions=[[px+math.cos(angle)*x-math.sin(angle)*y,py+math.sin(angle)*x+math.cos(angle)*y,pz-2.3] for x,y in native]
        assignment=min(itertools.permutations(range(len(native))),key=lambda order:sum(sum((a-b)**2 for a,b in zip(m['position_blender'][:2],positions[j][:2])) for m,j in zip(mounts,order)))
        for m,j in zip(mounts,assignment):
            m['figma_position_blender']=m['position_blender'][:]
            m['position_blender']=positions[j]
            m['position_godot']=[positions[j][0],positions[j][2],-positions[j][1]]
            m['rotation_blender']=platform['rotation_blender'][:]
            m['parent_fixture']=platform['name'];m['parent_socket']=f'ThrusterMount{j+1:02d}'
            m['placement_source']='native platform socket'
    for key,center,size in cuts:decks[key]['holes'].append(dict(center=center,size=size,depth=2.01))
    for m in markers:
        if m['asset'] not in ('spawn_point','weapon_holder','item_table','jump_pad','pressure_plate','barricade'):continue
        asset=m['asset'];p=json.loads((HERE.parents[1]/'gameplay'/asset/(asset+'_rig.json')).read_text())['cutout_m']
        w,h={'spawn_point':(2,2),'weapon_holder':(1,1),'item_table':(1,1),'barricade':(4.11,2.126),'pressure_plate':(2,1),'jump_pad':(1,1)}[asset]
        m['cutout_m']=[w,h]
        offset=sum(p.get('y',[0,0]))/2;angle=m['rotation_blender'][2]
        x,y,z=m['position_blender'];center=[x-math.sin(angle)*offset,y+math.cos(angle)*offset,z]
        walls=decks.get(m['deck'],{}).get('walls',[])
        if m['role']=='weapon' and asset=='weapon_holder' and walls:
            m['wall_mounted']=True
            wall=min(walls,key=lambda wall:math.hypot(wall[0]-x,wall[1]-y))
            wx,wy,wz,ww,wh,wd=wall
            dx,dy=x-wx,y-wy;heading=math.atan2(dy,dx)
            nx,ny=math.cos(heading),math.sin(heading)
            parent=next(n for n in markers if n['asset']=='weapon_holder_wall' and n['deck']==m['deck'] and n['position_blender']==[wx,wy,wz])
            parent['rotation_blender']=[0,0,heading+math.pi/2]
            m['parent_fixture']=parent['name'];m['parent_socket']='WeaponHolderMount'
            m['mount_position_blender']=[wx+nx,wy+ny,wz+1]
            m['mount_rotation_euler']=[math.pi/2,0,heading+math.pi/2]
            m['pickup_position_godot']=[x,z,-y]
            m['wall_figma_center_blender']=[wx,wy,wz]
            m['pickup_contact_gizmo']='Gizmo_'+m['name'].replace('-','_')+'_PickupContact'
            m['cutout_m']=[1,1]
            continue
        if m['deck'] not in decks:continue
        decks[m['deck']]['holes'].append(dict(center=center,size=[w,h],depth=p['depth'],yaw=angle))
    jumbo=dict(name='common-jumbotron',role='jumbotron',asset='jumbotron',category='environments',weapon=None,
        zone='common',deck='common',level='common',position_blender=[0,0,HEIGHTS['roof']+5],position_godot=[0,HEIGHTS['roof']+5,0],rotation_blender=[0,0,0],
        figma_node='131:182',label='Jumbotron',wall_mounted=False,cutout_m=[0,0])
    expanded=[]
    for m in markers:
        if m['role']!='ammo':expanded.append(m);continue
        for suffix,offset in [('L',-.1),('R',.1)]:
            n=dict(m);n['name']=m['name']+'-'+suffix
            x,y,z=m['position_blender'];a=m['rotation_blender'][2]
            n['position_blender']=[x+math.cos(a)*offset,y+math.sin(a)*offset,z]
            n['position_godot']=[n['position_blender'][0],z,-n['position_blender'][1]]
            expanded.append(n)
    markers=expanded;markers.append(jumbo)
    # One native 1 m structural block below each ram; no upper block.
    # Native ram stroke spans the remaining 2.2 m to the next deck underside.
    for pillar in [m for m in markers if m['role']=='pillar']:
        x,y,z=pillar['position_blender'];pad=dict(pillar)
        pad.update(name=pillar['name']+'-platform',role='prop',asset='pillar_platform',category='architecture',
            position_blender=[x,y,z+.5],position_godot=[x,z+.5,-y],load_at_start=True,budget_excluded=True)
        pad.pop('support_height_m',None);pad.pop('support_open_time_s',None)
        markers.append(pad)
        pillar.update(parent_fixture=pad['name'],parent_socket='PillarMountTop',
            mount_position_blender=[x,y,z+1],position_godot=[x,z+1,-y],budget_excluded=True)
    for platform in [m for m in markers if m['role']=='platform' and m['helper_family']=='platform']:
        prop=dict(platform);prop.update(name=platform['name']+'-regolith',role='prop',asset_suffix=platform['asset_suffix']+'_regolith',
            parent_fixture=platform['name'],parent_socket='RegolithMount',budget_excluded=True,load_at_start=True,no_collision=True)
        markers.append(prop)
    markers.append(dict(name='lunar-scenery',role='prop',asset='skyfall',category='maps',asset_suffix='_scenery',
        zone='common',deck='common',level='common',position_blender=[0,0,0],position_godot=[0,0,0],rotation_blender=[0,0,0],
        figma_node='69:3',label='Lunar scenery',wall_mounted=False,cutout_m=[0,0],load_at_start=True,budget_excluded=True))
    return list(decks.values()),markers
