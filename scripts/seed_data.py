"""Seed simple configuration data. Expanded in later blocks."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "reference_days"
SEED_DIR.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    (SEED_DIR / "README.md").write_text(
        "Place 12-15 reference days here, as defined in Block 10.\n",
        encoding="utf-8",
    )
    print("Seed directories initialized.")