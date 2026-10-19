"""Use the unchanged architecture collider framework with Hub's fitted slabs."""
import importlib.util
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import preview
import collision_extras
import model
model.door_actions.install_fbx_filter()
spec=importlib.util.spec_from_file_location('hub_collision_engine',HERE.parent/'bunker/collision.py')
engine=importlib.util.module_from_spec(spec);sys.modules[spec.name]=engine;spec.loader.exec_module(engine)
engine.HERE,engine.NAME=HERE,'hub'
if __name__=='__main__':
    engine.main()
    model.door_actions.isolate_glb(HERE/'hub_col.glb')
