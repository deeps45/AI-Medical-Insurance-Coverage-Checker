"""Coverage summary helpers."""

from __future__ import annotations

from types import SimpleNamespace

from helpers import make_settings
from services.summary import build_coverage_summary


def test_summary_extractive_fields():
    docs = [
        SimpleNamespace(
            page_content=(
                "Annual Deductible: $1,000\n"
                "Out-of-Pocket Maximum: $5,000\n"
                "Emergency Room: $100 copay\n"
                "MRI Coverage: Covered with $50 copay"
            ),
            metadata={"page": 1, "source": "p.pdf", "document_id": "d1"},
        )
    ]
    result = build_coverage_summary(docs, settings=make_settings())
    assert result["summary"]
    assert result["fields"]["annual_deductible"]
    assert result["fields"]["emergency_room_copay"]
