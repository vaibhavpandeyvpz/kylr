"""Explicit per-asset material naming, shared by native Blender exporters.

Classification is authored in each model.py, never inferred by the game.
Unclassified surfaces are diffuse. No colour, texture or geometry is changed.
"""
import ast
import atexit
import json
from pathlib import Path

CLASSIFIERS = ('Metallic', 'Glass', 'Emissive', 'Diffuse')
_registered = set()


def policy(folder):
    source = Path(folder) / 'model.py'
    if not source.exists():
        return {}
    for node in ast.parse(source.read_text(encoding='utf-8-sig')).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MATERIAL_CLASSIFIERS' for t in node.targets):
            result = ast.literal_eval(node.value)
            assert all(value in CLASSIFIERS for value in result.values())
            return result
    raise ValueError(f'Missing authored material classifiers: {source}')


def classified_name(name, choices):
    if any(name.endswith('_' + kind) for kind in CLASSIFIERS):
        return name
    return name + '_' + choices.get(name, 'Diffuse') if name.startswith('M_') else name


def classified_data(value, choices):
    if isinstance(value, str):
        return classified_name(value, choices) if value in choices else value
    if isinstance(value, list):
        return [classified_data(item, choices) for item in value]
    if isinstance(value, dict):
        return {classified_data(key, choices): classified_data(item, choices) for key, item in value.items()}
    return value


def scene_metadata(choices):
    import bpy
    for owner in [*bpy.data.scenes, *bpy.data.objects]:
        for key in list(owner.keys()):
            value = owner[key]
            if not isinstance(value, str):
                continue
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                continue
            updated = classified_data(parsed, choices)
            if updated != parsed:
                owner[key] = json.dumps(updated)


_active_choices = {}


def _before_save(_unused):
    scene_metadata(_active_choices)


def metadata(folder):
    folder = Path(folder)
    choices = policy(folder)


    for path in folder.glob('*_rig.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        data = classified_data(data, choices)
        data['material_classifiers'] = {classified_name(name, choices): kind for name, kind in choices.items()}
        path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def apply(objects, folder):
    """Assign named copies, leaving source-generator material lookups intact."""
    import bpy
    folder = Path(folder).resolve()
    choices = policy(folder)
    global _active_choices
    _active_choices = choices
    if _before_save not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(_before_save)
    for obj in objects:
        if obj.type != 'MESH':
            continue
        for slot in obj.material_slots:
            original = slot.material
            if original is None:
                continue
            name = classified_name(original.name, choices)
            if name == original.name:
                continue
            # A source material is immutable at this final export boundary.
            copy = bpy.data.materials.get(name)
            if copy is None:
                copy = original.copy()
                copy.name = name
            slot.material = copy
    if folder not in _registered:
        _registered.add(folder)
        atexit.register(metadata, folder)
