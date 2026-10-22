import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stamp_release_version import stamp


class ReleaseVersionTests(unittest.TestCase):
    def test_release_metadata_and_prerelease_platform_constraints(self):
        source = Path(__file__).resolve().parents[2] / "game"
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            for name in ("project.godot", "export_presets.cfg"):
                (project / name).write_bytes((source / name).read_bytes())
            for tag in ("v0.1.4", "v1.2.3-rc.1+build.9"):
                stamp(tag, project)
                config = (project / "project.godot").read_text(encoding="utf-8")
                presets = (project / "export_presets.cfg").read_text(encoding="utf-8")
                numeric = "0.1.4" if tag == "v0.1.4" else "1.2.3"
                self.assertIn(f'config/version="{tag[1:]}"', config)
                self.assertEqual(config.count('config/version='), 1)
                for key in ("file_version", "product_version"):
                    self.assertIn(f'application/{key}="{numeric}.0"', presets)
                for key in ("short_version", "version"):
                    self.assertIn(f'application/{key}="{numeric}"', presets)
                self.assertIn('application/bundle_identifier="com.vaibhavpandey.kylr"', presets)
            before = [(project / name).read_bytes() for name in ("project.godot", "export_presets.cfg")]
            for invalid in ("dev-main", "v1.2", "v01.2.3", "v65536.0.0", "v1.2.3\n"):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    stamp(invalid, project)
                self.assertEqual(before, [(project / name).read_bytes() for name in ("project.godot", "export_presets.cfg")])


if __name__ == "__main__":
    unittest.main()
