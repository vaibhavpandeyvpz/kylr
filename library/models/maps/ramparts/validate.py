"""Headless native geometry, closed collision and GLB/FBX round-trip checks."""
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from layout import data,HEIGHT,ROCK_BOTTOM


def clear():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)


def count():
    return sum(sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in bpy.context.scene.objects if ob.type=='MESH')


def main():
    report=json.loads((HERE/'ramparts_rig.json').read_text())
    assert report['total_map_triangles']<=25000
    scenery=json.loads((HERE/'ramparts_scenery_rig.json').read_text())
    assert scenery['triangles']<=scenery['triangle_budget'] and scenery['budget_excluded']
    decks,markers=data()
    assert len([d for d in decks if d.get('motion',{}).get('kind')=='shuttle'])==6
    assert len([m for m in markers if m['role']=='repair_station'])==2
    assert len([m for m in markers if m['role']=='spawn'])==10
    assert len([m for m in markers if m['asset']=='spawn_point' and m['building']=='cistern'])==4
    assert len([m for m in markers if m['asset']=='stasis_chamber' and m['building'] is None])==6
    for d in decks:assert d['position'][2]==HEIGHT
    assert HEIGHT==10.0
    from terrain import geometry
    for d in decks:
        if not d['rock']:continue
        vertices,faces=geometry(d['position'],319 if d['name'].startswith('A') else 841)
        assert min(v[2] for v in vertices)==ROCK_BOTTOM
        assert max(v[2] for v in vertices)==HEIGHT
        top=[v for v in vertices if HEIGHT-1<v[2]<HEIGHT-.01]
        assert len(top)>100, 'Eroded summit and sloping rim required'
        assert len({round(v[0],2) for v in top})>40, 'Summit outline must vary'
    assert not any(m["asset"]=="pole_light" for m in markers), "Ramparts has no pole lights"
    for marker in markers:
        yaw=marker['rotation_blender'][2]
        front=(math.sin(yaw),-math.cos(yaw))
        if marker['asset'] in ('pressure_plate','container'):
            deck=next(d for d in decks if d['name']==marker['deck'])
            dx=deck['position'][0]-marker['position_blender'][0]
            dy=deck['position'][1]-marker['position_blender'][1]
            if marker['asset']=='container':
                assert dx*front[0]+dy*front[1]>0,marker['name']
                assert marker['open_actions']==['front_open']
            else:
                # The plate faces away from the deck centre toward its nearer
                # edge; its machined opening must use that same yaw.
                assert dx*front[0]+dy*front[1]<0,marker['name']
                hole=next(h for h in deck['holes'] if h['marker']==marker['name'])
                assert abs(hole['yaw']-yaw)<1e-8
    results=[]
    for glb in sorted(HERE.glob('ramparts*.glb')):
        clear();bpy.ops.import_scene.gltf(filepath=str(glb));native=count()
        assert native>0,glb.name
        for ob in bpy.context.scene.objects:
            if ob.type!='MESH':continue
            assert all(math.isfinite(c) for v in ob.data.vertices for c in v.co),ob.name
            if ob.vertex_groups:
                for vertex in ob.data.vertices:
                    weights=[g.weight for g in vertex.groups if g.weight>.001]
                    assert len(weights)==1 and abs(weights[0]-1)<.001,(glb.name,ob.name,'rigid skinning')
            if glb.stem.endswith('_col'):
                if ob.vertex_groups:
                    for polygon in ob.data.polygons:
                        owners={g.group for i in polygon.vertices for g in ob.data.vertices[i].groups if g.weight>.5}
                        assert len(owners)==1,(glb.name,ob.name,'collision triangle spans bones')
                bm=bmesh.new();bm.from_mesh(ob.data)
                # UV seams can split imported vertices. Weld only coincident
                # points for the topology check, without changing the source.
                bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5)
                assert all(e.is_manifold for e in bm.edges),(glb.name,ob.name,'open collision')
                bm.free()
        if glb.stem=='ramparts_col':
            zs=[v.co.z for ob in bpy.context.scene.objects if ob.type=='MESH' and 'Trigger' not in ob.name and 'Crater' not in ob.name and 'Stones' not in ob.name for v in ob.data.vertices]
            assert abs(min(zs)-ROCK_BOTTOM)<.001 and abs(max(zs)-HEIGHT)<.001
        clear();bpy.ops.import_scene.fbx(filepath=str(glb.with_suffix('.fbx')))
        fbx=count();assert fbx==native,(glb.name,native,fbx)
        results.append(dict(asset=glb.name,glb_triangles=native,fbx_triangles=fbx,passed=True))
    target=HERE.parents[2]/'.local/ramparts-validation.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(dict(passed=True,map_triangles=report['total_map_triangles'],assets=results),indent=2)+'\n')
    print('RAMPARTS_VALIDATED',len(results),'native GLB/FBX assets',flush=True)


if __name__=='__main__':main()
