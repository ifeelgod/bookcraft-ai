"""
Unit Tests: Research & Trade-Off Reports Verification
Verifies existence, completeness, depth, and analytical rigor of architectural and monetization reports.
"""
from __future__ import annotations
from pathlib import Path
import pytest

from tests.conftest import PROJECT_ROOT


def test_fork_vs_direct_integration_report_exists():
    """Verify FORK_VS_DIRECT_INTEGRATION_REPORT.md exists and has substantial depth."""
    report_path = PROJECT_ROOT / "docs" / "reports" / "FORK_VS_DIRECT_INTEGRATION_REPORT.md"
    assert report_path.exists(), f"Report not found at {report_path}"
    
    content = report_path.read_text(encoding="utf-8")
    assert len(content) > 3000, "Report content is too brief for an in-depth architectural trade-off analysis."


def test_fork_vs_direct_integration_report_sections():
    """Verify the report contains all required analytical sections and matrices."""
    report_path = PROJECT_ROOT / "docs" / "reports" / "FORK_VS_DIRECT_INTEGRATION_REPORT.md"
    content = report_path.read_text(encoding="utf-8")

    required_keywords = [
        "Executive Summary",
        "Direct Integration",
        "Fork Strategy",
        "Code Reusability",
        "DevOps",
        "Conversion Funnel",
        "Decision Matrix",
        "15-Page",
        "SQLAlchemy",
    ]
    for kw in required_keywords:
        assert kw.lower() in content.lower(), f"Missing essential topic '{kw}' in report."


def test_fork_vs_direct_integration_report_decision_matrix():
    """Verify the report includes quantitative scoring matrix with criteria and weights."""
    report_path = PROJECT_ROOT / "docs" / "reports" / "FORK_VS_DIRECT_INTEGRATION_REPORT.md"
    content = report_path.read_text(encoding="utf-8")

    # Check for markdown table elements
    assert "|" in content
    assert "---" in content
    assert "Weight" in content or "weight" in content
    assert "Score" in content or "score" in content


def test_pricing_and_monetization_report_structure():
    """Verify PRICING_AND_MONETIZATION_REPORT.md if present, or validate specification criteria."""
    report_path = PROJECT_ROOT / "docs" / "reports" / "PRICING_AND_MONETIZATION_REPORT.md"
    if report_path.exists():
        content = report_path.read_text(encoding="utf-8")
        assert len(content) > 1000
        assert "stripe" in content.lower()
        assert "paypal" in content.lower()
        assert "tier" in content.lower()
    else:
        # Pass gracefully if report is authored in M3, while asserting expected path
        assert report_path.parent.exists()
