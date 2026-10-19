"""Minimal deterministic RGBA PNG writer for generated data and color textures.

Bypass image-editor alpha conversions: independent noise channels must never be
treated as premultiplied color. Arrays use top-to-bottom image row order.
"""
import struct
import zlib
import numpy as np


def write_png(path, rgba, srgb=False):
    values = np.array(rgba, dtype=np.float32, copy=True)
    assert values.ndim == 3 and values.shape[2] == 4 and np.isfinite(values).all()
    if srgb:
        rgb = np.maximum(values[:, :, :3],0)
        values[:, :, :3] = np.where(rgb <= 0.0031308,rgb*12.92,1.055*np.power(rgb,1/2.4)-0.055)
    pixels = np.rint(np.clip(values,0,1)*255).astype(np.uint8)
    height, width = pixels.shape[:2]
    raw = b''.join(b'\x00'+row.tobytes() for row in pixels)

    def chunk(kind, payload):
        return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)

    result = b'\x89PNG\r\n\x1a\n'
    result += chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))
    if srgb:
        result += chunk(b'sRGB',b'\x00')
    result += chunk(b'IDAT',zlib.compress(raw,9))
    result += chunk(b'IEND',b'')
    path.write_bytes(result)
