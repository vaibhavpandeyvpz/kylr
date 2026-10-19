import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from configure_online import configure


class OnlineConfigurationTests(unittest.TestCase):
    def test_public_origin_round_trip_and_other_settings_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder)/'project.godot'
            project.write_text('[application]\nconfig/name="KYLR"\n\n[rendering]\nrenderer="test"\n')
            configure('https://kylr.example.com/',project)
            configure('https://another.example.com',project)
            text=project.read_text()
            self.assertEqual(text.count('[network]'),1)
            self.assertEqual(text.count('services/api_url='),1)
            self.assertIn('config/name="KYLR"',text)
            self.assertIn('https://another.example.com',text)

    def test_rejects_credentials_insecure_remote_and_non_origin_urls(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder)/'project.godot'
            project.write_text('[application]\n')
            for url in ('http://remote.example.com','https://user:secret@example.com',
                'https://example.com/path','https://example.com?token=secret','file:///tmp/secret',
                'https://example.com:bad','https://example.com:99999','https://exam\nple.com'):
                with self.subTest(url=url),self.assertRaises(ValueError): configure(url,project)
            configure('http://127.0.0.1:8080',project)


if __name__=='__main__': unittest.main()
