"""Build the authored weapon_holder_wall."""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Diffuse',
    'M_Primary': 'Diffuse',
    'M_Secondary': 'Diffuse',
}
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from mechanical_mounts import build
if __name__=='__main__':build(HERE)
