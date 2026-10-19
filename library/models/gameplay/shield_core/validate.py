"""Validate the green Shield Core using the shared Energy Core casing."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'energy_core'))
from cube import validate
if __name__ == '__main__':
    validate(Path(__file__).resolve().parent, stem='shield_core')
