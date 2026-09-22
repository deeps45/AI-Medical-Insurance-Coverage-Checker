#!/usr/bin/env python3
"""Optional Pinecone smoke test. Skips unless PINECONE_SMOKE=1 and PINECONE_API_KEY set."""

from __future__ import annotations

import os
import sys


def main() -> int:
    if os.getenv("PINECONE_SMOKE", "").lower() not in {"1", "true", "yes"}:
        print("SKIP: set PINECONE_SMOKE=1 to run this smoke test")
        return 0

    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("FAIL: PINECONE_API_KEY is required when PINECONE_SMOKE=1")
        return 1

    index_name = os.getenv("PINECONE_INDEX_NAME", "docsage-lite")
    from pinecone import Pinecone

    pc = Pinecone(api_key=api_key)
    names = [idx.name for idx in pc.list_indexes()]
    print("indexes:", names)
    if index_name not in names:
        print(f"FAIL: index '{index_name}' not found")
        return 1

    index = pc.Index(index_name)
    stats = index.describe_index_stats()
    print("stats:", stats)
    print("PINECONE_SMOKE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
