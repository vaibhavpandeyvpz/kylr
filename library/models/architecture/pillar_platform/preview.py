"""Preview the authored pillar_platform."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from mechanical_mounts import preview
if __name__=='__main__':preview(HERE)
