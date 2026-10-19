"""Machine native building floors for Faceoff's sunken fixture gizmos."""
import argparse,bpy,bmesh,json,sys
from pathlib import Path
from mathutils import Matrix,Vector,Euler
HERE=Path(__file__).resolve().parent;MODELS=HERE.parents[1]
sys.path.insert(0,str(HERE));from layout import data
sys.path.insert(0,str(HERE.parent/'common'));sys.path.insert(0,str(HERE.parent/'common/platform'));from map_shells import shell,boolean,cutter,export,recess_size,RECESS_CLEARANCE_M
def main():
    markers,holes=data()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',nargs='+',help='Rebuild only the named native architecture hosts')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    hosts=[m for m in markers if m.get('source_category')=='architecture']
    if args.only:
        unknown=set(args.only)-{m['source_asset'] for m in hosts}
        assert not unknown,('Unknown architecture hosts',sorted(unknown))
        hosts=[m for m in hosts if m['source_asset'] in args.only]
    for host in hosts:
        asset=host['source_asset'];folder=MODELS/'architecture'/asset;stem='faceoff'+host['asset_suffix']
        transform=Matrix.Translation(Vector(host['position_blender']))@Euler(host['rotation_blender']).to_matrix().to_4x4();inverse=transform.inverted()
        metadata=json.loads((folder/(asset+'_rig.json')).read_text());cuts=[]
        for hole in holes:
            if hole['building']==asset:cuts.append({**hole,'center':list(inverse@Vector(hole['center'])),'yaw':hole['yaw']-host['rotation_blender'][2]})
        for collision in (False,True):
            if collision:
                bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);bpy.ops.import_scene.gltf(filepath=str(folder/(asset+'_col.glb')))
            else:bpy.ops.wm.open_mainfile(filepath=str(folder/(asset+'.blend')))
            rig=next(ob for ob in bpy.context.scene.objects if ob.type=='ARMATURE')
            meshes=[ob for ob in bpy.context.scene.objects if ob.type=='MESH' and ob.name.startswith('SK_') and not ob.name.startswith('SK_Tensor') and (collision or 'Trigger' not in ob.name)]
            empties=[ob for ob in bpy.context.scene.objects if ob.type=='EMPTY' and not ob.name.startswith('Gizmo_')]
            if not collision and 'cargo_lift_m' in metadata:
                cargo=metadata['cargo_lift_m'];animation=rig.animation_data
                active=animation.action if animation else None;mutes=[(track,track.mute) for track in animation.nla_tracks] if animation else []
                if animation:
                    animation.action=None
                    for track,_ in mutes:track.mute=True
                pose=rig.pose.bones['CargoLift'];saved=pose.matrix_basis.copy();pose.matrix_basis=Matrix.Identity(4);bpy.context.view_layer.update()
                socket=bpy.data.objects.new('LiftSurfaceMount',None);bpy.context.scene.collection.objects.link(socket)
                socket.parent=rig;socket.parent_type='BONE';socket.parent_bone='CargoLift';bpy.context.view_layer.update()
                socket.matrix_world=Matrix.Translation(Vector((*cargo['center'],cargo['lower'])))
                socket.empty_display_type='ARROWS';socket.empty_display_size=.35;empties.append(socket)
                metadata['gizmos']=[*metadata.get('gizmos',[]),dict(name='LiftSurfaceMount',bone='CargoLift',origin=[*cargo['center'],cargo['lower']],matrix_world=[list(row) for row in socket.matrix_world],attachment_kind='lift_surface')]
                pose.matrix_basis=saved
                if animation:
                    animation.action=active
                    for track,mute in mutes:track.mute=mute
            # Root carries every fixed floor; moving doors and lift parts remain intact.
            for ob in meshes:
                if ob.vertex_groups.find('Root')<0 or 'Regolith' in ob.name or 'Trigger' in ob.name:continue
                for hole in cuts:
                    center=Vector(hole['center']);w,h=hole['size'];depth=hole['depth']
                    inverse_mesh=ob.matrix_world.inverted()
                    intersects=False;rotation=Euler((0,0,hole['yaw'])).to_matrix()
                    for u in (-w/2+.002,0,w/2-.002):
                        for v in (-h/2+.002,0,h/2-.002):
                            origin=center+rotation@Vector((u,v,.025))
                            hit,at,normal,face=ob.ray_cast(inverse_mesh@origin,inverse_mesh.to_3x3()@Vector((0,0,-1)),distance=.06)
                            if hit and all(any(g.group==ob.vertex_groups['Root'].index and g.weight>.5 for g in ob.data.vertices[index].groups) for index in ob.data.polygons[face].vertices):intersects=True
                    if not intersects:continue # Only the actual floor, never doors/lift/roof.
                    # Closed welded wells hold machinery beneath thin upper slabs.
                    if center.z>2:
                        well=shell('TEMP_well',[-w/2-.06,-h/2-.06,w/2+.06,h/2+.06],center.z-.10,depth-.10+.06)
                        well.location=(center.x,center.y,0);well.rotation_euler.z=hole['yaw']
                        if ob.data.materials:well.data.materials.append(ob.data.materials[0])
                        boolean(ob,well,'UNION')
                    cutter(ob,hole['center'],recess_size(hole['size']),depth,hole['yaw'])
                    # New Boolean vertices belong to this fixed floor. Assign
                    # them before testing the next aperture in the same mesh.
                    ob.vertex_groups['Root'].add([v.index for v in ob.data.vertices if not any(g.weight>.001 for g in v.groups)],1,'REPLACE')
                group=ob.vertex_groups.get('Root')
                group.add([v.index for v in ob.data.vertices if not any(g.weight>.001 for g in v.groups)],1,'REPLACE')
            if not collision:
                for ob in meshes:
                    clean=ob.modifiers.new('coplanar machining cleanup','DECIMATE');clean.decimate_type='DISSOLVE';clean.angle_limit=.0001;clean.delimit={'MATERIAL','NORMAL','UV'};clean.use_dissolve_boundaries=False
                    bpy.context.view_layer.objects.active=ob;bpy.ops.object.modifier_apply(modifier=clean.name)
                    bm=bmesh.new();bm.from_mesh(ob.data)
                    bmesh.ops.dissolve_degenerate(bm,dist=1e-7,edges=list(bm.edges))
                    bm.to_mesh(ob.data);bm.free();ob.data.update()
                sys.path.insert(0,str(MODELS));from material_uv import prepare_export
                prepare_export(meshes,HERE,stem)
                count=sum(sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in meshes)
                metadata['map_owned_boolean_triangles']=max(0,count-metadata['triangles'])
                metadata['native_triangle_budget']=metadata['triangle_budget']
                metadata['triangle_budget']+=metadata['map_owned_boolean_triangles']
                assert count<=metadata['triangle_budget'],(asset,count,metadata['triangle_budget'])
                report={**metadata,'name':stem,'source_asset':asset,'source_category':'architecture','triangles':count,'faceoff_cutouts':cuts,'recess_clearance_per_side_m':RECESS_CLEARANCE_M,'meshes':{ob.name:sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in meshes}}
                (HERE/(stem+'_rig.json')).write_text(json.dumps(report,indent=2)+'\n')
                bpy.ops.wm.save_as_mainfile(filepath=str(HERE/(stem+'.blend')),compress=True)
                print('FACEOFF_ARCHITECTURE',asset,count,'native budget',metadata['triangle_budget'],flush=True)
            export([rig,*meshes,*empties],HERE,stem+('_col' if collision else ''),animated=True)
if __name__=='__main__':main()
