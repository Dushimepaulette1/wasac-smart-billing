import sys
from pathlib import Path

# backend/ml is shared with the training notebook, which imports its modules by bare name.
_ML = str(Path(__file__).resolve().parents[2] / "ml")  # backend/ml
if _ML not in sys.path:
    sys.path.insert(0, _ML)
