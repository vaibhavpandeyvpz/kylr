"""Convert retained ElevenLabs source clips; run with library/.venv Python."""
import argparse
import audioop
import hashlib
import json
import subprocess
from pathlib import Path
import imageio_ffmpeg
from prepare_weapon_audio import trim, smooth_end, write_wav


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('../library/sounds/speech'))
    parser.add_argument('--output', type=Path, default=Path('assets/audio/speech'))
    parser.add_argument('--only', nargs='+', help='Prepare only these stable recording keys')
    args = parser.parse_args()
    manifest = json.loads((args.source/'source_manifest.json').read_text(encoding='utf-8'))
    for clip in manifest['recordings']:
        if args.only and clip['key'] not in args.only:
            continue
        source = args.source/clip['source']
        if hashlib.sha256(source.read_bytes()).hexdigest() != clip['sha256']:
            raise ValueError('Source recording checksum mismatch: '+str(source))
        decoded = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-i', str(source), '-f', 's16le', '-ar', '48000', '-ac', '1', '-'], check=True, capture_output=True).stdout
        pcm = trim(decoded)
        peak = audioop.max(pcm,2)
        if not peak: raise ValueError('Silent recording: '+str(source))
        # Leave headroom before the runtime's controlled speech gain.
        pcm = audioop.mul(pcm,2,(32767*10**(-6/20))/peak)
        output = args.output/clip['bank']/(clip['key']+'.wav')
        write_wav(output,smooth_end(pcm,False))
        print(output)


if __name__ == '__main__': main()
