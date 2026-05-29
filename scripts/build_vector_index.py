from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_fds.config import MANUFACTURERS, PROCESSED_DIR, PROJECT_ROOT
from rag_fds.vector_index import DEFAULT_EMBEDDING_MODEL, build_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local vector index for RAG chunks.")
    parser.add_argument("--manufacturer", required=True)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manufacturer = args.manufacturer
    if manufacturer not in MANUFACTURERS:
        raise SystemExit(f"Unknown manufacturer: {manufacturer}")
    slug = manufacturer.lower()
    chunks_path = PROCESSED_DIR / "chunks" / f"{slug}_chunks.jsonl"
    index_dir = PROJECT_ROOT / "data" / "indexes" / slug
    config = build_index(chunks_path, index_dir, args.model)
    print(json.dumps({"status": "ok", "index_dir": str(index_dir), **config}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
