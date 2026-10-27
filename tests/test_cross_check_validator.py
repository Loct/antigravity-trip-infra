#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pytest>=8.0.0",
#     "httpx>=0.27.0",
#     "rich>=13.0.0",
#     "anthropic>=0.40.0",
#     "openai>=1.0.0",
# ]
# ///
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts dir is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from cross_check_validator import (
    extract_section_content,
    extract_verdict,
    synthesize_cross_check_report,
    run_cross_check,
)
import claude_validator
import deepseek_validator


def test_extract_verdict():
    sample_text = """
# 📋 Trip Audit Report: Rome
## 🌟 Executive Summary
All good.
## ✅ Final Verdict
GOOD WITH MINOR TWEAKS
"""
    assert extract_verdict(sample_text) == "GOOD WITH MINOR TWEAKS"

    sample_critical = """
## Final Verdict: [CRITICAL ERRORS DETECTED]
"""
    assert extract_verdict(sample_critical) == "CRITICAL ERRORS DETECTED"


def test_extract_section_content():
    sample_text = """
## 🛑 Critical Issues (Must Fix)
- Day 3 has overlapping flight and dinner reservations.
- Night 5 has no hotel booked.

## ⚠️ Warnings & Logistical Friction
- Long walk on Day 2.
"""
    critical = extract_section_content(sample_text, "Critical Issues")
    assert "- Day 3 has overlapping flight" in critical
    assert "Night 5 has no hotel" in critical
    assert "Long walk" not in critical


def test_synthesize_cross_check_report():
    ds_report = """# DeepSeek Report
## 🛑 Critical Issues
- DeepSeek caught missing hotel on Night 4.

## ⚠️ Warnings
- Heavy schedule on Day 1.

## 💡 Concrete Proposed Fixes
- Book hotel in Florence for Night 4.

## ✅ Final Verdict
NEEDS RESTRUCTURING
"""

    claude_report = """# Claude Report
## 🛑 Critical Issues
- Claude caught missing hotel on Night 4.
- Vatican Museum closed on Sunday.

## ⚠️ Warnings
- Transit buffer between airport and hotel too tight.

## 💡 Concrete Proposed Fixes
- Reschedule Vatican to Tuesday.

## ✅ Final Verdict
NEEDS RESTRUCTURING
"""

    report = synthesize_cross_check_report(
        trip_target="test-trip-id",
        trip_title="Italy Grand Tour",
        ds_report=ds_report,
        claude_report=claude_report,
        ds_model="deepseek-reasoner",
        claude_model="claude-3-7-sonnet-20250219",
    )

    assert "Italy Grand Tour" in report
    assert "High Model Agreement" in report
    assert "NEEDS RESTRUCTURING" in report
    assert "DeepSeek caught missing hotel" in report
    assert "Claude caught missing hotel" in report
    assert "Vatican Museum closed on Sunday" in report


@patch("cross_check_validator.claude_validator.fetch_trip_data")
@patch("cross_check_validator.deepseek_validator.run_validation")
@patch("cross_check_validator.claude_validator.run_claude_validation")
def test_run_cross_check_mocked(mock_claude_run, mock_ds_run, mock_fetch):
    mock_fetch.return_value = ({"title": "Sample Trip", "tripPlan": {"title": "Sample Trip"}}, "Markdown data")
    mock_ds_run.return_value = ("# DS Report\n## Final Verdict\nEXCELLENT", "DS thought")
    mock_claude_run.return_value = ("# Claude Report\n## Final Verdict\nEXCELLENT", "Claude thought")

    claude_cfg = claude_validator.ClaudeProviderConfig(api_key="sk-ant-test")
    ds_cfg = deepseek_validator.ProviderConfig(api_key="sk-or-test")

    cross_report, claude_rep, ds_rep = run_cross_check(
        trip_target="sample-target",
        claude_cfg=claude_cfg,
        ds_cfg=ds_cfg,
        stream_progress=False,
    )

    assert "EXCELLENT" in cross_report
    assert "High Model Agreement" in cross_report
    assert claude_rep == "# Claude Report\n## Final Verdict\nEXCELLENT"
    assert ds_rep == "# DS Report\n## Final Verdict\nEXCELLENT"
