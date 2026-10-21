"""Copy validated Faceoff exports and append its map data without replacing Skyfall."""
import json,math,runpy,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];MODELS=ROOT/'library/models';HERE=MODELS/'maps/faceoff'
markers,holes=runpy.run_path(str(HERE/'layout.py'))['data']()
def point(m):return m['position_godot']
def world(m,local):
 x,y,z=m['position_blender'];a=m['rotation_blender'][2];lx,ly,lz=local
 return [x+math.cos(a)*lx-math.sin(a)*ly,z+lz,-y-math.sin(a)*lx-math.cos(a)*ly]
buildings=[m for m in markers if m['category']=='architecture' or m.get('source_category')=='architecture']
walks=[];lifts=[];normal_jumps=[];drops=[];levels={0.0};exits=[]
for host in buildings:
 asset=host.get('source_asset',host['asset']);info=json.loads((MODELS/'architecture'/asset/(asset+'_rig.json')).read_text())
 for room in info.get('architecture_dimensions',{}).get('rooms',[]):levels.add(float(room['floor_m']))
 floor=float(info.get('architecture_dimensions',{}).get('rooms',[{'floor_m':0}])[0]['floor_m'])
 bounds=info['bounds_m'];reach=max(abs(bounds['lo'][1]),abs(bounds['hi'][1]))+1
 interior=min(2,max(0,reach-1.75))
 if asset=='habitat_pod':
  entry=world(host,[0,-2.2,0]);inside=world(host,[-.9,.3,floor])
  walks.append([world(host,[0,-reach,0]),entry]);normal_jumps.append({'from':entry,'to':inside,'via':world(host,[0,-1.35,floor+.55]),'crouch':True});normal_jumps.append({'from':inside,'to':entry,'via':world(host,[0,-1.35,floor+.55]),'crouch':True})
 elif asset!='container':walks.append([world(host,[0,-reach,0]),world(host,[0,-reach+1,floor]),world(host,[0,-interior,floor])])
 if asset in ('cistern','lodge','container','container_long'):walks.append([world(host,[0,reach,0]),world(host,[0,reach-1,floor]),world(host,[0,interior,floor])])
 if 'cargo_lift_m' in info:
  cargo=info['cargo_lift_m'];cx,cy=cargo['center'];lifts.append(dict(fixture=host['name'],lower_exit=world(host,[cx,cy-2,cargo['lower']]),upper_exit=world(host,[cx,cy-2,cargo['upper']])))
 if host['zone'] in ('A','B'):exits.append((host['zone'],world(host,[0,-9,0])))
for marker in markers:
 if marker['role']=='spawn' and marker['asset']=='stasis_chamber':levels.add(marker['position_godot'][1]+.53)
portals=sorted([m for m in markers if m['role']=='portal'],key=lambda m:m['pair_label']);flags=sorted([m for m in markers if m['role']=='flag_base'],key=lambda m:m['zone'])
assert len(flags)==2 and len(portals)==2
links=[]
for pad in [m for m in markers if m['role']=='jump_pad']:
 zone='A' if point(pad)[0]>0 else 'B';links.append({'from':point(pad),'to':dict(exits)[zone],'kind':'launch'})
config=dict(id='faceoff',title='Faceoff',model='faceoff',subtitle='Opposing duplex bases on a shared lunar battlefield.',description='Fight through native architecture, cross the common lunar surface, and use cargo lifts to reach flag floors. Team pulse guns defend each base.',
 match_types=['DM','TDM','CTF'],metadata='res://assets/models/maps/faceoff/faceoff_rig.json',gravity_multiplier=1.2,
 flag_markers=[m['name'] for m in flags],flag_bases=[point(m) for m in flags],flag_capture_meshes=['SK_FaceoffFlagCaptureTrigger_A','SK_FaceoffFlagCaptureTrigger_B'],
 navigation=dict(terrain_scan=[-1.5,3.5],min_x=-36,max_x=36,min_z=-36,max_z=36,levels=sorted(levels)),camera_path=[[0,45,0],[60,45,60]],camera_focus=[[0,2,0]],fall_boundary=-8,
 zone_bounds=[{'min':[12,0,-36],'max':[36,10,-12]},{'min':[-36,0,12],'max':[-12,10,36]}],zone_exits=[p for _,p in sorted(exits)],
 audio_zones=[],event=dict(time=120,warning=10,type='none',title='Lunar battlefield'),portal_pairs=[[m['name'] for m in portals]],jump_links=links,normal_jump_links=normal_jumps,drop_links=drops,walk_routes=walks,lift_links=lifts,bake_navigation=True,barricade_links={},
 pulse_gun=dict(range=20,damage=50,interval=1.0,speed=45,slow_multiplier=.25,slow_duration=.5,enabled_match_types=['TDM','CTF']))
path=ROOT/'game/data/maps/catalog.json';catalog=json.loads(path.read_text());catalog['maps']=[m for m in catalog['maps'] if m['id']!='faceoff']+[config];path.write_text(json.dumps(catalog,indent=2)+'\n')
for marker in markers:
 if marker['category']=='maps':continue
 category,asset=marker['category'],marker['asset'];source=MODELS/category/asset;target=ROOT/'game/assets/models'/category/asset;target.mkdir(parents=True,exist_ok=True)
 if '--placements-only' in sys.argv:continue
 for file in list(source.glob('*.glb'))+list(source.glob('*_rig.json')):shutil.copy2(file,target/file.name)
for file in HERE.glob('*.glb'):
 if '--placements-only' in sys.argv and file.name!='faceoff.glb':continue
 target=ROOT/'game/assets/models/maps/faceoff';target.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target/file.name)
for file in HERE.glob('*_rig.json'):
 if '--placements-only' in sys.argv and file.name!='faceoff_rig.json':continue
 shutil.copy2(file,ROOT/'game/assets/models/maps/faceoff'/file.name)
print('FACEOFF_RUNTIME',len(markers),'fixtures',len(lifts),'native cargo lifts; pulse guns TDM/CTF only')
