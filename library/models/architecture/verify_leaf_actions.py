"""Verify native-format independent door controls preserve the opposite leaf.

Run Blender with -- hangar laboratory after model and collider generation.
"""
import sys
from pathlib import Path
import bpy

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'environments'))
import light_common as common

def main():
    names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['hangar','laboratory']
    for name in names:
        for suffix in ('','_col'):
            for extension in ('glb','fbx'):
                bpy.ops.wm.read_factory_settings(use_empty=True)
                path=HERE/name/f'{name}{suffix}.{extension}'
                if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
                else:bpy.ops.import_scene.fbx(filepath=str(path))
                rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
                for track in rig.animation_data.nla_tracks:track.mute=True
                controls=(('front','Door','Lock','RearDoor','RearLock'),('rear','RearDoor','RearLock','Door','Lock')) if name in ('cistern','lodge') else (
                    ('left','LeftDoor','LeftDoorBolt','RightDoor','RightDoorBolt'),('right','RightDoor','RightDoorBolt','LeftDoor','LeftDoorBolt'))
                for side,own,own_lock,other,other_lock in controls:
                    for command in ('open','close'):
                        name_action=command+'_'+side
                        action=next(a for a in bpy.data.actions if a.name.split('|')[-1]==name_action)
                        paths=[f.data_path for f in common.kit.action_fcurves(action)]
                        assert not any('"'+other+'"' in p or '"'+other_lock+'"' in p for p in paths),(path,name_action,'opposite leaf keyed')
                        rig.animation_data.action=None
                        for bone in rig.pose.bones:
                            bone.location=(0,0,0);bone.rotation_euler=(0,0,0);bone.rotation_quaternion=(1,0,0,0)
                        peer=rig.pose.bones[other]
                        if peer.rotation_mode=='QUATERNION':
                            from mathutils import Quaternion
                            peer.rotation_quaternion=Quaternion((1,0,0),.71)
                        else:peer.rotation_euler[0]=.71
                        rig.pose.bones[other_lock].location[1]=-.09
                        bpy.context.view_layer.update()
                        held={bn:rig.pose.bones[bn].matrix.copy() for bn in (other,other_lock)}
                        rig.animation_data.action=action
                        for frame in (0,24,48,72,96):
                            t=action.frame_range[0]+(action.frame_range[1]-action.frame_range[0])*frame/96
                            bpy.context.scene.frame_set(int(t),subframe=t-int(t))
                            for bone,matrix in held.items():
                                error=max(abs(matrix[i][j]-rig.pose.bones[bone].matrix[i][j]) for i in range(4) for j in range(4))
                                assert error<1e-5,(path,name_action,frame,bone,error)
                print(f'[{path.name}] independently controlled leaves PASS',flush=True)

if __name__=='__main__':main()
