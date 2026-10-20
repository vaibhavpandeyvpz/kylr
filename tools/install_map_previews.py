"""Compress native engine captures into the map selector's runtime photography."""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'game/data/maps/previews.json').read_text(encoding='utf-8'))
    total = 0
    count = 0
    for map_id, shots in manifest.items():
        assert len(shots) == 5, f'{map_id}: five distinct views required'
        for index, shot in enumerate(shots, 1):
            source = ROOT / 'game/reports/map-previews' / map_id / f'{index:02d}.png'
            target = ROOT / 'game' / shot['image'].removeprefix('res://')
            image = Image.open(source).convert('RGB')
            assert image.size == (1920, 1080), f'{source.name}: capture at native 1920x1080'
            target.parent.mkdir(parents=True, exist_ok=True)
            image.resize((1280, 720), Image.Resampling.LANCZOS).save(target, quality=86, method=4)
            total += target.stat().st_size
            count += 1
    print(f'Installed {count} map views, {total / 1024:.0f} KiB')


if __name__ == '__main__':
    main()
