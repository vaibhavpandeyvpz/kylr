"""Build the shared, periodic lunar PBR maps from the original albedo source.

Run from library/: .venv/Scripts/python.exe textures/lunar_surface/generate.py
The normal is a conservative image-derived relief approximation, not scan data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[2] / 'game/assets/textures/lunar_surface'
SIZE = 2048
TILE_METRES = 1 / .24
NAMES = ('regolith_albedo.png', 'regolith_normal.png', 'regolith_orm.png')


def periodic(image):
    """Remove boundary discontinuities with a periodic-plus-smooth decomposition."""
    edge = np.zeros_like(image)
    edge[0] = image[-1] - image[0]
    edge[-1] = -edge[0]
    edge[:, 0] += image[:, -1] - image[:, 0]
    edge[:, -1] -= image[:, -1] - image[:, 0]
    h, w = image.shape
    denominator = (2*np.cos(2*np.pi*np.arange(h)/h)[:, None] +
                   2*np.cos(2*np.pi*np.arange(w)/w)[None, :] - 4)
    denominator[0, 0] = 1
    smooth = np.fft.fft2(edge) / denominator
    smooth[0, 0] = 0
    return image - np.fft.ifft2(smooth).real


def blur(image, sigma):
    fy = np.fft.fftfreq(image.shape[0])[:, None]
    fx = np.fft.fftfreq(image.shape[1])[None, :]
    return np.fft.ifft2(np.fft.fft2(image)*np.exp(-2*np.pi**2*sigma**2*(fx*fx+fy*fy))).real


def maps(source, size=SIZE):
    base = np.asarray(source.convert('RGB').resize((size, size), Image.Resampling.LANCZOS), dtype=np.float32)/255
    channels = [periodic(base[:, :, c]) for c in range(3)]
    # Remove broad illumination drift so the tile's coarse mips stay uniform.
    # Keep the grains' mineral colour; broad relief comes from arena geometry.
    albedo = np.stack([channel-blur(channel, size/24)+channel.mean()
                       for channel in channels], axis=2)
    # Keep mineral colour separate from the relief-derived occlusion channel.
    albedo = np.clip(albedo, 0, 1)
    luminance = albedo @ np.array([.2126, .7152, .0722])
    detail = blur(luminance, .85) - blur(luminance, 20)
    height = detail * .006  # metres; sub-millimetre dust, shallow embedded grains
    spacing = TILE_METRES / size
    dx = (np.roll(height, -1, 1)-np.roll(height, 1, 1))/(2*spacing)
    dy = (np.roll(height, -1, 0)-np.roll(height, 1, 0))/(2*spacing)
    normal = np.stack([-dx, dy, np.ones_like(dx)], axis=2)
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    cavity = np.maximum(blur(height, 5)-height, 0)
    ao = np.clip(1-cavity*160, .78, 1)
    roughness = np.clip(.92-detail*.38, .8, .98)
    orm = np.stack([ao, roughness, np.zeros_like(ao)], axis=2)
    encode = lambda data: Image.fromarray(np.rint(np.clip(data, 0, 1)*255).astype('uint8'))
    return encode(albedo), encode(normal*.5+.5), encode(orm)


def check():
    for name in NAMES:
        left, right = HERE/name, GAME/name
        if left.read_bytes() != right.read_bytes():
            raise ValueError(f'Library/game texture mismatch: {name}')
        with Image.open(left) as image:
            if image.size != (SIZE, SIZE) or image.mode != 'RGB':
                raise ValueError(f'Expected RGB {SIZE}px texture: {name}')
    normal = np.asarray(Image.open(HERE/NAMES[1]), dtype=float)/127.5-1
    if np.max(np.abs(np.linalg.norm(normal, axis=2)-1)) > .012 or normal[:, :, 2].min() < .5:
        raise ValueError('Invalid tangent-space normal map')
    orm = np.asarray(Image.open(HERE/NAMES[2]))
    if orm[:, :, 2].any() or orm[:, :, 1].min() < 200:
        raise ValueError('Regolith must be rough and nonmetallic')
    albedo = np.asarray(Image.open(HERE/NAMES[0]), dtype=float)
    interior = (np.abs(np.diff(albedo, axis=0)).mean()+np.abs(np.diff(albedo, axis=1)).mean())/2
    seam = max(np.abs(albedo[0]-albedo[-1]).mean(), np.abs(albedo[:, 0]-albedo[:, -1]).mean())
    if seam > interior*1.5:
        raise ValueError(f'Tile border discontinuity: {seam/interior:.2f}x interior')
    print(f'PASS original lunar PBR: matching {SIZE}px maps, unit OpenGL normals, zero metal, seam {seam/interior:.2f}x')


def generate():
    source = HERE/'source_albedo.png'
    GAME.mkdir(parents=True, exist_ok=True)
    for name, image in zip(NAMES, maps(Image.open(source))):
        image.save(HERE/name, optimize=True)
        shutil.copyfile(HERE/name, GAME/name)
    (HERE/'maps.json').write_text(json.dumps({
        'tile_metres': TILE_METRES, 'resolution': SIZE, 'normal_convention': 'OpenGL',
        'orm': ['occlusion', 'roughness', 'metallic_zero'],
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'maps': {name: hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in NAMES}
    }, indent=2)+'\n')
    check()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    check() if args.check else generate()
