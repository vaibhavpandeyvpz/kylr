"""Reject Android release payloads that ship the wrong ABI, debug code or keys."""
import shutil
import struct
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSPECTOR = ROOT / "game/tools/inspect_android_apk.ps1"


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required")
class AndroidPayloadTests(unittest.TestCase):
    def inspect(self, changes=None, remove=None):
        elf = bytearray(20)
        elf[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", elf, 18, 183)
        entries = {name: bytes(elf) for name in (
            "lib/arm64-v8a/libgodot_android.so",
            "lib/arm64-v8a/liblimboai.android.template_release.arm64.so",
        )}
        entries.update({name: b"fixture" for name in (
            "AndroidManifest.xml", "assets/assets.sparsepck",
            "assets/data/render_mesh_lods.bin",
            "assets/assets/ui/icons/touch/LICENSE",
            "assets/assets/ui/icons/touch/NOTICE.txt",
        )})
        entries.update(changes or {})
        if remove:
            del entries[remove]
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "test.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                for name, data in entries.items():
                    archive.writestr(name, data)
            return subprocess.run(
                ["pwsh", "-NoProfile", "-File", str(INSPECTOR), "-Path", str(apk)],
                capture_output=True, text=True,
            )

    def test_arm64_release_payload(self):
        result = self.inspect()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_private_keys_debug_libraries_and_diagnostics(self):
        for name in (
            "assets/.env", "assets/signing/release.p12",
            "lib/arm64-v8a/liblimboai.android.template_debug.arm64.so",
            "lib/x86_64/libgodot_android.so",
            "assets/.godot/exported/123/mobile_benchmark.gdc",
        ):
            with self.subTest(name=name):
                self.assertNotEqual(self.inspect({name: b"not-for-release"}).returncode, 0)

    def test_rejects_wrong_elf_architecture_even_in_arm64_directory(self):
        self.assertNotEqual(self.inspect({"lib/arm64-v8a/libgodot_android.so": b"\x7fELF" + b"\0" * 16}).returncode, 0)

    def test_requires_runtime_lods_and_redistribution_notices(self):
        for name in ("assets/data/render_mesh_lods.bin", "assets/assets/ui/icons/touch/LICENSE"):
            with self.subTest(name=name):
                self.assertNotEqual(self.inspect(remove=name).returncode, 0)


if __name__ == "__main__":
    unittest.main()
