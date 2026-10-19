"""Showcase the 25 cm hollow Energy Core cube."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cube import showcase

if __name__ == "__main__":
    showcase(Path(__file__).resolve().parent)
