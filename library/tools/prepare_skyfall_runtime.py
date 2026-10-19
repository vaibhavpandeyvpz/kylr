# Skyfall source-to-runtime handoff. Run after library validation.
from pathlib import Path
import json,shutil,runpy,math,sys
ROOT=Path(__file__).resolve().parents[2];MODEL=ROOT/'library/models'
decks,markers=runpy.run_path(str(MODEL/'maps/skyfall/layout.py'))['data']()
def point(m):return m['position_godot']
portals=[m for m in markers if m['role']=='portal'];pairs=[]
for zone in ('A','B'):
 lower=next(m for m in portals if m['zone']==zone and m['level']=='lower')
 roof=next(m for m in portals if m['zone']==zone and m['level']=='roof')
 pairs.append([lower['name'],roof['name']])

# Pairing is gameplay data; updating it does not rebuild or recopy geometry,
# weapon balance profiles, audio catalogs or animation exports.
if '--portal-pairs-only' in sys.argv:
 catalog_path=ROOT/'game/data/maps/catalog.json'
 catalog=json.loads(catalog_path.read_text())
 next(m for m in catalog['maps'] if m['id']=='skyfall')['portal_pairs']=pairs
 catalog_path.write_text(json.dumps(catalog,indent=2)+'\n')
 print('Updated Skyfall same-zone lower/rooftop portal pairs')
 raise SystemExit(0)

flags=sorted([m for m in markers if m['role']=='flag_base'],key=lambda m:m['zone'])
links=[];drops=[];ramp_links=[]
for m in markers:
 if m['role']=='speed_ramp':
  x,z,y=point(m);sign=1 if y>0 else -1
  ramp_links.append(dict(fixture=m['name'],to=[x,26,sign*2.5],speed=12.6))
for m in markers:
 if m['role']!='jump_pad':continue
 x,z,y=m['position_godot']
 # Pads on a lip clear the upper slab before steering inward.
 if 'island_2' in m['deck']:target=[x,26,-2.5 if y<0 else 2.5]
 elif 'mainland_1_lower' in m['deck']:
  # Rise through the authored opening, then steer onto its nearest solid rim.
  target=[math.copysign(18.5 if abs(x)<22.5 else 26.5,x),26,y]
 elif 'island_1' in m['deck']:
  sign=1 if m['zone']=='A' else -1;target=[sign*25,26,-sign*14]
 else:
  sign=1 if m['zone']=='A' else -1;target=[sign*25,30,-sign*20]
 links.append(dict(from_=point(m),to=target,kind='launch'))
def recessed(point):
 for marker in markers:
  if marker['role'] not in ('portal','jump_pad','pressure_plate'):continue
  at=marker['position_godot']
  if abs(at[1]-point[1])<1 and math.hypot(at[0]-point[0],at[2]-point[2])<1.5:return True
 for floor in decks:
  if abs(floor['z']-point[1])>.01:continue
  for x,y,z,w,h,depth in floor.get('walls',[]):
   if abs(point[0]-x)<w/2+.45 and abs(-point[2]-y)<h/2+.45:return True
  for hole in floor['holes']:
   if hole.get('rotation'):continue
   dx=point[0]-hole['center'][0];dy=-point[2]-hole['center'][1];yaw=hole.get('yaw',0)
   u=math.cos(yaw)*dx+math.sin(yaw)*dy;v=-math.sin(yaw)*dx+math.cos(yaw)*dy
   if abs(u)<hole['size'][0]/2+.45 and abs(v)<hole['size'][1]/2+.45:return True
 return False
for d in decks:
 if 'bridge' in d['name']:continue
 a,b,c,e=max(d['rects'],key=lambda r:(r[2]-r[0])*(r[3]-r[1]));candidates=[]
 for t in (.5,.35,.65,.2,.8):
  x=a+(c-a)*t;y=b+(e-b)*t
  candidates.extend([([a+.8,d['z'],-y],[a-1,0,-y]),([c-.8,d['z'],-y],[c+1,0,-y]),([x,d['z'],-b-.8],[x,0,-b+1]),([x,d['z'],-e+.8],[x,0,-e-1])])
 for entry,landing in candidates:
  if max(abs(landing[0]),abs(landing[2]))>36.75 or recessed(entry):continue
  if any(n['z']==d['z'] and any(r[0]<=landing[0]<=r[2] and r[1]<=-landing[2]<=r[3] for r in n['rects']) for n in decks):continue
  below=[n['z'] for n in decks if n['z']<d['z'] and any(r[0]<=landing[0]<=r[2] and r[1]<=-landing[2]<=r[3] for r in n['rects'])]
  if not below:continue # Lunar ground is lethal, never a navigation destination.
  landing[1]=max(below)
  if recessed(landing):continue
  drops.append({'from':entry,'to':landing,'kind':'drop'});break
# Authored clear approaches connect each higher mainland to its lower island.
# Rooftop pads have explicit drop apertures; the surrounding native floor stays solid.
for sign in (-1,1):
 drops.append({'from':[sign*14,26,-sign*26.5],'to':[sign*11,22,-sign*23.5],'kind':'drop'})
 drops.append({'from':[sign*22,30,-sign*22.5],'to':[sign*22,26,-sign*22.5],'kind':'drop'})
 drops.append({'from':[sign*25,26,-sign*1.9],'to':[sign*25,22,0],'kind':'drop'})
walk_routes=[]
for m in markers:
 if m['category']!='architecture':continue
 if m['asset'] not in ('bunker','lunar_dome','cistern','lodge'):continue
 x,y,z=m['position_blender'];yaw=m['rotation_blender'][2]
 meta=json.loads((MODEL/'architecture'/m['asset']/(m['asset']+'_rig.json')).read_text())
 floor=float(meta['architecture_dimensions']['rooms'][0]['floor_m'])
 if m['asset'] in ('bunker','lunar_dome'):
  walk_routes.append([[x+math.sin(yaw)*4,z+floor,-y+math.cos(yaw)*4],[x,z+floor,-y]])
 else:
  for side in (-1,1):
   walk_routes.append([[x+side*math.sin(yaw)*8,z+floor,-y+side*math.cos(yaw)*8],[x+side*math.sin(yaw)*2.5,z+floor,-y+side*math.cos(yaw)*2.5]])
for link in links:link['from']=link.pop('from_')
barricades=[m for m in markers if m['role']=='barricade'];plates=[m for m in markers if m['role']=='pressure_plate']
bindings={p['name']:min([b for b in barricades if b['deck']==p['deck']],key=lambda b:sum((i-j)**2 for i,j in zip(point(p),point(b))))['name'] for p in plates}
catalog=dict(version=2,maps=[dict(id='skyfall',title='Skyfall',model='skyfall',
 subtitle='A lunar battlefield across three floating levels.',description='Fight across floating lunar platforms, use wall mounts and cradles, and traverse between levels. Falling onto the lunar surface is fatal.',
 match_types=['DM','TDM','CTF'],metadata='res://assets/models/maps/skyfall/skyfall_rig.json',gravity_multiplier=0.8,
 flag_markers=[m['name'] for m in flags],flag_bases=[point(m) for m in flags],flag_capture_meshes=['SK_SkyfallFlagCaptureTrigger_A','SK_SkyfallFlagCaptureTrigger_B'],
 navigation=dict(min_x=-36,max_x=36,min_z=-36,max_z=36,levels=[22,26,26.53,30,30.1,30.10966,30.53]),
 camera_path=[[0,55,0],[70,58,70]],camera_focus=[[0,17,0]],fall_boundary=-8,lunar_surface_lethal=True,
 zone_bounds=[{'min':[-36,15,-36],'max':[36,35,-1]},{'min':[-36,15,1],'max':[36,35,36]}],
 audio_zones=[],event=dict(time=120,warning=10,type='none',title='Static lunar battlefield'),
 portal_pairs=pairs,vertical_pad_departure=True,pad_lift_heights={m['name']:5 for m in markers if m['role']=='jump_pad' and 'mainland_1_lower' in m['deck']},jump_links=links,drop_links=drops,walk_routes=walk_routes,bake_navigation=True,
 zone_exits=[[-25,22,-25],[25,22,25]],barricade_links=bindings,speed_ramp_links=ramp_links,
 pulse_gun=dict(range=20,damage=50,interval=1.0,speed=45,slow_multiplier=.25,slow_duration=.5,enabled_match_types=['TDM','CTF']))])
catalog_path=ROOT/'game/data/maps/catalog.json'
existing=json.loads(catalog_path.read_text())
catalog['maps'].extend(m for m in existing['maps'] if m['id']!='skyfall')
catalog_path.write_text(json.dumps(catalog,indent=2)+'\n')
weapons_path=ROOT/'game/data/weapons/catalog.json';weapons=json.loads(weapons_path.read_text())
for id,title,capacity,damage,interval,reach,speed,muzzle in [('flak_cannon','Flak cannon',100,15,2/3,100,45,'Muzzle1'),('bio_rifle','Bio rifle',100,15,1,100,45,'Muzzle'),('grenade_launcher','Grenade launcher',40,40,1,100,15,'Muzzle1')]:
 weapons['weapons'][id]=dict(title=title,model=id,animation_family=id,range=reach,damage=damage,interval=interval,capacity=capacity,recoil=2,attack='reference_projectile',muzzles=[muzzle],projectile_speed=speed,crosshair=dict(style='circle',width=2,radius=14))
weapons['weapons']['flak_cannon'].update(pellets=10,spread_degrees=8,bounces=3,bounce_restitution=.5)
weapons['weapons']['bio_rifle'].update(dot_damage=5,dot_interval=1,dot_duration=3,slow_multiplier=.25,slow_duration=.5)
weapons['weapons']['grenade_launcher'].update(projectile_gravity=9,splash_damage=15,splash_radius=5,slow_multiplier=.25,slow_duration=.5)
weapons_path.write_text(json.dumps(weapons,indent=2)+'\n')
cues_path=ROOT/'game/data/audio/cues.json';cues=json.loads(cues_path.read_text())
for weapon in ('flak_cannon','bio_rifle','grenade_launcher','pulse_gun'):
 for suffix,key in [('shot',weapon),('hit','hit_'+weapon),('bounce',weapon+'_bounce')]:
  if (ROOT/f'game/assets/audio/weapons/{weapon}_{suffix}.wav').exists():cues[key]=dict(asset=f'weapons/{weapon}_{suffix}',gain=0,near=5,far=65,priority=60,limit=8,playback_gain=0)
cues_path.write_text(json.dumps(cues,indent=2)+'\n')
assets=set((m['category'],m['asset']) for m in markers if m['asset'])
assets.update(('environments',w) for w in ('sconce_light','batten_light'))
assets.update(('weapons',w) for w in weapons['weapons'] if w in ('flak_cannon','bio_rifle','grenade_launcher'))
for category,asset in assets:
 source=MODEL/category/asset;target=ROOT/'game/assets/models'/category/asset;target.mkdir(parents=True,exist_ok=True)
 for path in list(source.glob('*.glb'))+list(source.glob('*_rig.json')):shutil.copy2(path,target/path.name)
map_source=MODEL/'maps/skyfall';map_target=ROOT/'game/assets/models/maps/skyfall'
stems={'skyfall','skyfall_col','skyfall_scenery','skyfall_scenery_col'}
for marker in markers:
 if marker['role']=='platform':
  stem='skyfall'+marker['asset_suffix'];stems.update((stem,stem+'_col'))
 elif marker.get('no_collision') and marker['category']=='maps':stems.add('skyfall'+marker['asset_suffix'])
for path in map_target.glob('skyfall_module_*'):
 stem=path.name.split('.glb')[0] if '.glb' in path.name else path.stem.removesuffix('_rig')
 if stem not in stems:path.unlink()
for stem in stems:shutil.copy2(map_source/(stem+'.glb'),map_target/(stem+'.glb'))
for marker in markers:
 if marker['role']=='platform' or marker.get('no_collision'):
  file='skyfall'+marker['asset_suffix']+'_rig.json';shutil.copy2(map_source/file,map_target/file)
shutil.copy2(MODEL/'maps/skyfall/skyfall_rig.json',ROOT/'game/assets/models/maps/skyfall/skyfall_rig.json')
# Native animation families already authored for Bio Rifle and Grenade Launcher.
for family in ('bio_rifle','grenade_launcher','flak_cannon'):
 for category in ('tensor','weapons'):
  source=ROOT/'library/animations/target'/category/family
  target=ROOT/'game/assets/animations'/category/family
  target.mkdir(parents=True,exist_ok=True)
  for path in source.glob('*.glb'):shutil.copy2(path,target/path.name)
print('Runtime map catalog, imported props, weapon profiles and audio prepared')
