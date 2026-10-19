"""Regenerate native fixture gizmos without repeating expensive mesh culling.
Geometry, rig, actions and collision exports are preserved; full builds use the
same source mount planner. Run in headless Blender from library.
"""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));import light_mounts
sys.path.insert(0,str(HERE.parent/'maps/common'));from map_shells import export
NAMES=['bastion','cistern','container','container_long','habitat_pod','hangar','hub','laboratory','lodge','shelter','bunker','lunar_dome']
if '--only' in sys.argv:NAMES=sys.argv[sys.argv.index('--only')+1:]
for name in NAMES:
    folder=HERE/name;report=json.loads((folder/(name+'_rig.json')).read_text())
    bpy.ops.wm.open_mainfile(filepath=str(folder/(name+'.blend')))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_') and 'Col' not in o.name and 'Trigger' not in o.name]
    before={o.name:(len(o.data.vertices),len(o.data.polygons)) for o in meshes}
    if name in ('container','container_long','habitat_pod','lunar_dome'):
        mounts,info=light_mounts.install_default(rig,meshes,name)
    else:
        old=[g for g in report.get('gizmos',[]) if g.get('attachment') in ('sconce_light','batten_light')]
        specs={'batten_light':[],'sconce_light':[]}
        for g in old:
            normal=Vector(g['mount_normal']);origin=Vector(g['origin'])+normal*.1
            prefix='BattenLightMount' if g['attachment']=='batten_light' else 'SconceLightMount'
            specs[g['attachment']].append((g['name'].removeprefix(prefix),origin,-normal))
        if name in ('laboratory','bastion'):
            specs['batten_light']=[(str(level)+tag,(x,y,(room['floor_m']+room['ceiling_m'])/2),(0,0,1))
                for level,room in enumerate(report['architecture_dimensions']['rooms'])
                for tag,x,y in [('FrontLeft',-3.2,-2.4),('FrontRight',3.2,-2.4),('RearLeft',-3.2,2.4),('RearRight',3.2,2.4)]]
        mounts,info=light_mounts.install(rig,meshes,specs['batten_light'],specs['sconce_light'],absolute=True)
    for g in info:
        matrix=bpy.data.objects[g['name']].matrix_world.to_3x3()
        forward=matrix@Vector((0,0,-1) if g['attachment']=='batten_light' else (0,-1,0))
        assert forward.dot(Vector(g['mount_normal']))>.999,(name,g['name'],'lamp must face into room')
    assert before=={o.name:(len(o.data.vertices),len(o.data.polygons)) for o in meshes}
    report['materials']=sorted({o.data.materials[p.material_index].name for o in meshes for p in o.data.polygons})
    report['gizmos']=[g for g in report.get('gizmos',[]) if g.get('attachment') not in ('sconce_light','batten_light') and not g.get('name','').startswith('Interior')]+info
    report['lighting_contract']='Native fixtures on surface-supported gizmos; emitter faces into room; source projection +Y becomes Godot -Z'
    empties=[o for o in bpy.context.scene.objects if o.type=='EMPTY']
    export([rig,*meshes,*empties],folder,name,animated=True)
    (folder/(name+'_rig.json')).write_text(json.dumps(report,indent=2)+'\n')
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/(name+'.blend')),compress=True)
    print('NATIVE_LIGHTING',name,len(info),'gizmos; geometry unchanged',flush=True)
