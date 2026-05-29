from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "Documentos - Parcial final"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

PRIMARY_MANUFACTURER = "SIKA"
EXTRA_MANUFACTURER = "Pintuco"

MANUFACTURERS = {
    "SIKA": SOURCE_ROOT / "SIKA",
    "Pintuco": SOURCE_ROOT / "Pintuco",
    "CORONA": SOURCE_ROOT / "CORONA",
    "Pintuland": SOURCE_ROOT / "Pintuland",
}
