"""Build the static light prop using the shared industrial luminaire generator."""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Light': 'Emissive',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
}
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from light_common import build
if __name__ == '__main__':
    build(HERE)
