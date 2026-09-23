#!/usr/bin/env python3
"""Build sample PDFs and run an accuracy eval against a live backend."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import fitz
import requests

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"

CASES = [
    {
        "file": "acme_ppo_policy.txt",
        "pdf_name": "acme_ppo.pdf",
        "questions": [
            {
                "q": "What is the individual annual deductible?",
                "expect_any": ["1500", "1,500", "$1500", "$1,500"],
                "category": "cost_sharing",
            },
            {
                "q": "What is the ER copay?",
                "expect_any": ["250", "$250"],
                "expect_source_any": ["Emergency Room", "250", "ER"],
                "category": "er",
            },
            {
                "q": "Is MRI covered and what is the copay?",
                "expect_any": ["100", "MRI", "covered"],
                "expect_source_any": ["MRI", "100"],
                "category": "imaging",
            },
            {
                "q": "Is cosmetic surgery covered?",
                "expect_any": ["not", "exclu", "cosmetic"],
                "expect_source_any": ["Cosmetic", "EXCLUSIONS"],
                "category": "exclusions",
            },
            {
                "q": "Does physical therapy need prior authorization?",
                "expect_any": ["prior authorization", "20", "authorization"],
                "category": "prior_auth",
            },
        ],
    },
    {
        "file": "bluecare_hmo_policy.txt",
        "pdf_name": "bluecare_hmo.pdf",
        "questions": [
            {
                "q": "What is the individual out-of-pocket maximum?",
                "expect_any": ["4000", "4,000", "$4,000"],
                "category": "cost_sharing",
            },
            {
                "q": "What is the primary care copay?",
                "expect_any": ["20", "$20"],
                "category": "pcp",
            },
            {
                "q": "Does MRI need prior authorization?",
                "expect_any": ["prior authorization", "authorization", "yes"],
                "category": "prior_auth",
            },
            {
                "q": "Is acupuncture covered?",
                "expect_any": ["not", "acupuncture", "exclu"],
                "expect_source_any": ["Acupuncture", "NOT COVERED"],
                "category": "exclusions",
            },
        ],
    },
    {
        "file": "summit_epo_policy.txt",
        "pdf_name": "summit_epo.pdf",
        "questions": [
            {
                "q": "What is the individual annual deductible?",
                "expect_any": ["2000", "2,000", "$2,000"],
                "category": "cost_sharing",
            },
            {
                "q": "What is the emergency room copay?",
                "expect_any": ["400", "$400"],
                "expect_source_any": ["Emergency Room", "400"],
                "category": "er",
            },
            {
                "q": "Is infertility treatment covered?",
                "expect_any": ["not", "infertility", "exclu"],
                "expect_source_any": ["Infertility", "NOT COVERED", "EXCLUSIONS"],
                "category": "exclusions",
            },
            {
                "q": "What is the MRI copay and is prior auth required?",
                "expect_any": ["200", "prior"],
                "expect_source_any": ["MRI", "200"],
                "category": "imaging",
            },
        ],
    },
]


def text_to_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 54
    for line in text.splitlines():
        if y > 740:
            page = doc.new_page()
            y = 54
        page.insert_text((50, y), line[:110], fontsize=10)
        y += 14
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def post_with_retry(url, *, headers, files=None, json=None, timeout=180, retries=5):
    last = None
    for attempt in range(retries):
        if files is not None:
            last = requests.post(url, files=files, headers=headers, timeout=timeout)
        else:
            last = requests.post(url, json=json, headers=headers, timeout=timeout)
        if last.status_code != 429:
            return last
        import time

        time.sleep(2 + attempt * 2)
    return last


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--api-key", default="")
    args = parser.parse_args()
    headers = {"X-API-Key": args.api_key} if args.api_key else {}

    health = requests.get(f"{args.base_url}/health", timeout=10)
    health.raise_for_status()
    print("health:", health.json())

    passed = 0
    failed = 0
    by_category: dict[str, dict[str, int]] = {}
    report = []

    for case in CASES:
        text = (SAMPLES / case["file"]).read_text()
        pdf = text_to_pdf(text)
        ingest = post_with_retry(
            f"{args.base_url}/ingest",
            files={"file": (case["pdf_name"], pdf, "application/pdf")},
            headers=headers,
            timeout=180,
        )
        ingest.raise_for_status()
        doc_id = ingest.json()["document_id"]
        print(f"\n== {case['pdf_name']} -> {doc_id} ==")

        summary = post_with_retry(
            f"{args.base_url}/summary",
            json={"document_id": doc_id, "k": 8},
            headers=headers,
            timeout=120,
        )
        summary.raise_for_status()
        print("summary ok, latency_ms=", round(summary.json()["latency_ms"], 1))

        for item in case["questions"]:
            cat = item.get("category") or "general"
            by_category.setdefault(cat, {"passed": 0, "failed": 0})
            ask = post_with_retry(
                f"{args.base_url}/ask",
                json={"question": item["q"], "document_id": doc_id, "k": 4},
                headers=headers,
                timeout=120,
            )
            ask.raise_for_status()
            body = ask.json()
            answer = body["answer"]
            ok = any(tok.lower() in answer.lower() for tok in item["expect_any"])
            source_ok = True
            expect_src = item.get("expect_source_any") or []
            if expect_src and body.get("sources"):
                blob = " ".join(
                    f"{s.get('snippet') or ''} {s.get('source') or ''}"
                    for s in body["sources"][:2]
                )
                source_ok = any(tok.lower() in blob.lower() for tok in expect_src)
            status = "PASS" if ok and source_ok else "FAIL"
            if ok and source_ok:
                passed += 1
                by_category[cat]["passed"] += 1
            else:
                failed += 1
                by_category[cat]["failed"] += 1
            print(f"  [{status}] ({cat}) {item['q']}")
            print(f"         -> {answer[:160].replace(chr(10), ' ')}")
            if body.get("sources"):
                s0 = body["sources"][0]
                print(
                    f"         source p{s0.get('page')} score={s0.get('score')} "
                    f"snippet={(s0.get('snippet') or '')[:90]}"
                )
            if not source_ok:
                print("         !! source snippet did not match expected terms")
            report.append(
                {
                    "doc": case["pdf_name"],
                    "question": item["q"],
                    "category": cat,
                    "status": status,
                    "answer": answer,
                    "sources": body.get("sources"),
                }
            )

        queries = requests.get(
            f"{args.base_url}/queries",
            params={"document_id": doc_id, "limit": 10},
            headers=headers,
            timeout=30,
        )
        queries.raise_for_status()
        print(f"  queries stored: {len(queries.json())}")

    total = passed + failed
    rate = (100.0 * passed / total) if total else 0.0
    out = ROOT / "samples" / "last_eval_report.json"
    payload = {
        "passed": passed,
        "failed": failed,
        "pass_rate": round(rate, 1),
        "by_category": by_category,
        "cases": report,
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"\nRESULT {passed} passed, {failed} failed ({rate:.0f}%) -> {out}")
    print("by_category:", json.dumps(by_category))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
