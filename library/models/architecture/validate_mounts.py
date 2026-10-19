"""Fresh fixture-gizmo round trips, including rigid rig and clip contracts."""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector

HERE=Path(__file__).resolve().parent
def main():
    name=sys.argv[sys.argv.index('--')+1];folder=HERE/name
    report=json.loads((folder/f'{name}_rig.json').read_text())
    expected={g['name']:g for g in report['gizmos']}
    assert any(n.startswith('BattenLightMount') for n in expected)
    assert any(n.startswith('SconceLightMount') for n in expected)
    for ext in ('glb','fbx'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(folder/f'{name}.glb'))
        else:bpy.ops.import_scene.fbx(filepath=str(folder/f'{name}.fbx'))
        meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('SK_')]
        count=0
        for obj in meshes:obj.data.calc_loop_triangles();count+=len(obj.data.loop_triangles)
        assert count==report['triangles'],(name,ext,count,report['triangles'])
        rigs=[o for o in bpy.data.objects if o.type=='ARMATURE'];assert len(rigs)==1
        assert {b.name for b in rigs[0].data.bones}=={b['name'] for b in report['bones']}
        assert set(report['animations'])<={a.name.split('|')[-1] for a in bpy.data.actions}
        for node_name,g in expected.items():
            node=bpy.data.objects.get(node_name);assert node is not None,(name,ext,node_name)
            assert (node.matrix_world.translation-Vector(g['origin'])).length<1e-4
            wanted=Matrix(g['matrix_world'])
            assert max(abs(node.matrix_world[i][j]-wanted[i][j]) for i in range(4) for j in range(4))<1e-4,(name,ext,node_name,'orientation')
        print(f'[{name}] {ext} PASS: {len(expected)} surface-seated fixture gizmos; {count} triangles; rig and clips retained',flush=True)
if __name__=='__main__':main()
