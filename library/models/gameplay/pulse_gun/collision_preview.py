"""Inspect an existing convex companion without repeating decomposition."""
import sys
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import collision
bpy.ops.wm.open_mainfile(filepath=str(HERE/f'{HERE.name}_col.blend'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
collision.render_all(rig,[bpy.data.objects['SK_PulseGunCol']],
    [bpy.data.objects['SK_PulseGun']],[],[])
