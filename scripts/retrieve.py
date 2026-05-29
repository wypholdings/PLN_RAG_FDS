from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_fds.config import MANUFACTURERS, PROJECT_ROOT
from rag_fds.vector_index import search


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search local vector index.")
    parser.add_argument("--manufacturer", default="SIKA")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def result_to_dict(result) -> dict:
    chunk = result.chunk
    return {
        "rank": result.rank,
        "score": round(result.score, 6),
        "chunk_id": chunk["chunk_id"],
        "product": chunk["product"],
        "source_file": chunk["source_file"],
        "section_number": chunk["section_number"],
        "section_title": chunk["section_title"],
        "pages": [chunk["page_start"], chunk["page_end"]],
        "content_types": chunk["content_types"],
        "table_ids": chunk["table_ids"],
        "image_ids": chunk["image_ids"],
        "asset_paths": chunk["asset_paths"],
        "excerpt": chunk["content"][:900],
        "trace": chunk["trace"],
    }


def main() -> int:
    args = parse_args()
    if args.manufacturer not in MANUFACTURERS:
        raise SystemExit(f"Unknown manufacturer: {args.manufacturer}")
    index_dir = PROJECT_ROOT / "data" / "indexes" / args.manufacturer.lower()
    results = [result_to_dict(result) for result in search(index_dir, args.query, args.top_k)]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    print(f"Pregunta: {args.query}\n")
    for result in results:
        print(f"[{result['rank']}] score={result['score']} | {result['product']}")
        print(f"    Documento: {result['source_file']}")
        print(f"    Seccion {result['section_number']}: {result['section_title']} | paginas {result['pages'][0]}-{result['pages'][1]}")
        print(f"    Tipos: {', '.join(result['content_types'])}")
        if result["table_ids"]:
            print(f"    Tablas: {', '.join(result['table_ids'])}")
        if result["image_ids"]:
            print(f"    Imagenes: {', '.join(result['image_ids'])}")
        print(f"    Extracto: {result['excerpt'].replace(chr(10), ' ')[:500]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
