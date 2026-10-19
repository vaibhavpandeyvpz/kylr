"""Preview the 10 cm spherical Energy Core pickup."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sphere import preview
if __name__=='__main__':preview(Path(__file__).resolve().parent)
