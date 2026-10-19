"""Showcase the green Shield Core using the shared Energy Core casing."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'energy_core'))
from cube import showcase
if __name__ == '__main__':
    showcase(Path(__file__).resolve().parent, stem='shield_core')
