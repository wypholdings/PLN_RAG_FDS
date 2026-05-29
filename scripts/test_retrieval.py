from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_fds.config import MANUFACTURERS, PROJECT_ROOT, REPORTS_DIR
from rag_fds.vector_index import search


TESTS = [
    {
        "id": "emergency_phone",
        "query": "telefono de emergencia CISPROQUIM",
        "expected_section": 1,
        "required_terms": ["CISPROQUIM", "Bogotá", "Resto del país"],
    },
    {
        "id": "ppe_section_8",
        "query": "equipo de proteccion personal guantes gafas respirador seccion 8",
        "expected_section": 8,
        "required_terms": ["Protección respiratoria"],
    },
    {
        "id": "transport_un",
        "query": "numero ONU transporte clase grupo de embalaje",
        "expected_section": 14,
        "required_terms": ["Número ONU", "Grupo de embalaje"],
    },
    {
        "id": "composition_cas",
        "query": "composicion componentes CAS concentracion",
        "expected_section": 3,
        "required_terms": ["CAS"],
    },
    {
        "id": "physical_properties",
        "query": "propiedades fisicas quimicas punto de inflamacion densidad",
        "expected_section": 9,
        "required_terms": ["Aspecto"],
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retrieval smoke tests.")
    parser.add_argument("--manufacturer", default="SIKA")
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def normalize(text: str) -> str:
    return text.casefold()


def main() -> int:
    args = parse_args()
    if args.manufacturer not in MANUFACTURERS:
        raise SystemExit(f"Unknown manufacturer: {args.manufacturer}")
    index_dir = PROJECT_ROOT / "data" / "indexes" / args.manufacturer.lower()
    rows = []
    for test in TESTS:
        results = search(index_dir, test["query"], args.top_k)
        top = results[0].chunk
        top_content = normalize(top["content"])
        required_terms_found = [
            term for term in test["required_terms"] if normalize(term) in top_content
        ]
        expected_section_in_top_k = any(
            result.chunk["section_number"] == test["expected_section"] for result in results
        )
        rows.append(
            {
                "id": test["id"],
                "query": test["query"],
                "expected_section": test["expected_section"],
                "top1_section": top["section_number"],
                "top1_chunk_id": top["chunk_id"],
                "top1_source_file": top["source_file"],
                "top1_score": round(results[0].score, 6),
                "expected_section_top1": top["section_number"] == test["expected_section"],
                "expected_section_in_top_k": expected_section_in_top_k,
                "required_terms": "|".join(test["required_terms"]),
                "required_terms_found": "|".join(required_terms_found),
                "required_terms_ok": len(required_terms_found) == len(test["required_terms"]),
            }
        )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS_DIR / f"retrieval_test_report_{args.manufacturer.lower()}.csv"
    json_path = REPORTS_DIR / f"retrieval_test_summary_{args.manufacturer.lower()}.json"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "manufacturer": args.manufacturer,
        "tests": len(rows),
        "top1_section_passed": sum(row["expected_section_top1"] for row in rows),
        "topk_section_passed": sum(row["expected_section_in_top_k"] for row in rows),
        "required_terms_passed": sum(row["required_terms_ok"] for row in rows),
        "status": "pass"
        if all(row["expected_section_in_top_k"] and row["required_terms_ok"] for row in rows)
        else "review",
        "report_csv": str(csv_path),
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
