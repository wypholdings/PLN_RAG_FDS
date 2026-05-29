from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_fds.config import MANUFACTURERS, PROJECT_ROOT
from rag_fds.generation import answer_question, build_prompt
from rag_fds.vector_index import search


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG QA with local retriever + Ollama generation.")
    parser.add_argument("--manufacturer", default="SIKA")
    parser.add_argument("--question", required=True)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"))
    parser.add_argument("--base-url", default=os.environ.get("OLLAMA_BASE_URL"))
    parser.add_argument("--timeout-seconds", type=int, default=int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "240")))
    parser.add_argument("--max-chars-per-source", type=int, default=int(os.environ.get("RAG_MAX_CHARS_PER_SOURCE", "1800")))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--show-prompt", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.manufacturer not in MANUFACTURERS:
        raise SystemExit(f"Unknown manufacturer: {args.manufacturer}")
    index_dir = PROJECT_ROOT / "data" / "indexes" / args.manufacturer.lower()

    if args.dry_run:
        results = search(index_dir, args.question, top_k=args.top_k)
        prompt = build_prompt(args.question, results, max_chars_per_source=args.max_chars_per_source)
        print(prompt)
        return 0

    answer = answer_question(
        index_dir=index_dir,
        question=args.question,
        top_k=args.top_k,
        model=args.model,
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
        max_chars_per_source=args.max_chars_per_source,
    )

    if args.json:
        print(json.dumps({"question": answer.question, "answer": answer.answer, "sources": answer.sources}, ensure_ascii=False, indent=2))
        return 0

    print(f"Pregunta: {answer.question}\n")
    print("Respuesta:")
    print(answer.answer)
    print("\nFuentes recuperadas:")
    for source in answer.sources:
        print(
            f"- [FUENTE {source['rank']}] {source['document']} | "
            f"seccion {source['section_number']} | paginas {source['page_start']}-{source['page_end']} | "
            f"{source['chunk_id']}"
        )

    if args.show_prompt:
        print("\n--- PROMPT ENVIADO A OLLAMA ---\n")
        print(answer.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
