"""Validate the 25 cm hollow Energy Core cube."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cube import validate

if __name__ == "__main__":
    validate(Path(__file__).resolve().parent)
