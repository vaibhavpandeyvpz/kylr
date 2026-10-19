"""Generic static-kit showcase; runtime effect animation belongs to Godot."""
from pathlib import Path
import math
import sys
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from preview import setup


def main():
    preview = setup()
    scene = bpy.context.scene
    camera = preview.create_camera()
    preview.create_lights()
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.frame_start, scene.frame_end = 1, 180
    for frame in range(1, 181):
        angle = math.tau * (frame-1) / 180
        camera.location = Vector((math.sin(angle)*11, -math.cos(angle)*11, 5))
        camera.rotation_euler = (Vector((0,0,1.5))-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.keyframe_insert('location', frame=frame)
        camera.keyframe_insert('rotation_euler', frame=frame)
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.filepath = str(HERE / (HERE.name+'_showcase.mp4'))
    if '--no-render' not in sys.argv:
        bpy.ops.render.render(animation=True)
    print('[combat_effects] static-kit showcase configured; runtime effects are validated in Godot')


if __name__ == '__main__':
    main()
