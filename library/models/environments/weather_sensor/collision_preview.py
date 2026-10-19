"""Render the standard collider inspection views without repeating decomposition."""
import sys
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import collision
bpy.ops.wm.open_mainfile(filepath=str(HERE/'weather_sensor_col.blend'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
render=[bpy.data.objects['SK_WeatherSensor']]
colliders=[bpy.data.objects['SK_WeatherSensorCol']]
collision.render_all(rig,colliders,render,[])
