#!/usr/bin/env python3
"""
Chunks each geological report into sentence-level passages, embeds them,
and indexes into the vector store — the RAG the README promises, which
previously didn't exist: extraction_agent.py sent the LLM the entire raw
report text every time. Retrieval matters most on longer, noisier real
reports; this repo's synthetic reports are short, so the effect is
modest here, but the retrieval path is real and exercised, not stubbed.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.vectors import get_vector_store  # noqa: E402


def chunk_report(report_id: str, text: str) -> list[dict]:
    """Splits on sentence boundaries — good enough for short synthetic
    reports; a real OCR'd report would need noise-tolerant chunking
    (see docs/BUILD_GUIDE.md's chunking challenge)."""
    sentences = [s.strip() for s in re.split(r"(?<=[.\n])\s+", text) if s.strip()]
    return [
        {
            "id": f"{report_id}-chunk-{i}",
            "text": s,
            "metadata": {"report_id": report_id, "chunk_index": i},
        }
        for i, s in enumerate(sentences)
    ]


def index_reports(reports_dir: str) -> int:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    store = get_vector_store("geo_reports")

    all_chunks = []
    for report_file in sorted(Path(reports_dir).glob("*.txt")):
        report_id = report_file.stem
        all_chunks.extend(chunk_report(report_id, report_file.read_text()))

    if not all_chunks:
        return 0

    embeddings = model.encode([c["text"] for c in all_chunks], show_progress_bar=False).tolist()
    store.upsert(
        ids=[c["id"] for c in all_chunks],
        embeddings=embeddings,
        metadatas=[c["metadata"] for c in all_chunks],
    )
    return len(all_chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", default="data/reports")
    args = parser.parse_args()

    n = index_reports(args.in_dir)
    print(f"indexed {n} chunks from reports in {args.in_dir}")


if __name__ == "__main__":
    main()
