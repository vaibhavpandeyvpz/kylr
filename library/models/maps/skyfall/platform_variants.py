"""Machine Skyfall recesses into the existing architecture platform castings.

The upstream deck, materials, rim and socket axes remain authoritative. Optional
underbodies are omitted for stacked floors. Sunken fixtures have closed welded
wells below the 0.8 m deck; holes between levels are open through the deck.
"""
import bpy,json,sys,math
from pathlib import Path
from mathutils import Matrix,Vector,Euler
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from layout import data
from model import shell,boolean,cutter
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'maps/common'));sys.path.insert(0,str(ROOT/'maps/common/platform'))
from native import construct,BRIDGE
from map_shells import recess_size,RECESS_CLEARANCE_M,RECESS_TOP_M
from platform_builder import build as build_platform
from platform_footprint import contains

def exports(objects,path):
    sys.path.insert(0,str(ROOT))
    from material_classes import apply
    apply(objects,HERE)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.export_scene.gltf(filepath=str(path.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=False,export_extras=True)
    bpy.ops.export_scene.fbx(filepath=str(path.with_suffix('.fbx')),use_selection=True,add_leaf_bones=False,axis_forward='-Z',axis_up='Y',bake_anim=False)

def separate_regolith(rig,meshes,stem):
    """Native optional dressing is a separate prop on a native-frame socket."""
    dressing=[ob for ob in meshes if 'ArchitectureRegolith' in ob.name]
    if not dressing:return meshes,None
    exports([rig,*dressing],HERE/(stem+'_regolith'))
    (HERE/(stem+'_regolith_rig.json')).write_text(json.dumps(dict(name=stem+'_regolith',triangles=sum(sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in dressing),budget_excluded=True,gizmos=[]),indent=2)+'\n')
    socket=bpy.data.objects.get('RegolithMount') or bpy.data.objects.new('RegolithMount',None)
    if not socket.users_collection:bpy.context.collection.objects.link(socket)
    socket.parent=rig;socket.parent_type='BONE';socket.parent_bone='Root';bpy.context.view_layer.update();socket.matrix_world=Matrix.Identity(4)
    gizmo=dict(name='RegolithMount',bone='Root',origin=[0,0,0],matrix_world=[list(row) for row in Matrix.Identity(4)])
    for ob in dressing:meshes.remove(ob);bpy.data.objects.remove(ob,do_unlink=True)
    return meshes,gizmo

def main():
    decks,markers=data();decks={d['name']:d for d in decks}
    selected=sys.argv[sys.argv.index('--only-family')+1] if '--only-family' in sys.argv else None
    selected_decks=set(sys.argv[sys.argv.index('--only-decks')+1].split(',')) if '--only-decks' in sys.argv else None
    platform_markers=[m for m in markers if m['role']=='platform' and (selected is None or m['helper_family']==selected)
                      and (selected_decks is None or m['deck'] in selected_decks)]
    built=set()
    for marker in platform_markers:
        family=marker['helper_family']
        if family=='platform':continue
        if family in built:continue
        if '--reuse-templates' not in sys.argv:construct(family,map_detail=False)
        built.add(family)
    for marker in platform_markers:
        asset=marker['helper_family'];folder=BRIDGE;stem='skyfall'+marker['asset_suffix']
        if asset=='platform':
            rig,_,_,meta=build_platform(HERE,stem,marker['size_m'],marker['extension_rects_m'],marker['omit_border_segments_m'],marker['underbody'])
        else:
            bpy.ops.wm.open_mainfile(filepath=str(folder/(asset+'.blend')))
            meta=json.loads((folder/(asset+'_rig.json')).read_text())
            rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        keep=set(meta.get('components',{}).get('deck',meta.get('meshes',{})))
        if marker['underbody']:keep.update(meta['components']['underbody'])
        keep.update(name for name in meta['meshes'] if 'Regolith' in name)
        # Bridges keep their native rails/cover. Regular decks omit the optional belly.
        if asset=='bridge':keep=set(meta['meshes'])
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name in keep]
        for ob in list(bpy.context.scene.objects):
            if ob!=rig and ob not in meshes and ob.type!='EMPTY':bpy.data.objects.remove(ob,do_unlink=True)
        transform=Matrix.Translation(Vector(marker['position_blender']))@Euler(marker['rotation_blender']).to_matrix().to_4x4()
        inverse=transform.inverted();a,b,c,d=marker['module_rect'];holes=[]
        for hole in decks[marker['deck']]['holes']:
            if hole.get('rotation'):continue # wall-mounted recess belongs to the raised wall.
            x,y,z=hole['center']
            hw,hh=hole['size'];angle=hole.get('yaw',0)
            ex=abs(math.cos(angle))*hw/2+abs(math.sin(angle))*hh/2
            ey=abs(math.sin(angle))*hw/2+abs(math.cos(angle))*hh/2
            if x+ex>a and x-ex<c and y+ey>b and y-ey<d:
                local=inverse@Vector(hole['center']);yaw=hole.get('yaw',0)-marker['rotation_blender'][2]
                owned=contains([[-marker['size_m'][0]/2,-marker['size_m'][1]/2,marker['size_m'][0]/2,marker['size_m'][1]/2],*marker['extension_rects_m']],local.x,local.y) if asset=='platform' else a<=x<=c and b<=y<=d
                holes.append(dict(center=list(local),size=hole['size'],depth=hole['depth'],yaw=yaw,through=hole['depth']>2,well_owner=owned))
        if asset=='platform':
            from platform_common import residue
            old=next(o for o in meshes if 'ArchitectureRegolith' in o.name)
            meshes.remove(old);bpy.data.objects.remove(old,do_unlink=True)
            drift=residue(rig,[[-marker['size_m'][0]/2,-marker['size_m'][1]/2,marker['size_m'][0]/2,marker['size_m'][1]/2],*marker['extension_rects_m']],marker['size_m'][1],holes)
            from platform_common import kit
            clip=kit.prism_bm([(x,y,.25) for x,y in meta['footprint']],1,(0,0,1))
            mesh=bpy.data.meshes.new('TEMP_regolith_footprint');clip.to_mesh(mesh);clip.free()
            tool=bpy.data.objects.new('TEMP_regolith_footprint',mesh);bpy.context.collection.objects.link(tool)
            boolean(drift,tool,'INTERSECT');meshes.append(drift)
        # Collision starts from the native planar deck envelope, not decorative trim.
        w,h=marker['size_m'] if asset=='platform' else (5,5)
        lip=asset.startswith('platform_lip') or asset=='bridge'
        rect=[-w/2,-h if lip else -h/2,w/2,0 if lip else h/2]
        col=shell('SK_'+stem+'_DeckCol',rect,0,.8)
        for extension in marker.get('extension_rects_m',[]):boolean(col,shell('TEMP_col_extension',extension,0,.8),'UNION')
        colliders=[col]
        if asset=='bridge':
            # Guard rails and canopy are blocking architecture, not decoration.
            for visual in meshes:
                if visual.name=="SK_Bridge5X5Deck":continue
                proxy=visual.copy();proxy.data=visual.data.copy();proxy.name=visual.name+'Col'
                bpy.context.collection.objects.link(proxy);proxy.data.materials.clear();colliders.append(proxy)
        if marker['underbody']:
            import bmesh
            for index,points in enumerate(meta['underbody_proxies']):
                bm=bmesh.new()
                for point in points:bm.verts.new(point)
                bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
                mesh=bpy.data.meshes.new(stem+'_chassis_'+str(index));bm.to_mesh(mesh);bm.free()
                ob=bpy.data.objects.new('SK_'+stem+'_UnderbodyCol_'+str(index),mesh);bpy.context.collection.objects.link(ob);colliders.append(ob)
        for hole in holes:
            x,y,z=hole['center'];hw,hh=hole['size'];depth=hole['depth']
            if not marker['underbody'] and not hole['through'] and depth>.8 and hole['well_owner']:
                # Fused well is only where a native sunken prop needs depth.
                for target in [meshes[0],col]:
                    well=shell('TEMP_welded_well',[-hw/2-.06,-hh/2-.06,hw/2+.06,hh/2+.06],-.72,depth-.72+.06)
                    well.location=(x,y,0);well.rotation_euler.z=hole['yaw']
                    if target.data.materials:well.data.materials.append(target.data.materials[0])
                    boolean(target,well,'UNION')
            clearance=recess_size(hole['size'])
            for target in [*meshes,*colliders]:cutter(target,[x,y,0],clearance,depth,hole['yaw'])
        for ob in [*meshes,*colliders]:
            ob.parent=rig
            group=ob.vertex_groups.get('Root') or ob.vertex_groups.new(name='Root')
            group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
            if not any(m.type=='ARMATURE' for m in ob.modifiers):ob.modifiers.new('native rigid deck','ARMATURE').object=rig
        # Planar reduction keeps every silhouette, opening and material border.
        # Never collapse a load-bearing casting to meet a triangle quota.
        for ob in meshes:
            mod=ob.modifiers.new('coplanar casting cleanup','DECIMATE');mod.decimate_type='DISSOLVE';mod.angle_limit=math.radians(.01);mod.delimit={'MATERIAL','NORMAL','UV'}
            bpy.context.view_layer.objects.active=ob;bpy.ops.object.modifier_apply(modifier=mod.name)
        sys.path.insert(0,str(ROOT/'maps/common'));sys.path.insert(0,str(ROOT/'maps/common/platform'))
        from platform_common import split_large
        split=[]
        for ob in meshes:split.extend(split_large(ob,rig,ob.name.removeprefix('SK_')))
        meshes=split
        if asset=='platform':
            from platform_common import common
            common.prepare_export([rig,*meshes],HERE,stem)
        meshes,regolith_mount=separate_regolith(rig,meshes,stem)
        empties=[o for o in bpy.context.scene.objects if o.type=='EMPTY' and (marker['underbody'] or not o.name.startswith('ThrusterMount')) and not (marker['underbody'] and o.get('required_option')=='deck_only')]
        # Retain every upstream attachment socket and the native belly sockets on thruster-bearing platforms.
        gizmos=[]
        if regolith_mount:gizmos.append(regolith_mount)
        for g in meta.get('gizmos',[]):
            if marker['underbody'] and g.get('required_option')=='deck_only':continue
            if g.get('attachment')=='thruster' and not marker['underbody']:continue
            if g.get('attachment')=='batten_light':
                # Keep native slots only where the machined ceiling still
                # supports the actual backplate; holes never gain floating lamps.
                frame=Matrix(g['matrix_world']);supported=True
                for x in (-.70,0,.70):
                    for y in (-.09,0,.09):
                        point=frame@Vector((x,y,-.02));valid=False
                        for mesh in meshes:
                            inv=mesh.matrix_world.inverted()
                            hit,at,_,_=mesh.ray_cast(inv@point,inv.to_3x3()@Vector((0,0,1)),distance=.04)
                            if hit and abs((mesh.matrix_world@at).z-frame.translation.z)<.003:valid=True;break
                        if not valid:supported=False
                if not supported:
                    ob=bpy.data.objects.get(g['name'])
                    if ob in empties:empties.remove(ob)
                    continue

            if g.get('attachment')=='sconce_light':
                world=transform@Matrix(g['matrix_world'])@Vector((0,-.1,0))
                if any(n['role']=='platform' and n['name']!=marker['name'] and abs(n['position_blender'][2]-marker['position_blender'][2])<.001 and n['module_rect'][0]<world.x<n['module_rect'][2] and n['module_rect'][1]<world.y<n['module_rect'][3] for n in markers):continue
            gizmos.append(g)
        exports([rig,*meshes,*empties],HERE/stem)
        exports([rig,*colliders],HERE/(stem+'_col'))
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/(stem+'.blend')),compress=True)
        report=dict(name=stem,source_helper=asset,underbody=marker['underbody'],depth_m=meta['depth_m'] if marker['underbody'] else .8,gizmos=gizmos,cutouts=holes,triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),placement=meta['placement'])
        if asset=='platform':
            for key in ('size_m','extension_rects_m','footprint','perimeter','omit_border_segments_m','top_surface','authoring_order'):report[key]=meta[key]
        report['meshes']={o.name:sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes}
        report['recess_clearance_per_side_m']=RECESS_CLEARANCE_M
        report['recess_top_above_surface_m']=RECESS_TOP_M
        report['triangle_budget']=report['triangles']
        report['budget_approval']='2026-10-13: user requests all native geometry; final map budget equals measured total'
        assert max(report['meshes'].values())<=5000,report['meshes']
        (HERE/(stem+'_rig.json')).write_text(json.dumps(report,indent=2)+'\n')
        print('SKYFALL_NATIVE_PLATFORM',stem,report['triangles'],len(holes),'recesses',flush=True)

if __name__=='__main__':main()
