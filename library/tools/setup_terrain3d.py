"""Install the pinned Terrain3D authoring SDK into the ignored local tool cache."""
from pathlib import Path
import hashlib
import io
import zipfile
import requests

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.2-stable'
SHA256 = 'a071850250ec5e596aa54da61c01d75768774eb379ee997584d426a45f4884a2'
DIRECTORY = ROOT / '.local/terrain3d'


def install():
    marker = DIRECTORY / 'sdk.sha256'
    if marker.exists() and marker.read_text(encoding='utf-8').strip() == SHA256 and (DIRECTORY/'addons/terrain_3d/terrain.gdextension').is_file():
        return DIRECTORY
    url = f'https://github.com/TokisanGames/Terrain3D/releases/download/v{VERSION}/Terrain3D_v{VERSION}.zip'
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    assert hashlib.sha256(response.content).hexdigest() == SHA256, 'Terrain3D SDK checksum mismatch'
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.startswith('addons/terrain_3d/'):
                continue
            target = (DIRECTORY / info.filename).resolve()
            assert target.is_relative_to(DIRECTORY.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    marker.write_text(SHA256 + '\n', encoding='utf-8')
    return DIRECTORY


if __name__ == '__main__':
    print(install())
