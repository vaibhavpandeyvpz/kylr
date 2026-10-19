"""Authored flat PBR weapon finishes; never export baked finish maps.

Run in headless Blender: --python models/weapon_materials.py -- pistol
Refreshes existing native exports without rebuilding geometry or UVs.
"""
from pathlib import Path
import json
import re
import runpy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

_specifications = {}
ALIASES = {
    'M_PaintedMetal_Primary': 'M_Primary',
    'M_Rubber_Grip': 'M_Secondary',
    'M_Titanium_Frame': 'M_Frame',
    'M_StainlessSteel': 'M_Joint',
    'M_Gunmetal': 'M_Metal',
    'M_Gunmetal_Receiver': 'M_Receiver',
    'M_PaintedMetal_Red': 'M_Red',
    'M_BrushedAluminum': 'M_Alu',
    'M_Copper': 'M_Wire',
    'M_Rubber_Wire': 'M_Wire',
}


def role_name(name):
    from material_classes import CLASSIFIERS
    role = name.split('.')[0]
    if role in ('M_Emissive', 'M_Glass'):
        return role
    for classifier in (*CLASSIFIERS, 'Reflective'):
        role = role.removesuffix('_' + classifier)
    return ALIASES.get(role, role)


def delivery_name(name, folder):
    from material_classes import classified_name, policy
    return classified_name(role_name(name), policy(folder))


def metadata_value(value, folder):
    if isinstance(value, str):
        return delivery_name(value, folder) if re.fullmatch(r'M_[A-Za-z0-9_]+', value) else value
    if isinstance(value, list):
        return [metadata_value(item, folder) for item in value]
    if isinstance(value, dict):
        return {metadata_value(key, folder): metadata_value(item, folder)
                for key, item in value.items()}
    return value


def metadata(folder):
    for path in Path(folder).glob('*_rig.json'):
        data = metadata_value(json.loads(path.read_text(encoding='utf-8')), folder)
        path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def specifications(folder):
    folder = Path(folder).resolve()
    if folder not in _specifications:
        source = runpy.run_path(str(folder / 'model.py'), run_name='_weapon_material_source')
        values = source.get('MATERIALS')
        if values is None:
            values = source['k'].MATERIALS
        _specifications[folder] = dict(values)
    return _specifications[folder]


def restore(objects, folder):
    """Keep per-face assignments and effect materials; restore source finish values."""
    import bpy
    from material_classes import policy
    authored = specifications(folder)
    classifiers = policy(folder)
    # Restore source role names so game paint/effect consumers keep their contract.
    for obj in objects:
        if obj.type != 'MESH':
            continue
        for slot in obj.material_slots:
            original = slot.material
            if original is None:
                continue
            name = delivery_name(original.name, folder)
            if original.name != name:
                target = bpy.data.materials.get(name)
                if target is None:
                    target = original.copy()
                    target.name = name
                # Generators still address the original role later when they
                # build ammo/projectiles. Keep those source datablocks named.
                slot.material = target
    materials = {slot.material for obj in objects if obj.type == 'MESH'
                 for slot in obj.material_slots if slot.material}
    restored = 0
    for material in materials:
        role = role_name(material.name)
        if classifiers.get(role) in ('Glass', 'Emissive'):
            continue
        if not material.use_nodes:
            continue
        shader = next((node for node in material.node_tree.nodes
                       if node.type == 'BSDF_PRINCIPLED'), None)
        if shader is None:
            continue
        images = [node for node in material.node_tree.nodes if node.type == 'TEX_IMAGE']
        if role not in authored:
            assert not images, (material.name, 'Missing authored finish specification')
            continue
        color, metallic, roughness, emission, *alpha = authored[role]
        if emission or (alpha and alpha[0] < 1):
            continue
        for name in ('Base Color', 'Metallic', 'Roughness', 'Normal'):
            for link in list(shader.inputs[name].links):
                material.node_tree.links.remove(link)
        for node in images:
            material.node_tree.nodes.remove(node)
        shader.inputs['Base Color'].default_value = (*color, 1.0)
        shader.inputs['Metallic'].default_value = metallic
        shader.inputs['Roughness'].default_value = roughness
        material.diffuse_color = (*color, 1.0)
        material['weapon_finish_source'] = 'authored_flat_pbr'
        restored += 1
    for owner in [*bpy.data.scenes, *objects]:
        for key in list(owner.keys()):
            value = owner[key]
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except (ValueError, TypeError):
                    continue
                updated = metadata_value(parsed, folder)
                if updated != parsed:
                    owner[key] = json.dumps(updated)
    return restored


if __name__ == '__main__':
    from material_uv import refresh_asset
    name = sys.argv[sys.argv.index('--') + 1]
    folder = Path(__file__).resolve().parent / 'weapons' / name
    assert folder.is_dir() and folder.parent.name == 'weapons'
    refresh_asset(folder, materials_only=True)
    metadata(folder)
