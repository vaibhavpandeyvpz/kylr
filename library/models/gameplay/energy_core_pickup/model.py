"""Build the 25 cm spherical Energy Core pickup."""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_CoreInner': 'Emissive',
    'M_CoreOuter': 'Glass',
}
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sphere import build
if __name__=='__main__':build(Path(__file__).resolve().parent)
