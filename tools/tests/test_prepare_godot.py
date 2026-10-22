import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_godot


class OfficialGodotInstallTests(unittest.TestCase):
    def fixture(self, folder, checksum=None):
        archive = folder / "official.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("Godot_v4.7.2-stable_win64.exe", b"editor")
            package.writestr("Godot_v4.7.2-stable_win64_console.exe", b"console")
            package.writestr("../../unexpected.exe", b"excluded")
        digest = hashlib.sha512(archive.read_bytes()).hexdigest()
        (folder / "godot-release.json").write_text(json.dumps({
            "version": "4.7.2.stable", "release": "4.7.2-stable",
            "files": {"Godot_v4.7.2-stable_win64.exe.zip": checksum or digest},
        }))
        return archive

    def test_verified_archive_extracts_only_expected_executables(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            archive = self.fixture(folder)
            with patch.object(prepare_godot, "__file__", str(folder / "prepare_godot.py")), patch.object(
                prepare_godot.urllib.request, "urlretrieve",
                side_effect=lambda _url, target: shutil.copyfile(archive, target),
            ):
                prepare_godot.install("windows", folder / "output")
            self.assertEqual((folder / "output/godot.exe").read_bytes(), b"editor")
            self.assertEqual((folder / "output/godot_console.exe").read_bytes(), b"console")
            self.assertEqual({p.name for p in (folder / "output").iterdir()}, {"godot.exe", "godot_console.exe"})

    def test_checksum_mismatch_does_not_replace_installed_editor(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            archive = self.fixture(folder, "0" * 128)
            (folder / "output").mkdir()
            (folder / "output/godot.exe").write_bytes(b"existing editor")
            with patch.object(prepare_godot, "__file__", str(folder / "prepare_godot.py")), patch.object(
                prepare_godot.urllib.request, "urlretrieve",
                side_effect=lambda _url, target: shutil.copyfile(archive, target),
            ), self.assertRaisesRegex(ValueError, "checksum mismatch"):
                prepare_godot.install("windows", folder / "output")
            self.assertEqual((folder / "output/godot.exe").read_bytes(), b"existing editor")


if __name__ == "__main__":
    unittest.main()
