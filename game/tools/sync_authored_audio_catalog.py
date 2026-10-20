"""Publish complete retained recording banks to the game's audio registries."""
import json
from pathlib import Path


def main():
    speech_path=Path('data/audio/speech.json')
    speech=json.loads(speech_path.read_text(encoding='utf-8'))
    music_path=Path('data/audio/music.json')
    music=json.loads(music_path.read_text(encoding='utf-8'))
    catalog_path=Path('assets/audio/catalog.json')
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    plan=json.loads(Path('../library/sounds/speech/recording_plan.json').read_text(encoding='utf-8'))
    for kind in ['speech','music']:
        manifest=json.loads(Path(f'../library/sounds/{kind}/source_manifest.json').read_text(encoding='utf-8'))
        if kind=='speech':
            expected={(voice['id'],key) for voice in plan['voices'] for key in plan['lines']['robot']}
            expected.update(('announcer',key) for key in plan['lines']['announcer'])
            actual=[(clip['bank'],clip['key']) for clip in manifest['recordings']]
            if len(actual)!=len(expected) or set(actual)!=expected:
                raise ValueError('speech: incomplete or duplicate source bank')
        elif len(manifest['recordings'])!=11: raise ValueError('music: incomplete source bank')
        for clip in manifest['recordings']:
            asset=f"speech/{clip['bank']}/{clip['key']}" if kind=='speech' else f"music/{clip['key']}"
            file=f"assets/audio/{asset}.{'wav' if kind=='speech' else 'ogg'}"
            if not Path(file).is_file(): raise FileNotFoundError(file)
            entry={'provider':'ElevenLabs','file':'res://'+file,'generation_id':clip['generation_id'],'source_sha256':clip['sha256']}
            if 'voice_id' in clip: entry['voice_id']=clip['voice_id']
            catalog[asset]=entry
            if kind=='music': music[clip['key']]='res://'+file
            elif clip['bank']=='announcer': speech['announcer'][clip['key']]=asset
            else:
                robot=next(r for r in speech['robots'] if r['id']==clip['bank'])
                robot['voice_id']=clip['voice_id']
                robot['voice_name']=clip['voice_name']
                robot['lines'][clip['key']]=asset
    for path,content in [(speech_path,speech),(music_path,music),(catalog_path,catalog)]:
        path.write_text(json.dumps(content,indent=2)+'\n',encoding='utf-8')
    print(f"Published {len(expected)} speech recordings, ten distinct robot banks and 11 musical cues")


if __name__=='__main__': main()
