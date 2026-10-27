"""Copy validated native outputs and register Ramparts runtime map data."""
import json
import math
import shutil
import sys
from pathlib import Path
from layout import data, metadata, settings, HERE, HEIGHT

ROOT=HERE.parents[3]
GAME=ROOT/'game'


def main():
    report=json.loads((HERE/'ramparts_rig.json').read_text())
    assert report['total_map_triangles']<=report['triangle_budget']
    target=GAME/'assets/models/maps/ramparts';target.mkdir(parents=True,exist_ok=True)
    for source in [*HERE.glob('ramparts*.glb'),*HERE.glob('ramparts*_rig.json')]:shutil.copy2(source,target/source.name)
    sys.path.insert(0,str(ROOT/'library/tools'))
    from handoff_lunar_materials import handoff
    for path in target.glob('*.glb'):
        compacted=handoff(path)
        if compacted:path.write_bytes(compacted[0])
    decks,markers=data()
    environment=settings()['environment']
    environment['water']['radius_m']=settings()['crater']['diameter_m']/2
    flags=[next(m for m in markers if m['zone']==zone and m['role']=='flag_base') for zone in ('A','B')]
    config=dict(id='ramparts',title='Ramparts',model='ramparts',
        subtitle='Martian crater lake linked by thruster decks and a rotating junction.',
        description='Cross six moving floaters and a clockwise rotating junction, raid the cistern bases, and control the side platforms inside a mountain-ringed crater lake. Falling into the lake is fatal.',
        match_types=['DM','TDM','CTF','ELIMINATION','GUNGAME'],metadata='res://assets/models/maps/ramparts/ramparts_rig.json',
        surface='lake',crater=settings()['crater'],lethal_terrain_contact=True,soil_material=settings()['soil_material'],environment=environment,gravity_multiplier=1.0,flag_bases=[m['position_godot'] for m in flags],
        flag_markers=[m['name'] for m in flags],flag_capture_meshes=['SK_RampartsFlagCaptureTrigger_A','SK_RampartsFlagCaptureTrigger_B'],
        navigation=dict(min_x=-36,max_x=36,min_z=-36,max_z=36,levels=[HEIGHT,HEIGHT+.08,HEIGHT+.097,HEIGHT+.169,HEIGHT+2.67,HEIGHT+3.15]),
        camera_path=[[0,HEIGHT+45,0],[68,HEIGHT+42,68]],camera_focus=[[0,HEIGHT,0]],fall_boundary=0.0,
        death_camera_min_height=settings()['death_camera_clearance_m'],
        crossing_balance=settings()['crossing_balance'],
        floater_paths=settings()['floater_paths'],
        reuse_navigation_query_shapes=settings()['reuse_navigation_query_shapes'],
        platform_emissive_only_assets=settings()['platform_emissive_only_assets'],
        zone_bounds=[dict(min=[-36,HEIGHT-2,-36],max=[-10,HEIGHT+5,-10]),dict(min=[10,HEIGHT-2,10],max=[36,HEIGHT+5,36])],
        zone_exits=[[-12,HEIGHT,-12],[12,HEIGHT,12]],portal_pairs=[],jump_links=[],drop_links=[],
        event=dict(time=120,warning=10,type='none',title='Continuous carrier motion'),bake_navigation=True,
        moving_decks=[d['name'] for d in decks if 'motion' in d],
        patrol_points=[m['position_godot'] for m in markers if m['role'] in ('spawn','weapon','shield','energy')],
        barricade_links={},speed_ramp_links=[])
    for zone in ('A','B'):
        plate=next(m for m in markers if m['zone']==zone and m['role']=='pressure_plate')
        wall=next(m for m in markers if m['zone']==zone and m['role']=='barricade')
        config['barricade_links'][plate['name']]=wall['name']
        pad=next(m for m in markers if m['zone']==zone and m['role']=='jump_pad')
        sign=1 if zone=='A' else -1
        config['jump_links'].append(dict(from_=pad['position_godot'],to=[-sign*22.5,HEIGHT,sign*4.0]))
        config['jump_links'][-1]['from']=config['jump_links'][-1].pop('from_')
        ramp=next(m for m in markers if m['zone']==zone and m['role']=='speed_ramp')
        native=metadata('gameplay','speed_ramp');local=native['launch_design']['launch_origin']
        x,y,z=ramp['position_blender'];yaw=ramp['rotation_blender'][2]
        lip=[x+math.cos(yaw)*local[0]-math.sin(yaw)*local[1],
             z+local[2],-(y+math.sin(yaw)*local[0]+math.cos(yaw)*local[1])]
        axis=native['authoring_belt']['axis'];horizontal=abs(axis[1]);vertical=axis[2]
        sign=1 if zone=='A' else -1
        landing=[lip[0],HEIGHT,sign*12.0];distance=abs(landing[2]-lip[2])
        speed=math.sqrt(19.6*distance*distance/(2*horizontal*horizontal*(vertical/horizontal*distance+lip[1]-HEIGHT)))
        config['speed_ramp_links'].append(dict(fixture=ramp['name'],to=landing,speed=speed))
    catalog=GAME/'data/maps/catalog.json';catalog_data=json.loads(catalog.read_text())
    catalog_data['maps']=[m for m in catalog_data['maps'] if m['id']!='ramparts']+[config]
    text=json.dumps(catalog_data,indent=2)+'\n'
    text=text.replace('"terrain_scan": [\n          -1.5,\n          3.5\n        ]','"terrain_scan": [-1.5, 3.5]')
    catalog.write_text(text)
    manifest=GAME/'data/maps/previews.json';previews=json.loads(manifest.read_text())
    specs=[('Crater lake',[65,HEIGHT+45,65],[0,HEIGHT,0],57),
           ('Cistern mainland',[-6,HEIGHT+9,-8],[-23,HEIGHT+1,-23],63),
           ('Thruster crossings',[16,HEIGHT+5,-12],[10,HEIGHT,-26],68),
           ('Rotating junction',[22,HEIGHT+12,16],[0,HEIGHT,0],65),
           ('Island outpost',[-4,HEIGHT+8,12],[-23,HEIGHT,8],65)]
    previews['ramparts']=[dict(title=title,image=f'res://assets/ui/maps/ramparts/{i:02}.webp',position=p,target=t,fov=f) for i,(title,p,t,f) in enumerate(specs,1)]
    manifest.write_text(json.dumps(previews,indent=2)+'\n')
    print('RAMPARTS_HANDOFF',len(list(target.glob('*.glb'))),'GLBs',report['total_map_triangles'],'map triangles')


if __name__=='__main__':main()
