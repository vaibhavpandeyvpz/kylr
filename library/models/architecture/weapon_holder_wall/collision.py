"""Collision the authored weapon_holder_wall."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from mechanical_mounts import collision
if __name__=='__main__':collision(HERE)
