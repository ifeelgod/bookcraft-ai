"""
BookCraft AI - Standalone Test Suite Runner & Verification Engine
Executes unit tests and 4-tier E2E suites with comprehensive per-tier statistics, formatted reporting, and exit code semantics.

Usage:
    python tests/run_all_tests.py
    python tests/run_all_tests.py --tier 1
    python tests/run_all_tests.py --tier 2
    python tests/run_all_tests.py --tier 3
    python tests/run_all_tests.py --tier 4
    python tests/run_all_tests.py --unit
"""
from __future__ import annotations
import argparse
import asyncio
import importlib
import inspect
import os
from pathlib import Path
import sys
import time
import traceback

# Add project root and backend to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"
TESTS_DIR = PROJECT_ROOT / "tests"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ANSI Color formatting
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class TestResult:
    def __init__(self, name: str, passed: bool, duration_sec: float, error: str = ""):
        self.name = name
        self.passed = passed
        self.duration_sec = duration_sec
        self.error = error


class TierSummary:
    def __init__(self, tier_name: str):
        self.tier_name = tier_name
        self.results: list[TestResult] = []

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def duration_sec(self) -> float:
        return sum(r.duration_sec for r in self.results)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100.0) if self.total > 0 else 0.0


async def run_single_test(test_func, fixtures: dict) -> TestResult:
    """Execute a single test function, injecting matching fixtures and handling async."""
    func_name = test_func.__name__
    sig = inspect.signature(test_func)
    kwargs = {}
    db_cleanup_callbacks = []

    for param in sig.parameters.values():
        if param.name in fixtures:
            val = fixtures[param.name]
            if callable(val) and not isinstance(val, (type, Path, str, int, dict)):
                try:
                    val = val()
                except Exception:
                    pass
            kwargs[param.name] = val
        elif param.name in ("db_session", "e2e_db_session"):
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
            from app.db.base import Base
            engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
            session = session_factory()
            kwargs[param.name] = session
            async def _cleanup(s=session, e=engine):
                await s.close()
                async with e.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
                await e.dispose()
            db_cleanup_callbacks.append(_cleanup)

    start_time = time.perf_counter()
    try:
        if asyncio.iscoroutinefunction(test_func):
            await test_func(**kwargs)
        else:
            test_func(**kwargs)
        elapsed = time.perf_counter() - start_time
        for cb in db_cleanup_callbacks:
            await cb()
        return TestResult(name=func_name, passed=True, duration_sec=elapsed)
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        tb = traceback.format_exc()
        for cb in db_cleanup_callbacks:
            try:
                await cb()
            except Exception:
                pass
        return TestResult(name=func_name, passed=False, duration_sec=elapsed, error=tb)


def get_session_fixtures(tmp_dir: Path) -> dict:
    """Construct standard fixtures passed to test functions."""
    import tests.conftest as conftest

    # Load sample AST from JSON
    ast_json_path = conftest.FIXTURES_DIR / "sample_multi_chapter.json"
    import json
    with open(ast_json_path, "r", encoding="utf-8") as f:
        ast_dict = json.load(f)

    from app.models.document_ast import DocumentAST, BookMetadata, Genre, TrimSize, Chapter, ParagraphBlock

    sample_ast = DocumentAST(**ast_dict)

    # 15 page AST
    fifteen_page_ast = DocumentAST(
        metadata=BookMetadata(
            title="Chronicles of Aethelgard: The Fifteen Seals",
            author="Master Chronicler Brandon",
            genre=Genre.fiction,
            trim_size=TrimSize.medium,
        ),
        chapters=[
            Chapter(
                chapter_number=i,
                title=f"Seal {i}",
                content=[ParagraphBlock(type="paragraph", text=f"Chronicle text {i}")],
            )
            for i in range(1, 16)
        ],
    )

    # 25 page AST
    twenty_five_page_ast = DocumentAST(
        metadata=BookMetadata(
            title="The Encyclopedia of Astronavigation",
            author="Dr. Victoria Chen",
            genre=Genre.technical,
            trim_size=TrimSize.medium,
        ),
        chapters=[
            Chapter(
                chapter_number=i,
                title=f"Sector Module {i}",
                content=[ParagraphBlock(type="paragraph", text=f"Deep space telemetry {i}")],
            )
            for i in range(1, 26)
        ],
    )

    # Unicode AST
    unicode_ast = DocumentAST(
        metadata=BookMetadata(
            title="✨ Le Guide Épique 2026: 宇宙 & Приключения 🚀",
            author="José Müller & 桜井 健太",
            genre=Genre.non_fiction,
            trim_size=TrimSize.large,
        ),
        chapters=[
            Chapter(
                chapter_number=1,
                title="L'Aventure Multilingue — 日本語と宇宙",
                content=[ParagraphBlock(type="paragraph", text="Dans un univers infini. 🌟 🪐 🛰️")],
            )
        ],
    )

    # Minimal AST
    minimal_ast = DocumentAST(
        metadata=BookMetadata(title="Min", author="A", genre=Genre.fiction, trim_size=TrimSize.medium),
        chapters=[Chapter(chapter_number=1, title="C1", content=[ParagraphBlock(type="paragraph", text="P")])],
    )

    return {
        "project_root": PROJECT_ROOT,
        "fixtures_dir": conftest.FIXTURES_DIR,
        "sample_ast_data": ast_dict,
        "sample_ast": sample_ast,
        "minimal_ast": minimal_ast,
        "fifteen_page_ast": fifteen_page_ast,
        "twenty_five_page_ast": twenty_five_page_ast,
        "unicode_ast": unicode_ast,
        "tmp_path": tmp_dir,
    }


async def run_test_module(module_name: str, tier_title: str, fixtures: dict) -> TierSummary:
    """Import and run all test_* functions in a module."""
    summary = TierSummary(tier_title)
    try:
        mod = importlib.import_module(module_name)
    except Exception as exc:
        print(f"{RED}[ERROR]{RESET} Failed to import {module_name}: {exc}")
        traceback.print_exc()
        summary.results.append(TestResult(name=f"import_{module_name}", passed=False, duration_sec=0.0, error=str(exc)))
        return summary

    # Collect test functions
    test_funcs = []
    for attr_name in dir(mod):
        if attr_name.startswith("test_"):
            attr = getattr(mod, attr_name)
            if callable(attr):
                test_funcs.append(attr)

    print(f"\n{BOLD}{CYAN}▶ Running {tier_title} ({len(test_funcs)} test cases){RESET}")

    for func in test_funcs:
        res = await run_single_test(func, fixtures)
        summary.results.append(res)
        if res.passed:
            print(f"  {GREEN}✔ PASS{RESET} {func.__name__} ({res.duration_sec * 1000:.1f}ms)")
        else:
            print(f"  {RED}✘ FAIL{RESET} {func.__name__} ({res.duration_sec * 1000:.1f}ms)")
            print(f"{RED}{res.error}{RESET}")

    return summary


def print_overall_summary(summaries: list[TierSummary], total_duration: float) -> int:
    """Print tabular summary of results across all tiers and return status code."""
    print("\n" + "=" * 80)
    print(f"{BOLD}BOOKCRAFT AI — TEST SUITE EXECUTION SUMMARY{RESET}")
    print("=" * 80)
    print(f"{'Tier / Test Suite':<40} | {'Total':<6} | {'Passed':<6} | {'Failed':<6} | {'Pass %':<8} | {'Time'}")
    print("-" * 80)

    total_tests = 0
    total_passed = 0
    total_failed = 0

    for s in summaries:
        total_tests += s.total
        total_passed += s.passed
        total_failed += s.failed

        pass_color = GREEN if s.failed == 0 else RED
        print(
            f"{s.tier_name:<40} | {s.total:<6} | {GREEN}{s.passed:<6}{RESET} | "
            f"{pass_color}{s.failed:<6}{RESET} | {pass_color}{s.pass_rate:>6.1f}%{RESET} | {s.duration_sec:.2f}s"
        )

    print("-" * 80)
    overall_rate = (total_passed / total_tests * 100.0) if total_tests > 0 else 0.0
    overall_color = GREEN if total_failed == 0 else RED
    print(
        f"{BOLD}{'TOTAL COMPOSITE':<40} | {total_tests:<6} | {GREEN}{total_passed:<6}{RESET} | "
        f"{overall_color}{total_failed:<6}{RESET} | {overall_color}{overall_rate:>6.1f}%{RESET} | {total_duration:.2f}s{RESET}"
    )
    print("=" * 80)

    if total_failed == 0:
        print(f"\n{GREEN}{BOLD}🎉 ALL {total_tests} TESTS PASSED CLEANLY (100.0% SUCCESS RATE)!{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}❌ {total_failed} TESTS FAILED! Please inspect errors above.{RESET}\n")
        return 1


async def main_async():
    parser = argparse.ArgumentParser(description="BookCraft AI Test Suite Runner")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Run specific test tier (1, 2, 3, or 4)")
    parser.add_argument("--unit", action="store_true", help="Run unit test suites only")
    args = parser.parse_args()

    tmp_dir = PROJECT_ROOT / "outputs" / "test_run_artifacts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fixtures = get_session_fixtures(tmp_dir)

    test_plan = []

    if args.unit or (not args.tier and not args.unit):
        test_plan.extend([
            ("tests.unit.test_compilers", "Unit: Multi-format Compilers (DOCX, MD, EPUB, PDF)"),
            ("tests.unit.test_lead_storage", "Unit: Lead Storage & Email Sync Models"),
            ("tests.unit.test_restriction_engine", "Unit: 15-Page Restriction Engine"),
            ("tests.unit.test_payment_service", "Unit: Payment & JWT Token Service"),
            ("tests.unit.test_reports_structure", "Unit: Architectural & Pricing Reports"),
        ])

    if args.tier == 1 or (not args.tier and not args.unit):
        test_plan.append(("tests.e2e.test_tier1_features", "Tier 1: Feature Coverage (12 Features)"))

    if args.tier == 2 or (not args.tier and not args.unit):
        test_plan.append(("tests.e2e.test_tier2_boundaries", "Tier 2: Boundary & Corner Cases (12 Features)"))

    if args.tier == 3 or (not args.tier and not args.unit):
        test_plan.append(("tests.e2e.test_tier3_combinations", "Tier 3: Cross-Feature Workflows & Interactions"))

    if args.tier == 4 or (not args.tier and not args.unit):
        test_plan.append(("tests.e2e.test_tier4_real_world", "Tier 4: Real-World Author Scenarios"))

    start_all = time.perf_counter()
    summaries = []

    for mod_name, tier_title in test_plan:
        summary = await run_test_module(mod_name, tier_title, fixtures)
        summaries.append(summary)

    total_time = time.perf_counter() - start_all
    exit_code = print_overall_summary(summaries, total_time)
    sys.exit(exit_code)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
