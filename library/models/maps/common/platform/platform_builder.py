"""One parametric platform casting: union, perimeter, chassis, residue, machining.

The map supplies dimensions and proposed extension rectangles in platform axes.
Separate architecture/gameplay fixtures are never baked into this builder.
"""
import math,json
from pathlib import Path
import bpy,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mathutils import Matrix,Vector
from platform_common import common,kit,DEPTH,split_large,residue,export,sconce_positions,fascia_recesses
from platform_footprint import outline,border_plan,contains,docking_specs
from platform_placements import thruster_positions
import platform_underbody as underbody
import perimeter_surface as surface

def build(folder,name,size,extensions=(),omit_border=(),with_underbody=False):
    folder=Path(folder);w,d=size
    rects=[[-w/2,-d/2,w/2,d/2],*extensions]
    boundary=outline(rects);segments,inner=border_plan(boundary,omit_border)
    title=''.join(p.title() for p in name.split('_'))
    kit.NAME,kit.TITLE=name,title;surface.configure(kit)
    kit.MATERIALS[common.EMI]=((.02,.55,.62),0,.35,1.5);kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    kit.JOINT_SPECS=[('Root',None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);rig['preview_poses']='{}'
    k=kit.Kit();common.LABELS.clear()
    # Exact union first. No internal lip seam, lip mesh, or lip socket survives.
    casting=kit.machine(common.block((-w/2,-d/2,-DEPTH),(w/2,d/2,0)),
        union=[common.block((a,b,-DEPTH),(c,e,0)) for a,b,c,e in extensions])
    seat=kit.prism_bm([(x,y,-.02) for x,y in inner],.08,(0,0,1))
    # The inset is machined after union so its outline follows every extension.
    from map_shells import boolean
    mesh=bpy.data.meshes.new('TEMP_union');casting.to_mesh(mesh);casting.free()
    body=bpy.data.objects.new('TEMP_union',mesh);bpy.context.collection.objects.link(body)
    mesh=bpy.data.meshes.new('TEMP_border_seat');seat.to_mesh(mesh);seat.free()
    tool=bpy.data.objects.new('TEMP_border_seat',mesh);bpy.context.collection.objects.link(tool)
    boolean(body,tool,'DIFFERENCE')
    import bmesh
    casting=bmesh.new();casting.from_mesh(body.data);bpy.data.objects.remove(body,do_unlink=True)
    # Fixture and service bays share the final exposed perimeter, including lips.
    fascia=[];mount_plan=[]
    for index,edge in enumerate(segments):
        if not edge['border_width']:continue # bridge docking land stays clear
        length=edge['length'];tx,ty=edge['tangent'];nx,ny=edge['normal']
        cx=(edge['a'][0]+edge['b'][0])/2;cy=(edge['a'][1]+edge['b'][1])/2
        lamps=sconce_positions(length)
        for position in lamps:
            mount_plan.append((f'SconceLightMount{index+1}_{len(mount_plan)+1}','sconce_light',
                               (cx+tx*position,cy+ty*position,-.4),math.atan2(nx,-ny)))
        for position in fascia_recesses(length):
            if length/2-abs(position)-.75<.4:continue
            if any(abs(position-lamp)-.75-.215<.4 for lamp in lamps):continue
            matrix=common.frame((cx+tx*position,cy+ty*position,-.4),(nx,ny,0),(0,0,1))
            fascia.append(matrix)
    # Machine actual fascia wells into the one casting in each face's axes.
    for frame in fascia:
        inv=frame.inverted()
        for vertex in casting.verts:vertex.co=inv@vertex.co
        casting=kit.machine(casting,boxes=[((0,0,-.025),(1.5,.26,.10))])
        for vertex in casting.verts:vertex.co=frame@vertex.co
    common.emit(k,casting,common.SEC,'one Boolean-unioned platform casting including extensions')
    common.emit(k,kit.prism_bm([(x,y,-.03) for x,y in inner],.06,(0,0,1)),common.PRI,
                'continuous planar painted surface following the final union perimeter')
    for frame in fascia:
        with k.frame(frame):
            common.emit(k,common.block((-.738,-.118,-.075),(.738,.118,-.06)),common.FRM,'recessed fascia cassette backing')
            for height in (-.072,0,.072):
                common.emit(k,common.block((-.68,height-.01,-.06),(.68,height+.01,-.027)),common.PRI,'formed cooling fin')
    kit.check_connectivity(k,joints,[])
    body=k.to_object('SK_'+title+'Deck');kit.skin(body,rig)
    # Chassis is built once beneath the base; extensions remain integral cantilevers.
    deck_meshes=split_large(body,rig,title+'Deck');meshes=list(deck_meshes)
    proxies=[];chassis_meshes=[]
    thrusters=thruster_positions(w,d) if with_underbody else []
    if with_underbody:
        chassis=kit.Kit();proxies=underbody.build(chassis,common,kit,w,d,thrusters,map_detail=False)
        kit.check_connectivity(chassis,joints,[])
        obj=chassis.to_object('SK_'+title+'Underbody');kit.skin(obj,rig)
        chassis_meshes=split_large(obj,rig,title+'Underbody');meshes.extend(chassis_meshes)
    # Random residue exists before map machining, so those cuts clear it too.
    drift=residue(rig,rects,d)
    clip=kit.prism_bm([(x,y,.25) for x,y in boundary],1,(0,0,1))
    mesh=bpy.data.meshes.new('TEMP_residue_footprint');clip.to_mesh(mesh);clip.free()
    tool=bpy.data.objects.new('TEMP_residue_footprint',mesh);bpy.context.collection.objects.link(tool)
    boolean(drift,tool,'INTERSECT');meshes.append(drift)
    mounts=[];metadata=[]
    def mount(tag,asset,at,angle=0):
        matrix=Matrix.Rotation(angle,4,'Z');matrix.translation=at
        obj=bpy.data.objects.new(tag,None);bpy.context.collection.objects.link(obj)
        obj.parent=rig;obj.matrix_world=matrix;obj.empty_display_type='ARROWS';obj.empty_display_size=.4
        obj['attachment']=asset;mounts.append(obj)
        metadata.append(dict(name=tag,attachment=asset,bone='Root',origin=list(at),matrix_world=[list(row) for row in matrix]))
    for spec in mount_plan:mount(*spec)
    for tag,at,angle in docking_specs(segments):
        mount(tag,'',at,angle)
        mounts[-1]['attachment_kind']='bridge_plug';metadata[-1].pop('attachment')
        metadata[-1].update(attachment_kind='bridge_plug',compatible_assets=['bridge'],omit_fixture_mounts=[])
    for index,(x,y) in enumerate(thrusters,1):mount(f'ThrusterMount{index:02d}','thruster',(x,y,-underbody.depth(w,d)))
    if not with_underbody:
        seen=set()
        for a,b,c,e in rects:
            nx=max(1,math.ceil((c-a)/5));ny=max(1,math.ceil((e-b)/5))
            for ix in range(nx):
                for iy in range(ny):
                    x=a+(c-a)*(ix+.5)/nx;y=b+(e-b)*(iy+.5)/ny
                    angle=math.pi/2 if c-a<1.6 else 0
                    if (round(x,4),round(y,4)) in seen:continue
                    corners=[(x+math.cos(angle)*u-math.sin(angle)*v,y+math.sin(angle)*u+math.cos(angle)*v) for u in (-.7,.7) for v in (-.12,.12)]
                    if not all(contains(rects,u,v) for u,v in corners):continue
                    seen.add((round(x,4),round(y,4)))
                    mount(f'BattenLightMountUnderside{len(seen)}','batten_light',(x,y,-DEPTH),angle)
    for obj in meshes:
        obj['component']='regolith' if obj==drift else 'underbody' if obj in chassis_meshes else 'deck'
    report=dict(name=name,source_helper='platform',size_m=list(size),extension_rects_m=list(extensions),footprint=boundary,
        perimeter=segments,omit_border_segments_m=list(omit_border),depth_m=underbody.depth(w,d) if with_underbody else DEPTH,
        components=dict(deck=[o.name for o in deck_meshes],underbody=[o.name for o in chassis_meshes]),
        underbody_proxies=proxies,gizmos=metadata,top_surface=dict(layout='continuous',perimeter_border_width_m=.16,internal_grid=False),
        authoring_order=['union_extensions','perimeter_border','underbody','random_regolith','placement_booleans'],
        placement='Platform base centre; +Z up; native root axes',meshes={o.name:kit.triangles(o) for o in meshes})
    return rig,meshes,mounts,report

def generate(folder,name,config):
    """Standalone generated example or reusable map input; no size catalog."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    rig,meshes,mounts,report=build(folder,name,config['size_m'],config.get('extension_rects_m',[]),
        config.get('omit_border_segments_m',[]),config.get('underbody',False))
    common.prepare_export([rig,*meshes],folder,name)
    report['triangles']=sum(kit.triangles(o) for o in meshes)
    report['meshes']={o.name:kit.triangles(o) for o in meshes}
    assert max(report['meshes'].values())<=5000
    export([rig,*meshes,*mounts],folder/name)
    (folder/(name+'_rig.json')).write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/(name+'.blend')),compress=True)
    return report

if __name__=='__main__':
    import sys
    config_path=Path(sys.argv[sys.argv.index('--config')+1])
    config=json.loads(config_path.read_text())
    generate(config_path.parent,config.get('name','platform'),config)
