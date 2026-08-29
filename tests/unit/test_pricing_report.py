"""
Unit Tests: Pricing & Monetization Research Report Validation.
Ensures docs/reports/PRICING_AND_MONETIZATION_REPORT.md exists and satisfies all research requirements.
"""
from __future__ import annotations
from pathlib import Path
import pytest

REPORT_PATH = Path(__file__).parent.parent.parent / "docs" / "reports" / "PRICING_AND_MONETIZATION_REPORT.md"


def test_pricing_report_exists():
    """Verify PRICING_AND_MONETIZATION_REPORT.md exists and is non-empty."""
    assert REPORT_PATH.exists(), f"Pricing report missing at {REPORT_PATH}"
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert len(content) > 5000, "Pricing report is too short (expected > 5000 chars)"
    assert len(content.splitlines()) >= 150, "Pricing report has insufficient line depth"


def test_pricing_report_contains_competitors():
    """Verify report evaluates key industry competitors."""
    content = REPORT_PATH.read_text(encoding="utf-8")
    competitors = ["Atticus", "Vellum", "Designrr", "Sudowrite", "Reedsy"]
    for comp in competitors:
        assert comp.lower() in content.lower(), f"Competitor '{comp}' not analyzed in report"


def test_pricing_report_contains_recommended_tiers():
    """Verify report details the recommended 3-tier pricing structure."""
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "19" in content, "Missing $19 Pro Pass tier analysis"
    assert "29" in content, "Missing $29 Author Pro tier analysis"
    assert "Demo" in content or "demo" in content, "Missing Free Demo tier analysis"
    assert "Pro Pass" in content, "Missing Pro Pass naming"


def test_pricing_report_contains_unit_economics_and_margins():
    """Verify report contains DeepSeek/LLM token costs and gross margin analysis."""
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "DeepSeek" in content or "deepseek" in content, "Missing AI model economics"
    assert "Typst" in content, "Missing Typst compute economics"
    assert "Margin" in content or "margin" in content, "Missing margin calculations"
    assert "Stripe" in content and "PayPal" in content, "Missing gateway comparison"


def test_pricing_report_markdown_structure():
    """Verify document formatting follows proper markdown heading hierarchy."""
    lines = REPORT_PATH.read_text(encoding="utf-8").splitlines()
    h1_count = sum(1 for line in lines if line.startswith("# "))
    h2_count = sum(1 for line in lines if line.startswith("## "))
    assert h1_count >= 1, "Report must have at least one H1 header"
    assert h2_count >= 5, "Report must have at least five structured H2 sections"
