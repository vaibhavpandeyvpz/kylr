"""Use the shared single-mesh export, rig and collider round-trip audit."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('architecture_roundtrip', HERE.parent/'hangar/validate.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
audit.HERE, audit.NAME = HERE, HERE.name

if __name__ == '__main__':
    audit.main()
