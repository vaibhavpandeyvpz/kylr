"""Prepare retained instrumental sources as compact stereo Godot music assets."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import imageio_ffmpeg


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('../library/sounds/music'))
    parser.add_argument('--output',type=Path,default=Path('assets/audio/music'))
    args=parser.parse_args()
    manifest=json.loads((args.source/'source_manifest.json').read_text(encoding='utf-8'))
    args.output.mkdir(parents=True,exist_ok=True)
    for clip in manifest['recordings']:
        source=args.source/clip['source']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=clip['sha256']:
            raise ValueError('Source checksum mismatch: '+str(source))
        duration=float(clip.get('duration',clip['duration_secs']))
        if clip['key'] in ['lobby','active','pressure']: duration=38.4 # 64 beats at 100 BPM.
        filters=f'loudnorm=I=-18:TP=-3:LRA=9,aresample=48000,afade=t=in:st=0:d=0.015,afade=t=out:st={duration-0.12}:d=0.12'
        target=args.output/(clip['key']+'.ogg')
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-y','-i',str(source),'-t',str(duration),'-af',filters,'-ac','2','-c:a','libvorbis','-q:a','5',str(target)],check=True)
        print(target)


if __name__=='__main__': main()
