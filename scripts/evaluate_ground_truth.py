from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_fds.config import MANUFACTURERS, PROJECT_ROOT
from rag_fds.generation import answer_question
from rag_fds.vector_index import search


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", text.lower()).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RAG against ground truth pairs.")
    parser.add_argument("--manufacturer", default="SIKA")
    parser.add_argument("--ground-truth", default="data/ground_truth/sika_ground_truth_25.json")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--max-chars-per-source", type=int, default=1700)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--with-llm", action="store_true")
    return parser.parse_args()


def check_terms(terms: list[str], text: str) -> tuple[bool, float]:
    if not terms:
        return True, 1.0
    normalized = normalize(text)
    found = sum(1 for term in terms if normalize(term) in normalized)
    return found == len(terms), found / len(terms)


def main() -> int:
    args = parse_args()
    if args.manufacturer not in MANUFACTURERS:
        raise SystemExit(f"Unknown manufacturer: {args.manufacturer}")

    gt_path = PROJECT_ROOT / args.ground_truth
    gt_items = json.loads(gt_path.read_text(encoding="utf-8"))
    index_dir = PROJECT_ROOT / "data" / "indexes" / args.manufacturer.lower()

    rows: list[dict] = []
    passed_top1_section = 0
    passed_topk_section = 0
    passed_context_terms = 0
    passed_answer_terms = 0
    answered = 0

    for item in gt_items:
        question = item["question"]
        expected_section = int(item["expected_section"])
        expected_terms = item.get("expected_terms", [])

        retrieval = search(index_dir, question, top_k=args.top_k)
        top1_section = int(retrieval[0].chunk["section_number"]) if retrieval else -1
        topk_sections = [int(result.chunk["section_number"]) for result in retrieval]
        context_text = "\n".join(result.chunk["content"] for result in retrieval)

        context_terms_ok, context_terms_ratio = check_terms(expected_terms, context_text)
        top1_ok = top1_section == expected_section
        topk_ok = expected_section in topk_sections

        if top1_ok:
            passed_top1_section += 1
        if topk_ok:
            passed_topk_section += 1
        if context_terms_ok:
            passed_context_terms += 1

        answer_text = ""
        answer_terms_ok = False
        answer_terms_ratio = 0.0
        if args.with_llm:
            answer = answer_question(
                index_dir=index_dir,
                question=question,
                top_k=args.top_k,
                timeout_seconds=args.timeout_seconds,
                max_chars_per_source=args.max_chars_per_source,
            )
            answer_text = answer.answer
            answer_terms_ok, answer_terms_ratio = check_terms(expected_terms, answer_text)
            answered += 1
            if answer_terms_ok:
                passed_answer_terms += 1

        rows.append(
            {
                "id": item["id"],
                "type": item["type"],
                "question": question,
                "expected_section": expected_section,
                "top1_section": top1_section,
                "top1_ok": top1_ok,
                "topk_ok": topk_ok,
                "context_terms_ok": context_terms_ok,
                "context_terms_ratio": round(context_terms_ratio, 3),
                "answer_terms_ok": answer_terms_ok,
                "answer_terms_ratio": round(answer_terms_ratio, 3),
                "top1_chunk_id": retrieval[0].chunk["chunk_id"] if retrieval else "",
                "answer_excerpt": answer_text[:400].replace("\n", " ") if answer_text else "",
            }
        )

    reports_dir = PROJECT_ROOT / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    mode = "with_llm" if args.with_llm else "retrieval_only"
    csv_path = reports_dir / f"ground_truth_eval_{args.manufacturer.lower()}_{mode}.csv"
    json_path = reports_dir / f"ground_truth_eval_{args.manufacturer.lower()}_{mode}.json"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    summary = {
        "manufacturer": args.manufacturer,
        "ground_truth_items": total,
        "evaluation_mode": mode,
        "top1_section_accuracy": round(passed_top1_section / total, 4),
        "topk_section_recall": round(passed_topk_section / total, 4),
        "context_term_coverage_pass_rate": round(passed_context_terms / total, 4),
        "llm_answers_evaluated": answered,
        "answer_term_pass_rate": round((passed_answer_terms / answered), 4) if answered else None,
        "report_csv": str(csv_path),
        "report_json": str(json_path),
    }
    json_path.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
