"""Ramparts blueprint in metres. Figma XY becomes Blender X/-Y and Godot X/Z."""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = HERE.parents[1]
RUNTIME = HERE.parents[3] / 'game/assets/models'
HEIGHT = json.loads((HERE / 'settings.json').read_text())['deck_height_m']
WATER = 0.0
ROCK_BOTTOM = -json.loads((HERE / 'settings.json').read_text())['crater']['depth_m']-2.0


def settings():
    return json.loads((HERE / 'settings.json').read_text())


def metadata(category, asset):
    native = MODELS / category / asset / (asset + '_rig.json')
    # Native handoff metadata is a read-only dependency when authoring caches
    # have not been generated in this checkout.
    return json.loads((native if native.exists() else RUNTIME / category / asset / (asset + '_rig.json')).read_text())


def data():
    orientation = settings()['orientation']
    source = json.loads((HERE / 'figma_layout.json').read_text())
    nodes = source['nodes']
    origin = nodes[0]['transform']
    leaves = [n for n in nodes if n['type'] not in ('GROUP', 'FRAME')]

    def point(n):
        t = n['transform']
        return [(t[0][2] + t[0][0]*n['width']/2 + t[0][1]*n['height']/2 - origin[0][2])/100-37.5,
                37.5-(t[1][2] + t[1][0]*n['width']/2 + t[1][1]*n['height']/2 - origin[1][2])/100, HEIGHT]

    def deck(n):
        zone = 'A' if 'Zone A' in n['path'] else 'B' if 'Zone B' in n['path'] else 'common'
        if 'Junction' in n['path']: return 'Junction'
        floater = next((p for p in n['path'] if p.startswith('Floater ')), None)
        return zone + '_' + (floater.replace(' ', '_') if floater else 'Island' if 'Island' in n['path'] else 'Mainland')

    decks = []
    for n in leaves:
        if n['name'] not in ('Mountain top 25x25', 'Platform 10x10', 'Platform'): continue
        name = deck(n)
        if name == 'Junction':
            parts = [p for p in leaves if p['path'][-2:] == ['Junction', 'Platform']]
            rects = []
            for p in parts:
                x,y,_ = point(p)
                rects.append([x-p['width']/200,y-p['height']/200,x+p['width']/200,y+p['height']/200])
            # The union's arms are 7.5 m wide, with 22.5 m overall diameter.
            size = [7.5,7.5]
            center = [0,0,HEIGHT]
        else:
            size = [n['width']/100,n['height']/100]
            center = point(n)
            rects = [[-size[0]/2,-size[1]/2,size[0]/2,size[1]/2]]
        d = dict(name=name,position=center,size_m=size,rects=rects,rock='Mainland' in name,
                 figma_node=n['id'],holes=[])
        if 'Floater' in name:
            span = next(p for p in leaves if p['name']=='Span' and deck(p)==name)
            sp = point(span)
            # Travel follows the long axis of the authored span; the whole
            # platform stays inside it, including at its reversal points.
            d['motion'] = dict(kind='shuttle',axis=[0,0,1],distance=span['height']/100-size[1],
                               start=(center[1]-sp[1])*-1+(span['height']/100-size[1])/2,
                               speed=1.0,bob_amplitude=.5,bob_peak_speed=1.0)
        if name=='Junction': d['motion']=dict(kind='rotation',radius=11.25,rim_speed=.5)
        decks.append(d)
    by_deck = {d['name']:d for d in decks}
    markers = []
    weapons = {'flak cannon':'flak_cannon','rifle':'rifle','minigun':'minigun','bio rifle':'bio_rifle',
               'lightining gun':'lightning_gun','flamethrower':'flamethrower','emp':'emp_gun',
               'grenade launcher':'grenade_launcher','rocket launcher':'rocket_launcher'}
    for n in leaves:
        label=n['name'].lower(); role=None; asset=None; category='gameplay'; weapon=None
        if label.startswith('weapon pickup') or label.startswith('ammo '):
            role='weapon' if label.startswith('weapon') else 'ammo'
            weapon=next((v for k,v in weapons.items() if k in label),None)
            assert weapon, n['name']
            asset='item_cradle' if 'cradle' in label else 'weapon_holder' if role=='weapon' else weapon
            if role=='ammo': category='weapons'
        elif label.startswith('spawn point'): role='spawn';asset='stasis_chamber' if 'stasis' in label else 'spawn_point'
        elif label.startswith('flag placement'): role='flag_base';asset='ctf_flag'
        elif label.startswith('jump platform'):role='jump_pad';asset='jump_pad'
        elif label.startswith('pressure plate'):role='pressure_plate';asset='pressure_plate'
        elif label.startswith('barricade'):role='barricade';asset='barricade'
        elif label=='speedramp':role='speed_ramp';asset='speed_ramp'
        elif label=='repair station':role='repair_station';asset='repair_station'
        elif 'core' in label:role='shield' if 'shield' in label else 'energy';asset='item_cradle'
        elif label=='jumbotron':role='jumbotron';asset='jumbotron';category='environments'
        elif label.startswith('thruster'):role='thruster';asset='thruster';category='environments'
        elif label in ('cistern','container','hub'):role='prop';asset=label;category='architecture'
        elif label.startswith('pole light') or label.startswith('barrel') or label=='wather sensor':
            role='prop';category='environments';asset='pole_light' if 'light' in label else 'barrel' if label.startswith('barrel') else 'weather_sensor'
        if not role or asset in settings()['excluded_assets']:continue
        dname=deck(n);zone='A' if 'Zone A' in n['path'] else 'B' if 'Zone B' in n['path'] else 'common'
        p=point(n);t=n['transform'];yaw=-math.atan2(t[1][0],t[0][0])
        yaw += math.radians(orientation.get(asset+'_yaw_offset_degrees',0))
        if role=='thruster':p[2]-=.8
        if role=='jumbotron':p[2]=HEIGHT+12;dname=None
        building='cistern' if 'Cistern' in n['path'] and asset!='cistern' else 'container' if 'Container' in n['path'] and asset!='container' else 'hub' if 'Hub' in n['path'] and asset!='hub' else None
        if role=='spawn':
            asset=settings()['spawns']['cistern' if building=='cistern' else 'outside']
            target=by_deck[dname]['position']
            yaw=math.atan2(target[0]-p[0],-(target[1]-p[1]))
        if building:p[2]+=metadata('architecture',building)['architecture_dimensions']['rooms'][0]['floor_m']
        if role=='spawn' and asset=='spawn_point':yaw+=math.pi
        m=dict(name=zone+'-'+asset+'-'+n['id'].replace(':','_'),role=role,asset=asset,category=category,
               zone=zone,deck=dname,building=building,level='ground',position_blender=p,
               position_godot=[p[0],p[2],-p[1]],rotation_blender=[0,0,yaw],figma_node=n['id'])
        if weapon:m['weapon']=weapon
        if asset=='container':m['open_actions']=orientation['container_open_actions']
        markers.append(m)
        if role in ('spawn','weapon','jump_pad','pressure_plate','barricade') and asset not in ('stasis_chamber','item_cradle'):
            cut=metadata(category,asset)['cutout_m'];size=cut.get('size',cut.get('patch',[2,2] if asset=='spawn_point' else [4,2]))
            depth=cut['depth'];offset=sum(cut.get('y',[0,0]))/2
            h=dict(marker=m['name'],center=[p[0]-math.sin(yaw)*offset,p[1]+math.cos(yaw)*offset,p[2]],size=size,depth=depth,yaw=yaw)
            if 'tiers' in cut:h['tiers']=cut['tiers']
            h['building']=building
            assert not building or building=='cistern', ('Native architecture needs machining',m['name'])
            by_deck[dname]['holes'].append(h)
    # Resolve semantic facing from the native -Y front axis. The blueprint
    # snapshot remains a record of Figma; these authored rules own runtime yaw.
    for marker in markers:
        if marker['role']=='spawn':
            if marker['asset']=='spawn_point':
                target=next(m for m in markers if m['role']=='spawn' and m['asset']=='spawn_point'
                            and m['zone']==marker['zone'] and m['name']!=marker['name'])
            else:
                target=next(m for m in markers if m['asset']=='cistern' and m['zone']==marker['zone'])
            dx=target['position_blender'][0]-marker['position_blender'][0]
            dy=target['position_blender'][1]-marker['position_blender'][1]
            yaw=math.atan2(dx,-dy)+(math.pi if marker['asset']=='spawn_point' else 0)
            marker['rotation_blender'][2]=yaw
            for hole in by_deck[marker['deck']]['holes']:
                if hole['marker']==marker['name']:hole['yaw']=yaw
        if marker['building']=='container':
            host=next(m for m in markers if m['zone']==marker['zone'] and m['asset']=='container')
            angle=math.radians(orientation['container_yaw_offset_degrees'])
            x,y,z=marker['position_blender'];hx,hy,_=host['position_blender']
            marker['position_blender']=[hx+math.cos(angle)*(x-hx)-math.sin(angle)*(y-hy),hy+math.sin(angle)*(x-hx)+math.cos(angle)*(y-hy),z]
            marker['position_godot']=[marker['position_blender'][0],z,-marker['position_blender'][1]]
            marker['rotation_blender'][2]=host['rotation_blender'][2]
    # Each deck is a separate native platform import. The carrier skeleton owns
    # motion; all geometry, fixtures, collision and sockets inherit that frame.
    for d in decks:
        if d['rock']:continue
        x,y,z=d['position']
        markers.insert(0,dict(name='deck-'+d['name'],role='platform',asset='ramparts',category='maps',
            asset_suffix='_deck_'+d['name'],zone=d['name'][0] if d['name']!='Junction' else 'common',
            deck=d['name'],building=None,level='ground',position_blender=[x,y,z],position_godot=[x,z,-y],
            rotation_blender=[0,0,0],figma_node=d['figma_node']))
    for marker in markers:
        if marker['asset']=='cistern':
            marker.update(source_asset='cistern',source_category='architecture',
                asset='ramparts',category='maps',asset_suffix='_architecture_'+marker['zone']+'_cistern')
    markers.append(dict(name='martian-crater-scenery',role='prop',asset='ramparts',category='maps',
        asset_suffix='_scenery',zone='common',deck=None,building=None,level='scenery',
        position_blender=[0,0,0],position_godot=[0,0,0],rotation_blender=[0,0,0],
        figma_node=None,load_at_start=True,budget_excluded=True))
    return decks,markers
