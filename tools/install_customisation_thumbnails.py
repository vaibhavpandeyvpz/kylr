"""Compress the authored Blender portraits into small runtime WebP tiles."""
from pathlib import Path
import argparse
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'library/build/customisation'
TARGET = ROOT/'game/assets/ui/customisation'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--section',choices=['all','heads','upper_bodies','emotes','armor'],default='all')
    args = parser.parse_args()
    count = 0
    total = 0
    for path in SOURCE.rglob('*.png'):
        if args.section != 'all' and path.relative_to(SOURCE).parts[0] != args.section: continue
        target = (TARGET/path.relative_to(SOURCE)).with_suffix('.webp')
        target.parent.mkdir(parents=True,exist_ok=True)
        with Image.open(path) as image:
            image.resize((192,192),Image.Resampling.LANCZOS).save(target,'WEBP',quality=87,method=4)
        count += 1
        total += target.stat().st_size
    print(f'Installed {count} portraits, {total/1024:.0f} KiB')
