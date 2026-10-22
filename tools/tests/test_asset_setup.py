"""Focused checks for licensed-asset installation and credential-safe MCP IO."""
import io
import json
import hashlib
import zipfile
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import epidemic_mcp
import install_animations
import install_private_assets
import importlib.util
spec = importlib.util.spec_from_file_location("regolith", Path(__file__).resolve().parents[2]/"library/textures/lunar_surface/generate.py")
regolith = importlib.util.module_from_spec(spec)
spec.loader.exec_module(regolith)
from download_epidemic_audio import safe_audio_url
from install_epidemic_audio import destination, render_cue, wav_bytes, write_clip


class AssetSetupTests(unittest.TestCase):
    def test_preflight_rejects_uncatalogued_weapon_assets_before_install(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch)
            assets=root/'assets'
            for folder in ['assets/animations','assets/audio','data/weapons','data/audio']:
                (root/folder).mkdir(parents=True)
            (assets/'animations/manifest.json').write_text('{}')
            (assets/'audio/catalog.json').write_text('{}')
            (root/'data/audio/cues.json').write_text('{}')
            (root/'data/weapons/catalog.json').write_text(json.dumps({'weapons':{'bio_rifle':{'animation_family':'bio_rifle'}}}))
            with patch.object(install_private_assets,'GAME',assets):
                with self.assertRaisesRegex(ValueError,'bio_rifle/idle'):
                    install_private_assets.required_files()
                (root/'data/weapons/catalog.json').write_text('{"weapons":{}}')
                (root/'data/audio/cues.json').write_text('{"pulse_gun":{"asset":"weapons/pulse_gun_shot"}}')
                with self.assertRaisesRegex(ValueError,'pulse_gun_shot'):
                    install_private_assets.required_files()

    def test_runtime_weapon_assets_are_in_the_installation_catalogs(self):
        root=Path(__file__).resolve().parents[2]
        manifest=json.loads((root/'game/assets/animations/manifest.json').read_text(encoding='utf-8'))
        weapons=json.loads((root/'game/data/weapons/catalog.json').read_text(encoding='utf-8'))['weapons']
        for weapon in weapons.values():
            family=weapon['animation_family']
            for clip in ['idle','hit_reaction','aim_level','aim_up30','aim_down30']:
                self.assertIn(f'{family}/{clip}',manifest)
        catalog=json.loads((root/'game/assets/audio/catalog.json').read_text(encoding='utf-8'))
        cues=json.loads((root/'game/data/audio/cues.json').read_text(encoding='utf-8'))
        required=set(install_private_assets.audio_files())
        for cue in cues.values():
            asset=cue.get('asset','')
            if not asset.startswith('weapons/'):continue
            path='res://assets/audio/'+asset+'.wav'
            self.assertTrue(any(path==entry.get('file') or path in entry.get('files',[]) for entry in catalog.values()),asset)
            self.assertIn(path.removeprefix('res://assets/'),required)

    def test_sse_keepalive_and_notifications_before_result(self):
        response = io.BytesIO(b'data: \nid: 0\nretry: 3000\n\n'
                              b'data: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
                              b'data: {"jsonrpc":"2.0","id":4,"result":{"ok":true}}\n\n')
        response.headers = {"Content-Type":"text/event-stream"}
        self.assertEqual(epidemic_mcp.response_message(response,4)["result"],{"ok":True})

    def test_mismatched_json_rpc_id_fails(self):
        response = io.BytesIO(b'{"jsonrpc":"2.0","id":9,"result":{}}')
        response.headers = {"Content-Type":"application/json"}
        with self.assertRaisesRegex(ValueError,"ID"):
            epidemic_mcp.response_message(response,4)

    def test_credentials_are_not_redirected(self):
        self.assertIsNone(epidemic_mcp.NoRedirect().redirect_request(None,None,307,"",{},"https://other.invalid"))
        with self.assertRaises(ValueError):
            safe_audio_url("https://epidemicsound.com.evil.invalid/audio.wav")
        with self.assertRaises(ValueError):
            safe_audio_url("http://audiocdn.epidemicsound.com/audio.wav")

    def test_quoted_local_credential(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root/".env").write_text('UNRELATED=ignored\nEPIDEMICSOUND_API_KEY="test-only-key"\n')
            with patch.object(epidemic_mcp,"ROOT",root),patch.dict(epidemic_mcp.os.environ,{},clear=True):
                self.assertEqual(epidemic_mcp.credential(),"test-only-key")

    def test_animation_install_keeps_curated_manifest(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            target,source = root/"game",root/"authored"
            target.mkdir();(source/"tensor/common").mkdir(parents=True)
            required = {"common/idle":{"file":"tensor/common/idle.glb"}}
            authored = {**required,"unused":{"file":"tensor/common/unused.glb"}}
            (target/"manifest.json").write_text(json.dumps(required))
            (source/"manifest.json").write_text(json.dumps(authored))
            (source/"tensor/common/idle.glb").write_bytes(b"glTF")
            with patch.object(install_animations,"TARGET",target):
                install_animations.prepare(source,install=True)
            self.assertEqual(json.loads((target/"manifest.json").read_text()),required)
            self.assertTrue((target/"tensor/common/idle.glb").exists())
            self.assertFalse((target/"tensor/common/unused.glb").exists())

    def test_archive_checksum_is_checked_before_install(self):
        with tempfile.TemporaryDirectory() as scratch:
            archive=Path(scratch)/'assets.zip'
            archive.write_bytes(b'corrupted download')
            with patch.object(install_private_assets,'install') as install:
                with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                    install_private_assets.install_archive(archive,'0'*64)
                install.assert_not_called()

    def test_archive_extracts_only_manifest_paths(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);archive=root/'assets.zip'
            with zipfile.ZipFile(archive,'w') as zipped:
                zipped.writestr('animations/manifest.json','{}')
                zipped.writestr('../escape.txt','not installed')
                zipped.writestr('extra.txt','not installed')
            def inspect(folder):
                self.assertEqual((folder/'animations/manifest.json').read_text(),'{}')
                self.assertEqual([p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()],
                                 ['animations/manifest.json'])
                self.assertFalse((folder.parent/'escape.txt').exists())
            with patch.object(install_private_assets,'ROOT',root), \
                 patch.object(install_private_assets,'required_files',return_value=['animations/manifest.json']), \
                 patch.object(install_private_assets,'install',side_effect=inspect) as install:
                install_private_assets.install_archive(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
                install.assert_called_once()

    def test_archive_checksum_accepts_pasted_whitespace(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);archive=root/'assets.zip'
            with zipfile.ZipFile(archive,'w') as zipped:
                zipped.writestr('animations/manifest.json','{}')
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            with patch.object(install_private_assets,'ROOT',root), \
                 patch.object(install_private_assets,'required_files',return_value=['animations/manifest.json']), \
                 patch.object(install_private_assets,'install') as install:
                install_private_assets.install_archive(archive,' \n'+digest.upper()+'\r\n')
                install.assert_called_once()

    def test_archive_reports_wrong_root_before_installing(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);archive=root/'assets.zip'
            with zipfile.ZipFile(archive,'w') as zipped:
                zipped.writestr('assets/animations/manifest.json','{}')
            with patch.object(install_private_assets,'ROOT',root), \
                 patch.object(install_private_assets,'required_files',return_value=['animations/manifest.json']), \
                 patch.object(install_private_assets,'install') as install:
                with self.assertRaisesRegex(ValueError,'missing required entries: animations/manifest.json'):
                    install_private_assets.install_archive(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
                install.assert_not_called()

    def test_asset_paths_cannot_escape_root(self):
        with self.assertRaises(ValueError):
            install_animations.relative_file(Path("safe"),"../outside.glb")
        with self.assertRaises(ValueError):
            destination(Path("safe"),"game/assets/audio/../../../../outside.wav")

    def test_periodic_pbr_channels_and_normals(self):
        import numpy as np
        from PIL import Image
        rng = np.random.default_rng(4)
        source = Image.fromarray(rng.integers(30,150,(128,128,3),dtype='uint8'))
        albedo, normal, orm = regolith.maps(source,128)
        data = np.asarray(normal,dtype=float)/127.5-1
        self.assertLess(np.max(abs(np.linalg.norm(data,axis=2)-1)),.012)
        self.assertGreater(data[:,:,2].min(),.5)
        self.assertFalse(np.asarray(orm)[:,:,2].any())
        self.assertGreaterEqual(np.asarray(orm)[:,:,1].min(),200)
        a=np.asarray(albedo,dtype=float)
        interior=abs(np.diff(a,axis=0)).mean()
        self.assertLess(abs(a[0]-a[-1]).mean(),interior)

    def test_cue_tail_processing_and_failed_hash_protect_existing_file(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as scratch:
            path=Path(scratch)/"cue.wav"
            path.write_bytes(wav_bytes(np.array([10,20,30,40],dtype="<i2").tobytes()))
            entry={"start_frame":0,"frames":4,"tail_frames":2,"tail_mode":"fade"}
            self.assertEqual(np.frombuffer(render_cue(path,entry),dtype="<i2").tolist(),[10,20,15,0])
            entry["tail_mode"]="loop"
            self.assertEqual(np.frombuffer(render_cue(path,entry),dtype="<i2").tolist(),[10,20,20,20])
            before=path.read_bytes()
            with self.assertRaises(ValueError):
                write_clip(path,b"\0\0","wrong-checksum",(1,2,48000),True)
            self.assertEqual(path.read_bytes(),before)


class PrivateDownloadTests(unittest.TestCase):
    def test_download_installs_pinned_archive_and_removes_temporary_files(self):
        import install_private_assets as assets
        import os
        settings={'R2_ENDPOINT_URL':'https://example.invalid','R2_ASSET_URI':'s3://private/assets.zip',
                  'AWS_SECRET_ACCESS_KEY':'secret-value'}
        captured=[]
        def download(command, check):
            self.assertTrue(check)
            self.assertNotIn('secret-value',str(command))
            Path(command[4]).write_bytes(b'private fixture')
            captured.append(Path(command[4]))
        def install(archive, checksum):
            self.assertEqual(checksum,'a'*64)
            self.assertEqual(archive.read_bytes(),b'private fixture')
        with patch.dict(os.environ,settings),patch.object(assets.subprocess,'run',side_effect=download),patch.object(assets,'install_archive',side_effect=install):
            assets.download_archive('a'*64)
        self.assertFalse(captured[0].exists())

    def test_missing_pin_prevents_download(self):
        import install_private_assets as assets
        with patch.object(assets.subprocess,'run') as download:
            with self.assertRaises(ValueError): assets.download_archive('')
        download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
