"""Render-only native luminaires attached to architectural fixture sockets."""
from pathlib import Path
import bpy
from mathutils import Matrix


def install():
    models=Path(__file__).resolve().parents[1]
    mounts=[o for o in bpy.context.scene.objects if o.type=='EMPTY'
            and o.get('attachment') in ('sconce_light','batten_light')]
    for mount in mounts:
        asset=mount['attachment']
        before=set(bpy.context.scene.objects)
        bpy.ops.import_scene.gltf(filepath=str(models/'environments'/asset/(asset+'.glb')))
        imported=set(bpy.context.scene.objects)-before
        for obj in imported:
            if obj.type=='ARMATURE':obj.animation_data_clear()
            if obj.parent not in imported:
                local=obj.matrix_world.copy()
                obj.parent=mount
                obj.matrix_parent_inverse=Matrix.Identity(4)
                obj.matrix_basis=local
        for obj in imported:obj.name='PRV_Mounted_'+obj.name
    bpy.context.view_layer.update()
    print('PREVIEW_MOUNTED_FIXTURES',len(mounts),'native luminaires',flush=True)
