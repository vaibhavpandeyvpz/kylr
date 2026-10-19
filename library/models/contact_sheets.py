"""Create environment/gameplay/architecture front-left contact sheets.

Run from library/:
  Blender 5.2 --background --factory-startup --python models/contact_sheets.py
  .venv/Scripts/python.exe models/contact_sheets.py

Blender measures only authored SK_ render meshes in the saved rest pose and
renders missing front-left views. Pillow assembles the three generated PNGs.
Outputs and the dimension audit are in ignored target/contact_sheets/.
"""
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target' / 'contact_sheets'
CATEGORIES = ('environments', 'gameplay', 'architecture')


def collect():
    import bpy
    OUT.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location(
        'contact_preview', ROOT / 'models/gameplay/item_table/preview.py')
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    records = []
    for category in CATEGORIES:
        for folder in sorted((ROOT / 'models' / category).iterdir()):
            if not (folder / 'model.py').is_file():
                continue
            name = folder.name
            bpy.ops.wm.open_mainfile(filepath=str(folder / f'{name}.blend'))
            bpy.context.view_layer.update()
            meshes = [o for o in bpy.context.scene.objects
                      if o.type == 'MESH' and o.name.startswith('SK_')
                      and not o.hide_render and not o.name.endswith('Col')
                      and 'Trigger' not in o.name
                      and o.name != 'SK_ArchitectureRegolith']
            assert meshes, name
            points = []
            deps = bpy.context.evaluated_depsgraph_get()
            for obj in meshes:
                evaluated = obj.evaluated_get(deps)
                mesh = evaluated.to_mesh()
                points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
                evaluated.to_mesh_clear()
            lo = [min(p[i] for p in points) for i in range(3)]
            hi = [max(p[i] for p in points) for i in range(3)]
            xyz = [hi[i] - lo[i] for i in range(3)]
            image = folder / f'{name}_front_left.png'
            if not image.exists():
                preview.HERE, preview.NAME = folder, name
                preview.setup_render()
                cam, lights = preview.create_camera(), preview.create_lights()
                preview.render_view(cam, lights, 'front_left', subject=meshes)
            records.append(dict(category=category, name=name,
                                image=str(image), lwh_m=[xyz[1], xyz[0], xyz[2]],
                                bounds_m=dict(lo=lo, hi=hi),
                                measured_meshes=[o.name for o in meshes],
                                source=str(folder / f'{name}.blend')))
            print(f'[contact] {category}/{name}: {xyz[1]:.3f} x {xyz[0]:.3f} x {xyz[2]:.3f} m', flush=True)
    (OUT / 'dimensions.json').write_text(json.dumps(records, indent=2) + '\n')


def compose():
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    records = json.loads((OUT / 'dimensions.json').read_text())
    fonts = ROOT.parent / 'game/assets/ui/fonts'
    def font(size, bold=False):
        return ImageFont.truetype(str(fonts / ('Rajdhani-Bold.ttf' if bold else 'Inter.ttf')), size)
    for category in CATEGORIES:
        items = [r for r in records if r['category'] == category]
        cols = 4
        cell_w, cell_h, gap, margin, top = 660, 490, 22, 44, 190
        rows = math.ceil(len(items) / cols)
        width = 2 * margin + cols * cell_w + (cols - 1) * gap
        height = top + rows * cell_h + (rows - 1) * gap + 95
        sheet = Image.new('RGB', (width, height), '#eef1f4')
        draw = ImageDraw.Draw(sheet)
        draw.text((margin, 30), 'KYLR  /  ' + category.upper(), font=font(52, True), fill='#17232e')
        draw.text((margin, 100), f'{len(items)} authored assets  |  Front-left view  |  L × W × H in metres', font=font(28), fill='#415264')
        draw.text((margin, 140), 'L = front-to-back (Y)   •   W = left-to-right (X)   •   H = vertical (Z)', font=font(25), fill='#526272')
        for index, record in enumerate(items):
            x = margin + index % cols * (cell_w + gap)
            y = top + index // cols * (cell_h + gap)
            draw.rounded_rectangle((x, y, x + cell_w, y + cell_h), radius=12, fill='white', outline='#d5dde5', width=2)
            image = Image.open(record['image']).convert('RGB')
            image = ImageOps.contain(image, (cell_w - 24, 355), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + (cell_w - image.width) // 2, y + 10 + (355 - image.height) // 2))
            draw.text((x + 22, y + 375), record['name'].replace('_', ' ').title(), font=font(30, True), fill='#17232e')
            dims = ' × '.join(f'{v:.3f}'.rstrip('0').rstrip('.') for v in record['lwh_m'])
            draw.text((x + 22, y + 421), f'{dims} m', font=font(32), fill='#256381')
        note = ('Dimensions: native building envelope in saved rest pose; optional regolith apron excluded. Views individually fitted; not to common scale.'
                if category == 'architecture' else
                'Dimensions: native render-mesh envelope in saved rest pose; includes below-floor machinery. Views individually fitted; not to common scale.')
        draw.text((margin, height - 62), note, font=font(24), fill='#526272')
        path = OUT / f'{category}_front_left_contact_sheet.png'
        sheet.save(path)
        small = sheet.copy()
        small.thumbnail((1400, 1900), Image.Resampling.LANCZOS)
        small.save(OUT / f'{category}_review.png')
        print(f'{path} ({width} × {height})')


if __name__ == '__main__':
    try:
        import bpy
    except ImportError:
        compose()
    else:
        collect()
