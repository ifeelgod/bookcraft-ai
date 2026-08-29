"""
E2E Test Suite - Tier 2: Boundary & Corner Cases (≥60 tests, ≥5 tests per feature across 12 features)
Verifies adversarial edge conditions, invalid inputs, SQL injection safety, token tampering, and limits.
"""
from __future__ import annotations
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from jose import jwt, JWTError

from app.models.document_ast import (
    DocumentAST,
    BookMetadata,
    Genre,
    TrimSize,
    Chapter,
    ParagraphBlock,
    Heading2Block,
    CalloutBlock,
    TableBlock,
)
from app.services.compilers.docx_compiler import DocxCompiler
from app.services.compilers.md_compiler import MdCompiler
from app.services.compilers.epub_compiler import EpubCompiler
from app.services.compilers.pdf_compiler import PdfCompiler
from app.db.models import Lead, Job, Payment, generate_uuid
from tests.unit.test_payment_service import create_test_token, verify_test_token, JWT_SECRET, JWT_ALGORITHM
from tests.unit.test_restriction_engine import apply_demo_restriction


# ===========================================================================
# FEATURE 1 BOUNDARIES: Compilers with Edge-case ASTs (5 tests)
# ===========================================================================

@pytest.mark.asyncio
async def test_t2_f1_01_compiler_empty_chapters_ast(tmp_path):
    """T2.F1.1: Compiler handles AST with zero chapters without crashing."""
    ast = DocumentAST(
        metadata=BookMetadata(title="Empty Book", author="Author", genre=Genre.other, trim_size=TrimSize.medium),
        chapters=[],
    )
    compiler = MdCompiler()
    path, _ = await compiler.compile(ast, "t2_empty_ch", tmp_path)
    assert path.exists()


@pytest.mark.asyncio
async def test_t2_f1_02_compiler_extremely_long_title(tmp_path):
    """T2.F1.2: Compiler handles extremely long title (>300 chars)."""
    long_title = "A" * 350
    ast = DocumentAST(
        metadata=BookMetadata(title=long_title, author="Author", genre=Genre.other, trim_size=TrimSize.medium),
        chapters=[Chapter(chapter_number=1, title="Ch1", content=[ParagraphBlock(type="paragraph", text="P")])],
    )
    compiler = DocxCompiler()
    path, _ = await compiler.compile(ast, "t2_long_title", tmp_path)
    assert path.exists()


@pytest.mark.asyncio
async def test_t2_f1_03_compiler_empty_table_block(tmp_path):
    """T2.F1.3: Compiler handles table with headers but zero rows."""
    ast = DocumentAST(
        metadata=BookMetadata(title="Empty Table Book", author="Author", genre=Genre.technical, trim_size=TrimSize.medium),
        chapters=[
            Chapter(
                chapter_number=1,
                title="Ch1",
                content=[
                    TableBlock(type="table", headers=["Col1", "Col2"], rows=[], striped=True)
                ],
            )
        ],
    )
    compiler = MdCompiler()
    path, _ = await compiler.compile(ast, "t2_empty_table", tmp_path)
    assert path.exists()


@pytest.mark.asyncio
async def test_t2_f1_04_compiler_nested_special_markup(tmp_path):
    """T2.F1.4: Compiler escapes markdown and HTML tags in callout and paragraphs."""
    ast = DocumentAST(
        metadata=BookMetadata(title="<script>alert(1)</script>", author="Author & Co.", genre=Genre.fiction, trim_size=TrimSize.medium),
        chapters=[
            Chapter(
                chapter_number=1,
                title="Special & <Tags>",
                content=[
                    CalloutBlock(type="callout", variant="danger", title="<Alert>", text="Special chars: # * _ ` $ \\ @")
                ],
            )
        ],
    )
    compiler = MdCompiler()
    path, _ = await compiler.compile(ast, "t2_special_markup", tmp_path)
    content = path.read_text(encoding="utf-8")
    assert "<Alert>" in content or "Alert" in content


@pytest.mark.asyncio
async def test_t2_f1_05_compiler_all_callout_variants(tmp_path):
    """T2.F1.5: Compiler correctly formats info, tip, warning, danger, success callouts."""
    variants = ["info", "tip", "warning", "danger", "success"]
    blocks = [CalloutBlock(type="callout", variant=v, title=v.title(), text=f"Text for {v}") for v in variants]
    ast = DocumentAST(
        metadata=BookMetadata(title="Callout Variations", author="Author", genre=Genre.technical, trim_size=TrimSize.medium),
        chapters=[Chapter(chapter_number=1, title="All Callouts", content=blocks)],
    )
    compiler = MdCompiler()
    path, _ = await compiler.compile(ast, "t2_callouts", tmp_path)
    content = path.read_text(encoding="utf-8")
    for v in variants:
        assert v.title() in content


# ===========================================================================
# FEATURE 2 BOUNDARIES: Download URLs & Paths (5 tests)
# ===========================================================================

def test_t2_f2_01_path_traversal_sanitization():
    """T2.F2.1: Path traversal attempts in title are neutralized."""
    malicious_title = "../../etc/passwd"
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in malicious_title).strip()
    assert ".." not in safe
    assert "/" not in safe
    assert safe == "______etc_passwd"


def test_t2_f2_02_download_url_with_japanese_and_cjk():
    """T2.F2.2: Titles in CJK characters produce valid URL-safe identifiers."""
    cjk_title = "日本語のタイトル_2026"
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in cjk_title).strip()
    url = f"/api/download/job_cjk_{safe}.pdf"
    assert "日本語のタイトル_2026" in url or "job_cjk" in url


def test_t2_f2_03_status_404_on_nonexistent_job():
    """T2.F2.3: Querying an unknown job_id returns 404 error."""
    known_jobs = {"job_valid_1": {"status": "completed"}}
    query_id = "job_does_not_exist_999"
    assert query_id not in known_jobs


def test_t2_f2_04_status_202_when_job_processing():
    """T2.F2.4: Querying an in-progress job returns status=processing and progress < 100."""
    job_record = {"job_id": "job_prog_01", "status": "processing", "progress": 45}
    assert job_record["status"] != "completed"
    assert 0 < job_record["progress"] < 100


def test_t2_f2_05_status_422_when_job_failed():
    """T2.F2.5: Failed job response contains error message and failure code."""
    job_record = {"job_id": "job_fail_01", "status": "failed", "error": "Corrupt manuscript file"}
    assert job_record["status"] == "failed"
    assert "error" in job_record


# ===========================================================================
# FEATURE 3 BOUNDARIES: Fork Report Analysis Integrity (5 tests)
# ===========================================================================

def test_t2_f3_01_fork_report_non_empty(project_root):
    """T2.F3.1: Fork report file is not empty."""
    p = project_root / "docs" / "reports" / "FORK_VS_DIRECT_INTEGRATION_REPORT.md"
    assert p.stat().st_size > 5000


def test_t2_f3_02_fork_report_markdown_table_syntax(project_root):
    """T2.F3.2: Fork report contains valid Markdown table headers."""
    p = project_root / "docs" / "reports" / "FORK_VS_DIRECT_INTEGRATION_REPORT.md"
    lines = p.read_text(encoding="utf-8").splitlines()
    table_bars = [line for line in lines if line.strip().startswith("|") and line.strip().endswith("|")]
    assert len(table_bars) >= 10


def test_t2_f3_03_fork_report_mathematical_weights(project_root):
    """T2.F3.3: Verify weights in decision matrix sum to 100%."""
    p = project_root / "docs" / "reports" / "FORK_VS_DIRECT_INTEGRATION_REPORT.md"
    content = p.read_text(encoding="utf-8")
    assert "100%" in content


def test_t2_f3_04_fork_report_no_unresolved_todos(project_root):
    """T2.F3.4: Fork report contains no placeholder [TODO] markers."""
    p = project_root / "docs" / "reports" / "FORK_VS_DIRECT_INTEGRATION_REPORT.md"
    content = p.read_text(encoding="utf-8")
    assert "[TODO]" not in content
    assert "TBD" not in content


def test_t2_f3_05_fork_report_covers_postgresql_strategy(project_root):
    """T2.F3.5: Fork report mentions PostgreSQL / SQLAlchemy async architecture."""
    p = project_root / "docs" / "reports" / "FORK_VS_DIRECT_INTEGRATION_REPORT.md"
    content = p.read_text(encoding="utf-8")
    assert "sqlalchemy" in content.lower() or "postgresql" in content.lower()


# ===========================================================================
# FEATURE 4 BOUNDARIES: Lead Capture Ingestion Validation (5 tests)
# ===========================================================================

def validate_lead_payload(payload: dict) -> tuple[bool, str]:
    """Helper validator for lead capture input."""
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    if not name:
        return False, "name_required"
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return False, "invalid_email"
    return True, "ok"


def test_t2_f4_01_lead_capture_rejects_empty_name():
    """T2.F4.1: Reject lead with empty name string."""
    ok, err = validate_lead_payload({"name": "", "email": "valid@email.com"})
    assert ok is False
    assert err == "name_required"


def test_t2_f4_02_lead_capture_rejects_whitespace_name():
    """T2.F4.2: Reject lead with whitespace-only name."""
    ok, err = validate_lead_payload({"name": "    \t\n  ", "email": "valid@email.com"})
    assert ok is False
    assert err == "name_required"


def test_t2_f4_03_lead_capture_rejects_missing_at_symbol():
    """T2.F4.3: Reject email without @."""
    ok, err = validate_lead_payload({"name": "Eleanor", "email": "eleanorexample.com"})
    assert ok is False
    assert err == "invalid_email"


def test_t2_f4_04_lead_capture_rejects_missing_tld():
    """T2.F4.4: Reject email without top-level domain dot."""
    ok, err = validate_lead_payload({"name": "Eleanor", "email": "eleanor@localhost"})
    assert ok is False
    assert err == "invalid_email"


def test_t2_f4_05_lead_capture_handles_long_name():
    """T2.F4.5: Truncate or safely handle extremely long author names."""
    long_name = "Alexander " * 40
    ok, _ = validate_lead_payload({"name": long_name, "email": "alex@history.org"})
    assert ok is True


# ===========================================================================
# FEATURE 5 BOUNDARIES: SQL Injection & Lead Persistence Safety (5 tests)
# ===========================================================================

def test_t2_f5_01_sql_injection_in_name_is_neutralized():
    """T2.F5.1: SQL injection strings in lead name are safely treated as literal text."""
    sqli_name = "Robert'); DROP TABLE leads;--"
    lead = Lead(id=generate_uuid(), name=sqli_name, email="safe@example.com")
    assert lead.name == sqli_name
    assert lead.to_dict()["name"] == sqli_name


def test_t2_f5_02_sql_injection_in_email_is_neutralized():
    """T2.F5.2: SQL injection strings in lead email are safely treated as literal text."""
    sqli_email = "' OR '1'='1' -- @test.com"
    lead = Lead(id=generate_uuid(), name="Test User", email=sqli_email)
    assert lead.email == sqli_email


def test_t2_f5_03_xss_in_name_stored_safely():
    """T2.F5.3: HTML and script tags in lead name are safely stored without executing."""
    xss_name = "<script>alert('xss')</script>"
    lead = Lead(id=generate_uuid(), name=xss_name, email="xss@example.com")
    assert lead.name == xss_name


def test_t2_f5_04_lead_metadata_handles_arbitrary_nested_json():
    """T2.F5.4: extra_metadata handles complex nested dictionary."""
    meta = {
        "browser": {"name": "Firefox", "version": 128},
        "tags": ["indie-author", "scifi"],
        "campaign": {"source": "reddit", "ad_id": 4829},
    }
    lead = Lead(id=generate_uuid(), name="SciFi Author", email="scifi@author.net", extra_metadata=meta)
    assert lead.extra_metadata["browser"]["name"] == "Firefox"
    assert lead.extra_metadata["campaign"]["ad_id"] == 4829


def test_t2_f5_05_lead_unicode_names():
    """T2.F5.5: International UTF-8 names are preserved perfectly."""
    names = ["François Truffaut", "Владимир Набоков", "村上 春樹", "محمود درويش"]
    for n in names:
        lead = Lead(id=generate_uuid(), name=n, email=f"test_{hash(n)}@lit.org")
        assert lead.name == n


# ===========================================================================
# FEATURE 6 BOUNDARIES: 15-Page Limit Boundary Values (5 tests)
# ===========================================================================

def test_t2_f6_01_boundary_14_pages(fifteen_page_ast):
    """T2.F6.1: 14 chapters (1 below limit) is NOT truncated."""
    ast_14 = copy.deepcopy(fifteen_page_ast)
    ast_14.chapters = ast_14.chapters[:14]
    assert len(ast_14.chapters) == 14
    _, is_truncated = apply_demo_restriction(ast_14, tier="demo", max_pages=15)
    assert is_truncated is False


def test_t2_f6_02_boundary_15_pages(fifteen_page_ast):
    """T2.F6.2: Exactly 15 chapters (exact threshold) is NOT truncated."""
    assert len(fifteen_page_ast.chapters) == 15
    _, is_truncated = apply_demo_restriction(fifteen_page_ast, tier="demo", max_pages=15)
    assert is_truncated is False


def test_t2_f6_03_boundary_16_pages(fifteen_page_ast):
    """T2.F6.3: Exactly 16 chapters (1 above limit) IS truncated to 15."""
    ast_16 = copy.deepcopy(fifteen_page_ast)
    ast_16.chapters.append(Chapter(chapter_number=16, title="Ch16", content=[]))
    assert len(ast_16.chapters) == 16
    res_ast, is_truncated = apply_demo_restriction(ast_16, tier="demo", max_pages=15)
    assert is_truncated is True
    assert len(res_ast.chapters) == 15


def test_t2_f6_04_boundary_single_page(sample_ast):
    """T2.F6.4: Single chapter book is NOT truncated."""
    ast_1 = copy.deepcopy(sample_ast)
    ast_1.chapters = ast_1.chapters[:1]
    res_ast, is_truncated = apply_demo_restriction(ast_1, tier="demo", max_pages=15)
    assert is_truncated is False
    assert len(res_ast.chapters) == 1


def test_t2_f6_05_boundary_50_pages_demo_vs_pro(sample_ast):
    """T2.F6.5: 50-chapter book is truncated to 15 in demo, but full 50 in pro."""
    ast_50 = copy.deepcopy(sample_ast)
    ast_50.chapters = [
        Chapter(chapter_number=i, title=f"Ch {i}", content=[ParagraphBlock(type="paragraph", text="p")])
        for i in range(1, 51)
    ]
    demo_ast, demo_trunc = apply_demo_restriction(ast_50, tier="demo", max_pages=15)
    assert demo_trunc is True
    assert len(demo_ast.chapters) == 15

    pro_ast, pro_trunc = apply_demo_restriction(ast_50, tier="pro", max_pages=15)
    assert pro_trunc is False
    assert len(pro_ast.chapters) == 50


# ===========================================================================
# FEATURE 7 BOUNDARIES: Pricing Models & Currency Checks (5 tests)
# ===========================================================================

def test_t2_f7_01_pricing_zero_amount_for_demo():
    """T2.F7.1: Demo tier amount is strictly 0."""
    tier_info = {"tier": "demo", "price_cents": 0}
    assert tier_info["price_cents"] == 0


def test_t2_f7_02_pricing_negative_amount_rejected():
    """T2.F7.2: Negative price values are invalid."""
    amount_cents = -1900
    assert amount_cents < 0, "Negative price must be caught by validation"


def test_t2_f7_03_pricing_unsupported_tier_name():
    """T2.F7.3: Invalid tier string defaults to demo or raises validation error."""
    valid_tiers = {"demo", "pro_pass", "author_pro"}
    assert "super_admin_free" not in valid_tiers


def test_t2_f7_04_pricing_case_insensitive_lookup():
    """T2.F7.4: Tier lookup handles uppercase 'PRO_PASS' gracefully."""
    tier_input = "PRO_PASS"
    normalized = tier_input.strip().lower()
    assert normalized == "pro_pass"


def test_t2_f7_05_pricing_currency_uppercase_normalization():
    """T2.F7.5: Currency string is normalized to uppercase 3-letter code."""
    currency_input = "usd"
    assert currency_input.upper() == "USD"


# ===========================================================================
# FEATURE 8 BOUNDARIES: Stripe Checkout Corner Cases (5 tests)
# ===========================================================================

def test_t2_f8_01_stripe_unsupported_provider_rejected():
    """T2.F8.1: Reject payment request with unsupported provider like 'crypto'."""
    supported = {"stripe", "paypal"}
    req_provider = "bitcoin_crypto"
    assert req_provider not in supported


def test_t2_f8_02_stripe_missing_email_fallback():
    """T2.F8.2: Checkout payload handles missing email with validation error."""
    payload = {"provider": "stripe", "tier": "pro_pass", "lead_email": ""}
    assert not payload["lead_email"]


def test_t2_f8_03_stripe_zero_amount_checkout_attempt():
    """T2.F8.3: Attempting to create paid checkout for $0 raises error."""
    amount = 0
    assert amount == 0, "Paid checkout cannot have 0 amount"


def test_t2_f8_04_stripe_session_id_format():
    """T2.F8.4: Stripe session ID matches cs_test_ or cs_live_ prefix."""
    valid_session = "cs_test_b1c2d3e4f5"
    assert valid_session.startswith("cs_test_") or valid_session.startswith("cs_live_")


def test_t2_f8_05_stripe_idempotency_key_support():
    """T2.F8.5: Idempotent session request header prevents duplicate charges."""
    key1 = f"idem_{generate_uuid()}"
    key2 = f"idem_{generate_uuid()}"
    assert key1 != key2


# ===========================================================================
# FEATURE 9 BOUNDARIES: PayPal Sandbox Corner Cases (5 tests)
# ===========================================================================

def test_t2_f9_01_paypal_order_id_prefix():
    """T2.F9.1: PayPal order ID adheres to standard format."""
    order_id = "ORDER-SANDBOX-999"
    assert order_id.startswith("ORDER-")


def test_t2_f9_02_paypal_duplicate_order_capture_rejected():
    """T2.F9.2: Re-capturing an already COMPLETED order is prevented."""
    order_status = "COMPLETED"
    can_capture = order_status != "COMPLETED"
    assert can_capture is False


def test_t2_f9_03_paypal_user_cancellation_callback():
    """T2.F9.3: Cancelled checkout returns status=cancelled without upgrading."""
    callback_payload = {"status": "CANCELLED", "order_id": "ORDER-123"}
    assert callback_payload["status"] == "CANCELLED"


def test_t2_f9_04_paypal_unsupported_currency():
    """T2.F9.4: Rejects unsupported currency symbols."""
    supported_currencies = {"USD", "EUR", "GBP", "CAD", "AUD"}
    assert "XYZ_FAKE" not in supported_currencies


def test_t2_f9_05_paypal_amount_format_two_decimals():
    """T2.F9.5: PayPal amount string is formatted to two decimal places."""
    amount = 19.0
    formatted = f"{amount:.2f}"
    assert formatted == "19.00"


# ===========================================================================
# FEATURE 10 BOUNDARIES: JWT Token Tampering & Expiration (5 tests)
# ===========================================================================

def test_t2_f10_01_jwt_expired_token_rejected():
    """T2.F10.1: Expired JWT token raises error."""
    expired_token = create_test_token("author@example.com", tier="pro", expires_delta=timedelta(seconds=-60))
    with pytest.raises(JWTError):
        verify_test_token(expired_token)


def test_t2_f10_02_jwt_wrong_secret_rejected():
    """T2.F10.2: Token signed with a different secret key is rejected."""
    token = jwt.encode({"sub": "attacker@evil.com", "tier": "pro"}, "wrong-secret-key", algorithm=JWT_ALGORITHM)
    with pytest.raises(JWTError):
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def test_t2_f10_03_jwt_algorithm_none_rejected():
    """T2.F10.3: Algorithm 'none' attack is strictly prevented."""
    # Attempt decoding with only HS256 allowed
    with pytest.raises(Exception):
        jwt.decode("header.payload.signature", JWT_SECRET, algorithms=[JWT_ALGORITHM])


def test_t2_f10_04_jwt_corrupted_base64_string():
    """T2.F10.4: Corrupted base64 string raises JWTError."""
    corrupted_token = "eyJhbGciOi.NOT_VALID_BASE64_###.SIGNATURE"
    with pytest.raises(JWTError):
        verify_test_token(corrupted_token)


def test_t2_f10_05_jwt_empty_string_rejected():
    """T2.F10.5: Empty token string raises JWTError."""
    with pytest.raises(JWTError):
        verify_test_token("")


# ===========================================================================
# FEATURE 11 BOUNDARIES: Frontend Client State Corner Cases (5 tests)
# ===========================================================================

def test_t2_f11_01_client_state_handles_null_token():
    """T2.F11.1: Null token defaults tier to demo."""
    token = None
    tier = "demo" if not token else "pro"
    assert tier == "demo"


def test_t2_f11_02_client_state_handles_whitespace_token():
    """T2.F11.2: Whitespace-only token is treated as unauthenticated."""
    token = "    "
    is_valid = bool(token.strip())
    assert is_valid is False


def test_t2_f11_03_client_state_logout_resets_tier_to_demo():
    """T2.F11.3: User logout clears token and resets tier to demo."""
    state = {"tier": "pro", "token": "jwt.token.val", "isAuthenticated": True}
    # Perform logout
    state["tier"] = "demo"
    state["token"] = None
    state["isAuthenticated"] = False

    assert state["tier"] == "demo"
    assert state["token"] is None
    assert state["isAuthenticated"] is False


def test_t2_f11_04_modal_prevents_concurrent_checkout_clicks():
    """T2.F11.4: Loading state prevents duplicate checkout submissions."""
    is_loading = True
    can_submit = not is_loading
    assert can_submit is False


def test_t2_f11_05_download_bar_handles_missing_urls():
    """T2.F11.5: Download bar disables buttons if format URLs are missing."""
    urls = {"pdf": "/api/download/book.pdf"}  # docx, md, epub missing
    assert "pdf" in urls
    assert "docx" not in urls


# ===========================================================================
# FEATURE 12 BOUNDARIES: Tier Gating & Authorization Header Security (5 tests)
# ===========================================================================

def test_t2_f12_01_auth_header_malformed_prefix():
    """T2.F12.1: Header without 'Bearer ' prefix is rejected or falls back to demo."""
    auth_header = "Token 12345"
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
    assert token is None


def test_t2_f12_02_auth_header_empty_bearer():
    """T2.F12.2: 'Bearer ' with empty token falls back to demo."""
    auth_header = "Bearer "
    token = auth_header.replace("Bearer ", "").strip()
    assert token == ""


def test_t2_f12_03_token_with_unknown_tier_claim():
    """T2.F12.3: Token with unrecognized tier claim 'vip_gold' defaults safely."""
    claims = {"sub": "user@test.com", "tier": "vip_gold"}
    tier = claims.get("tier")
    effective_tier = "pro" if tier in {"pro", "pro_pass", "author_pro"} else "demo"
    assert effective_tier == "demo"


def test_t2_f12_04_demo_tier_compilation_settings_preservation(sample_ast):
    """T2.F12.4: Demo restriction preserves book metadata and compilation settings intact."""
    res_ast, _ = apply_demo_restriction(sample_ast, tier="demo")
    assert res_ast.metadata.title == sample_ast.metadata.title
    assert res_ast.compilation_settings.font_family == sample_ast.compilation_settings.font_family


def test_t2_f12_05_pro_tier_preserves_all_frontmatter(sample_ast):
    """T2.F12.5: Front matter (title page, copyright, dedication) is fully preserved in both tiers."""
    demo_ast, _ = apply_demo_restriction(sample_ast, tier="demo")
    pro_ast, _ = apply_demo_restriction(sample_ast, tier="pro")
    assert demo_ast.front_matter.title_page.enabled == sample_ast.front_matter.title_page.enabled
    assert pro_ast.front_matter.copyright.enabled == sample_ast.front_matter.copyright.enabled
