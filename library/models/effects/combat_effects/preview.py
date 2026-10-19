"""Generic exploded-kit preview; never modifies the generated source blend."""
from pathlib import Path
import importlib.util
import bpy

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if parent.name == 'models')


def setup():
    spec = importlib.util.spec_from_file_location('effect_preview_shared', ROOT / 'gameplay/item_table/preview.py')
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    preview.HERE, preview.NAME = HERE, HERE.name
    preview.BLEND_PATH = HERE / (HERE.name + '.blend')
    preview.open_model()
    objects = sorted((obj for obj in bpy.context.scene.objects if obj.type == 'MESH'), key=lambda obj: obj.name)
    for index, obj in enumerate(objects):
        obj.location.x += (index % 4 - 1.5) * 2.0
        obj.location.z += (index // 4) * 2.0 + 0.6
    preview.setup_render()
    return preview


def main():
    preview = setup()
    camera, lights = preview.create_camera(), preview.create_lights()
    for view in ('front_left', 'front'):
        preview.render_view(camera, lights, view)
    print('[combat_effects] neutral exploded-kit previews complete')


if __name__ == '__main__':
    main()
