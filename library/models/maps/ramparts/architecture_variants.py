"""Machine map-owned spawn recesses into the native cistern floor slabs."""
import json
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/'common'))
sys.path.insert(0,str(HERE.parents[1]))
from layout import data,metadata,RUNTIME,MODELS
from map_shells import cutter,recess_size,export
from material_uv import prepare_export


def main():
    decks,markers=data()
    for host in [m for m in markers if m.get('source_asset')=='cistern']:
        stem='ramparts'+host['asset_suffix']
        frame=Matrix.Translation(Vector(host['position_blender']))@Euler(host['rotation_blender']).to_matrix().to_4x4()
        holes=[]
        for h in next(d for d in decks if d['name']==host['deck'])['holes']:
            if h.get('building')=='cistern':
                holes.append({**h,'center':list(frame.inverted()@Vector(h['center'])),
                              'yaw':h['yaw']-host['rotation_blender'][2]})
        assert len(holes)==2
        report=metadata('architecture','cistern')
        for collision in (False,True):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            name='cistern'+('_col' if collision else '')+'.glb'
            source=MODELS/'architecture/cistern'/name
            if not source.exists():source=RUNTIME/'architecture/cistern'/name
            bpy.ops.import_scene.gltf(filepath=str(source))
            rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            sockets=[o for o in bpy.context.scene.objects if o.type=='EMPTY']
            cut_meshes=set();cut_markers=set()
            for ob in list(meshes):
                root=ob.vertex_groups.get('Root')
                if root is None or 'Regolith' in ob.name:continue
                # Boolean only rigid Root geometry. Keeping animated mechanisms
                # separate prevents interpolated weights on new cut vertices.
                is_root=lambda v:any(g.group==root.index and g.weight>.5 for g in v.groups)
                root_faces={p.index for p in ob.data.polygons if all(is_root(ob.data.vertices[i]) for i in p.vertices)}
                if not root_faces:continue
                if len(root_faces)!=len(ob.data.polygons):
                    fixed=ob.copy();fixed.data=ob.data.copy();fixed.name=ob.name+'_Fixed'
                    bpy.context.scene.collection.objects.link(fixed);meshes.append(fixed)
                    for target,remove_root in [(ob,True),(fixed,False)]:
                        bm=bmesh.new();bm.from_mesh(target.data)
                        bm.faces.ensure_lookup_table()
                        remove=[f for f in bm.faces if (f.index in root_faces)==remove_root]
                        bmesh.ops.delete(bm,geom=remove,context='FACES')
                        bm.to_mesh(target.data);bm.free();target.data.update()
                    ob=fixed;root=ob.vertex_groups['Root']
                selected=[]
                bpy.context.view_layer.update()
                for h in holes:
                    center=Vector(h['center']);inverse=ob.matrix_world.inverted()
                    hit,at,normal,face=ob.ray_cast(inverse@(center+Vector((0,0,.025))),
                        inverse.to_3x3()@Vector((0,0,-1)),distance=.06)
                    if not hit:continue
                    if not all(any(g.group==root.index and g.weight>.5 for g in ob.data.vertices[i].groups)
                               for i in ob.data.polygons[face].vertices):continue
                    selected.append(h)
                for h in selected:
                    center=Vector(h['center'])
                    for tier in h['tiers']:
                        p=list(center);p[2]+=tier['from_z']
                        cutter(ob,p,recess_size(tier['size']),tier['from_z']-tier['to_z'],h['yaw'])
                    for group in ob.vertex_groups:group.remove(list(range(len(ob.data.vertices))))
                    root.add(list(range(len(ob.data.vertices))),1,'REPLACE')
                    ob.data.validate();ob.data.update();cut_meshes.add(ob.name)
                    cut_markers.add(h['marker'])
            assert cut_meshes,('No native cistern floor was cut',stem,collision)
            assert len(cut_markers)==2,('Both spawn floors must be machined',stem,collision,cut_markers)
            if not collision:
                prepare_export(meshes,HERE,stem)
                counts={o.name:sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes}
                assert max(counts.values())<=5000,('Native architecture per-mesh budget',counts)
                count=sum(counts.values());added=max(0,count-report['triangles'])
                result={**report,'name':stem,'source_asset':'cistern','source_category':'architecture',
                    'triangles':count,'meshes':counts,'map_owned_boolean_triangles':added,
                    'native_triangle_budget':report['triangle_budget'],
                    'triangle_budget':report['triangle_budget']+added,
                    'ramparts_cutouts':holes,'recess_clearance_per_side_m':.001}
                (HERE/(stem+'_rig.json')).write_text(json.dumps(result,indent=2)+'\n')
                bpy.ops.wm.save_as_mainfile(filepath=str(HERE/(stem+'.blend')),compress=True)
            export([rig,*meshes,*sockets],HERE,stem+('_col' if collision else ''),animated=not collision)
            print('RAMPARTS_CISTERN',stem,'collision' if collision else 'render',len(holes),'stepped spawn wells',flush=True)


if __name__=='__main__':main()
