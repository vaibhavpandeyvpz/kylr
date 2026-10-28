"""Render Godot hero portraits and cinematic stills, then install compressed WebP media.

Run from library with its Python environment:
  .venv/Scripts/python tools/render_hero_showcase.py --preview --hero-only
  .venv/Scripts/python tools/render_hero_showcase.py
Use GODOT or --godot for the official editor. Captures and metadata stay under
ignored game/reports/cinematics/readme; only compressed images enter docs/media.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'game'
MAPS = ('ramparts', 'skyfall', 'faceoff')
SHOTS = ('vista', 'combat', 'portal', 'aftermath', 'launch')


def validate_metadata(folder, map_id, hero):
    selected = 'hero' if hero else 'all'
    reports = json.loads((folder / f'{map_id}-{selected}-metadata.json').read_text())
    assert len(reports) == (1 if hero else 5), (map_id, 'missing captures')
    expected = set(json.loads((GAME / 'data/weapons/catalog.json').read_text())['weapons'])
    for report in reports:
        assert report['quality'] == 'High' and report['internal_scale'] == 1 and not report['upscaling']
        assert report['rendering_ready']['ready'] and report['gameplay_driven_shots']
        assert report['gpu'], 'Capture requires a rendering device'
        assert all(a.get('weapon_palette_authored',False) for a in report['actors']), (map_id,'weapon palette')
        if hero:
            actors = report['actors']
            assert len(actors) == 10 and all(a['alive'] for a in actors), (map_id, 'hero roster')
            assert {a['weapon'] for a in actors} == expected, (map_id, 'weapon coverage')
            assert len({(a['head'], a['upper_body'], a['primary'], a['secondary']) for a in actors}) == 10
            assert all(a['shots'] > 0 or a.get('streaming', False) for a in actors), (map_id, 'inactive weapons')
        elif report['shot'] != 'vista':
            assert len(report['actors']) >= 2
    return reports


def capture(godot, folder, map_id, shot, preview):
    folder.mkdir(parents=True, exist_ok=True)
    args = [godot, '--path', str(GAME), '--render-thread', 'safe', '--gpu-index', '0',
            'tools/cinematic_showcase.tscn', '--', f'--map={map_id}', f'--shot={shot}',
            f'--out={folder.as_posix()}']
    if preview:
        args.append('--preview=1')
    log_path = folder / f'{map_id}-{shot}.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(args, cwd=GAME, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 300
        while True:
            try:
                code = process.wait(timeout=.5)
                break
            except subprocess.TimeoutExpired:
                partial = log_path.read_text(encoding='utf-8', errors='replace')
                failed = 'SCRIPT ERROR:' in partial or 'ERROR:' in partial
                if not failed and time.monotonic() < deadline:
                    continue
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    process.kill()
                raise RuntimeError(f'Capture {"failed" if failed else "timed out"}: {log_path}')
    output = log_path.read_text(encoding='utf-8', errors='replace')
    assert code == 0 and not any(s in output for s in ('SCRIPT ERROR:', 'ERROR:', 'instances were leaked')), log_path
    validate_metadata(folder, map_id, shot == 'hero')
    print(f'CAPTURE {map_id}/{shot}', flush=True)


def install(folder, maps, preview, hero_only):
    output = folder / 'compressed' if preview else ROOT / 'docs/media'
    output.mkdir(parents=True, exist_ok=True)
    for map_id in maps:
        if not hero_only:
            for shot in SHOTS:
                path = output / 'cinematics' / f'{map_id}-{shot}.webp'
                path.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(folder / f'{map_id}-{shot}.png') as frame:
                    frame.convert('RGB').resize((1280,720), Image.Resampling.LANCZOS).save(path, quality=86, method=6)
        path = output / 'heroes' / f'{map_id}.webp'
        path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(folder / f'{map_id}-hero.png') as frame:
            assert frame.width * 3 == frame.height * 2
            frame.convert('RGB').save(path, quality=88, method=6)
    if set(maps) == set(MAPS):
        width, height, gap = (512,768,8) if preview else (1024,1536,12)
        canvas = Image.new('RGB', (width*3+gap*4,height+gap*2), '#e8e7e3')
        for index, map_id in enumerate(MAPS):
            with Image.open(folder / f'{map_id}-hero.png') as frame:
                portrait = frame.convert('RGB').resize((width,height), Image.Resampling.LANCZOS)
            canvas.paste(portrait,(gap+index*(width+gap),gap))
        path = output / 'hero-showcase.webp'
        canvas.save(path, quality=88, method=6)
        print(f'HERO {path.relative_to(ROOT)} {canvas.size} {path.stat().st_size} bytes', flush=True)
    sizes = {str(p.relative_to(output)):p.stat().st_size for p in output.rglob('*.webp')}
    (folder / 'compression.json').write_text(json.dumps(sizes, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--hero-only', action='store_true')
    parser.add_argument('--maps', nargs='+', choices=MAPS, default=list(MAPS))
    parser.add_argument('--install-only', action='store_true')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--godot', default=os.environ.get('GODOT','godot'))
    args = parser.parse_args()
    folder = (args.input or GAME / 'reports/cinematics/readme' / ('proof' if args.preview else 'final')).resolve()
    if not args.install_only:
        godot = shutil.which(args.godot)
        assert godot, 'Set GODOT or pass --godot with official Godot 4.7.2'
        version = subprocess.check_output([godot,'--version'], text=True).strip()
        assert version.startswith('4.7.2.stable.official.'), version
        for map_id in args.maps:
            capture(godot,folder,map_id,'hero',args.preview)
            if not args.hero_only:
                capture(godot,folder,map_id,'all',args.preview)
    for map_id in args.maps:
        validate_metadata(folder,map_id,True)
        if not args.hero_only:
            validate_metadata(folder,map_id,False)
    install(folder,args.maps,args.preview,args.hero_only)

if __name__ == '__main__':
    main()
