"""Build the green Shield Core using the shared Energy Core casing."""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_CoreArmor': 'Metallic',
    'M_CoreInner': 'Emissive',
    'M_CoreOuter': 'Glass',
}
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'energy_core'))
from cube import build
if __name__ == '__main__':
    build(Path(__file__).resolve().parent, stem='shield_core')
