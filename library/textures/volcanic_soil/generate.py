"""Bake original volcanic sources through the shared periodic PBR pipeline."""
from pathlib import Path
import importlib.util

HERE=Path(__file__).resolve().parent

def generate():
    source=HERE.parent/'planetary/generate.py'
    spec=importlib.util.spec_from_file_location('volcanic_pbr',source)
    generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)
    generator.HERE=HERE
    generator.GAME=HERE.parents[2]/'game/assets/textures/volcanic_soil'
    generator.generate()

if __name__=='__main__':generate()
