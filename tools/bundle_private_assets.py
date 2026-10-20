"""Build the checksummed, allowlisted private asset archive used by CI."""
import argparse
import hashlib
from pathlib import Path
import zipfile

from install_private_assets import GAME, check, required_files


def bundle(output):
    check()
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name in required_files():
            archive.write(GAME/name,name)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n',encoding='utf-8')
    print(f'Private bundle: {len(required_files())} files; SHA-256 {digest}')
    return digest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    bundle(parser.parse_args().output)
