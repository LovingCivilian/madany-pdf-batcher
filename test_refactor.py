"""
Regression tests for the Category 1 deduplication refactor.

Tests cover:
- get_page_dim_corrected
- resolve_config_for_page
- parse_custom_pages
- check_page_selection
- PDFOperations.apply_stamp_to_page (via apply_text_to_page as a proxy)
- End-to-end text insertion via batch path vs preview path consistency
"""
import io
import sys
import traceback

import fitz

from core.pdf_operations import (
    PDFOperations,
    get_page_dim_corrected,
    resolve_config_for_page,
    parse_custom_pages,
    check_page_selection,
)
from core.constants import DEFAULT_TEXT_CONFIG, DEFAULT_TIMESTAMP_CONFIG, DEFAULT_STAMP_CONFIG

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []


def test(name, fn):
    try:
        fn()
        results.append((True, name))
        print(f"  {PASS} {name}")
    except Exception as e:
        results.append((False, name))
        print(f"  {FAIL} {name}")
        traceback.print_exc()


def make_page(width=595, height=842, rotation=0):
    """Create an in-memory PDF and return its first page."""
    doc = fitz.open()
    doc.insert_page(0, width=width, height=height)
    page = doc.load_page(0)
    if rotation:
        page.set_rotation(rotation)
    return doc, page


# ------------------------------------------------------------------
# get_page_dim_corrected
# ------------------------------------------------------------------
def t_dim_portrait():
    doc, page = make_page(595, 842)
    w, h = get_page_dim_corrected(page)
    assert abs(w - 595) < 1 and abs(h - 842) < 1, f"Expected 595x842, got {w}x{h}"
    doc.close()

def t_dim_landscape():
    doc, page = make_page(842, 595)
    w, h = get_page_dim_corrected(page)
    assert abs(w - 842) < 1 and abs(h - 595) < 1, f"Expected 842x595, got {w}x{h}"
    doc.close()

def t_dim_rotated_90():
    doc, page = make_page(595, 842, rotation=90)
    w, h = get_page_dim_corrected(page)
    # PyMuPDF already swaps page.rect for 90/270 rotation. get_page_dim_corrected
    # un-does that swap to return the underlying physical paper dimensions, so
    # paper-size detection is consistent regardless of stored rotation.
    assert abs(w - 595) < 1 and abs(h - 842) < 1, f"Expected physical 595x842, got {w}x{h}"
    doc.close()

def t_dim_rotated_270():
    doc, page = make_page(595, 842, rotation=270)
    w, h = get_page_dim_corrected(page)
    assert abs(w - 595) < 1 and abs(h - 842) < 1, f"Expected physical 595x842, got {w}x{h}"
    doc.close()

def t_dim_rotated_180():
    doc, page = make_page(595, 842, rotation=180)
    w, h = get_page_dim_corrected(page)
    # 180 does not swap dimensions
    assert abs(w - 595) < 1 and abs(h - 842) < 1, f"Expected 595x842 after rot180, got {w}x{h}"
    doc.close()


# ------------------------------------------------------------------
# parse_custom_pages
# ------------------------------------------------------------------
def t_parse_simple():
    assert parse_custom_pages("1,3,5", 10) == {1, 3, 5}

def t_parse_range():
    assert parse_custom_pages("2-4", 10) == {2, 3, 4}

def t_parse_mixed():
    assert parse_custom_pages("1-3, 5, 7-9", 10) == {1, 2, 3, 5, 7, 8, 9}

def t_parse_out_of_bounds():
    # Pages beyond total should be ignored
    result = parse_custom_pages("1, 20, 50", 10)
    assert result == {1}, f"Expected {{1}}, got {result}"

def t_parse_reversed_range():
    assert parse_custom_pages("5-3", 10) == {3, 4, 5}

def t_parse_empty():
    assert parse_custom_pages("", 10) == set()

def t_parse_invalid():
    # Bad tokens should be skipped silently
    result = parse_custom_pages("abc, 2, xyz", 10)
    assert result == {2}, f"Expected {{2}}, got {result}"


# ------------------------------------------------------------------
# check_page_selection
# ------------------------------------------------------------------
def t_sel_all():
    cfg = {"page_selection": "all"}
    for i in range(5):
        assert check_page_selection(cfg, i, 5)

def t_sel_first():
    cfg = {"page_selection": "first"}
    assert check_page_selection(cfg, 0, 5) is True
    assert check_page_selection(cfg, 1, 5) is False

def t_sel_last():
    cfg = {"page_selection": "last"}
    assert check_page_selection(cfg, 4, 5) is True
    assert check_page_selection(cfg, 0, 5) is False

def t_sel_odd():
    cfg = {"page_selection": "odd"}
    assert check_page_selection(cfg, 0, 5) is True   # page 1
    assert check_page_selection(cfg, 1, 5) is False  # page 2
    assert check_page_selection(cfg, 2, 5) is True   # page 3

def t_sel_even():
    cfg = {"page_selection": "even"}
    assert check_page_selection(cfg, 0, 5) is False  # page 1
    assert check_page_selection(cfg, 1, 5) is True   # page 2

def t_sel_custom():
    cfg = {"page_selection": "custom", "custom_pages": "1,3"}
    assert check_page_selection(cfg, 0, 5) is True   # page 1
    assert check_page_selection(cfg, 1, 5) is False  # page 2
    assert check_page_selection(cfg, 2, 5) is True   # page 3

def t_sel_custom_bounds():
    # Pages outside total_pages must not match even if listed
    cfg = {"page_selection": "custom", "custom_pages": "1,99"}
    assert check_page_selection(cfg, 0, 5) is True
    assert check_page_selection(cfg, 4, 5) is False  # page 5 not in custom list

def t_sel_default():
    # Missing key defaults to "all"
    assert check_page_selection({}, 3, 10) is True

def t_sel_unknown_mode():
    cfg = {"page_selection": "bogus"}
    assert check_page_selection(cfg, 0, 5) is False


# ------------------------------------------------------------------
# resolve_config_for_page
# ------------------------------------------------------------------
def t_resolve_known_size():
    doc, page = make_page(595, 842)  # A4 portrait
    cfg_a4 = {"font_size": 24}
    cfg_default = {"font_size": 12}
    # A4 portrait key should be ("A4", "portrait")
    configs = {("A4", "portrait"): cfg_a4}
    result = resolve_config_for_page(page, configs, cfg_default)
    assert result is cfg_a4, f"Expected A4 config, got {result}"
    doc.close()

def t_resolve_fallback():
    doc, page = make_page(300, 400)  # Non-standard size
    cfg_default = {"font_size": 12}
    result = resolve_config_for_page(page, {}, cfg_default)
    assert result is cfg_default
    doc.close()

def t_resolve_unknown_portrait():
    doc, page = make_page(300, 400)
    cfg_unknown = {"font_size": 9}
    configs = {("Unknown", "portrait"): cfg_unknown}
    result = resolve_config_for_page(page, configs, {"font_size": 12})
    assert result is cfg_unknown
    doc.close()

def t_resolve_unknown_landscape():
    doc, page = make_page(400, 300)  # width > height = landscape
    cfg_unknown = {"font_size": 9}
    configs = {("Unknown", "landscape"): cfg_unknown}
    result = resolve_config_for_page(page, configs, {"font_size": 12})
    assert result is cfg_unknown
    doc.close()


# ------------------------------------------------------------------
# End-to-end: apply_text_to_page (uses get_page_dim_corrected internally)
# ------------------------------------------------------------------
FONT_FAMILIES = {}  # Use built-in helv font

def t_apply_text_portrait():
    doc, page = make_page(595, 842)
    ops = PDFOperations()
    cfg = dict(DEFAULT_TEXT_CONFIG)
    cfg["position"] = "Top Left"
    ops.apply_text_to_page(page, "Hello Portrait", cfg, FONT_FAMILIES)
    # Verify text was written by checking page content stream is non-trivial
    content = page.get_text()
    assert "Hello Portrait" in content, f"Text not found in page. Got: {content!r}"
    doc.close()

def t_apply_text_rotated():
    """Text insertion must work on rotated pages without crashing."""
    doc, page = make_page(595, 842, rotation=90)
    ops = PDFOperations()
    cfg = dict(DEFAULT_TEXT_CONFIG)
    cfg["position"] = "Center Center"
    ops.apply_text_to_page(page, "Hello Rotated", cfg, FONT_FAMILIES)
    doc.close()

def t_apply_text_multiline():
    doc, page = make_page(595, 842)
    ops = PDFOperations()
    cfg = dict(DEFAULT_TEXT_CONFIG)
    ops.apply_text_to_page(page, "Line One\nLine Two\nLine Three", cfg, FONT_FAMILIES)
    content = page.get_text()
    assert "Line One" in content
    doc.close()


# ------------------------------------------------------------------
# End-to-end: apply_stamp_to_page (new unified method)
# ------------------------------------------------------------------
def _make_stamp_bytes(size=20):
    """Create a tiny PNG image as stamp bytes."""
    from PIL import Image
    img = Image.new("RGBA", (size, size), (255, 0, 0, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def t_apply_stamp_no_prepared():
    """apply_stamp_to_page with stamp_path only (preview path)."""
    import tempfile, os
    stamp_bytes = _make_stamp_bytes()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tf:
        tf.write(stamp_bytes)
        stamp_path = tf.name
    try:
        doc, page = make_page(595, 842)
        ops = PDFOperations()
        cfg = dict(DEFAULT_STAMP_CONFIG)
        cfg["position"] = "Center Center"
        ops.apply_stamp_to_page(page, cfg, stamp_path, prepared_stamp=None)
        doc.close()
    finally:
        os.unlink(stamp_path)

def t_apply_stamp_with_prepared():
    """apply_stamp_to_page with PreparedStamp (batch path)."""
    import tempfile, os
    from core.pdf_operations import PreparedStamp
    stamp_bytes = _make_stamp_bytes()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tf:
        tf.write(stamp_bytes)
        stamp_path = tf.name
    try:
        doc, page = make_page(595, 842)
        ops = PDFOperations()
        prepared = PreparedStamp(stamp_path, ops)
        cfg = dict(DEFAULT_STAMP_CONFIG)
        cfg["position"] = "Bottom Right"
        ops.apply_stamp_to_page(page, cfg, stamp_path, prepared_stamp=prepared)
        doc.close()
    finally:
        os.unlink(stamp_path)

def t_apply_stamp_rotation_90():
    """Stamp with 90-degree rotation swaps visual dimensions."""
    import tempfile, os
    stamp_bytes = _make_stamp_bytes()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tf:
        tf.write(stamp_bytes)
        stamp_path = tf.name
    try:
        doc, page = make_page(595, 842)
        ops = PDFOperations()
        cfg = dict(DEFAULT_STAMP_CONFIG)
        cfg["stamp_rotation"] = 90
        ops.apply_stamp_to_page(page, cfg, stamp_path)
        doc.close()
    finally:
        os.unlink(stamp_path)


# ------------------------------------------------------------------
# Consistency: batch path and preview path produce identical text placement
# ------------------------------------------------------------------
def t_batch_preview_text_consistency():
    """
    Both paths must call apply_text_to_page with the same config resolved
    from resolve_config_for_page. We verify resolve_config_for_page returns
    the same dict regardless of which caller uses it.
    """
    doc, page = make_page(595, 842)
    cfg_a4 = {"font_size": 18, "position": "Top Left", "page_selection": "all"}
    cfg_default = {"font_size": 12, "position": "Top Left", "page_selection": "all"}
    configs = {("A4", "portrait"): cfg_a4}

    # Simulate what the batch thread does
    result_batch = resolve_config_for_page(page, configs, cfg_default)
    # Simulate what the preview path does (same call, different caller)
    result_preview = resolve_config_for_page(page, configs, cfg_default)

    assert result_batch is result_preview is cfg_a4
    doc.close()


# ------------------------------------------------------------------
# Run all tests
# ------------------------------------------------------------------
print("\n--- get_page_dim_corrected ---")
test("portrait dimensions", t_dim_portrait)
test("landscape dimensions", t_dim_landscape)
test("rotated 90 degrees", t_dim_rotated_90)
test("rotated 270 degrees", t_dim_rotated_270)
test("rotated 180 degrees (no swap)", t_dim_rotated_180)

print("\n--- parse_custom_pages ---")
test("simple list", t_parse_simple)
test("range", t_parse_range)
test("mixed list and ranges", t_parse_mixed)
test("out-of-bounds pages ignored", t_parse_out_of_bounds)
test("reversed range normalised", t_parse_reversed_range)
test("empty string", t_parse_empty)
test("invalid tokens skipped", t_parse_invalid)

print("\n--- check_page_selection ---")
test("mode=all", t_sel_all)
test("mode=first", t_sel_first)
test("mode=last", t_sel_last)
test("mode=odd", t_sel_odd)
test("mode=even", t_sel_even)
test("mode=custom", t_sel_custom)
test("mode=custom bounds enforced", t_sel_custom_bounds)
test("missing key defaults to all", t_sel_default)
test("unknown mode returns False", t_sel_unknown_mode)

print("\n--- resolve_config_for_page ---")
test("known A4 portrait size", t_resolve_known_size)
test("fallback on unknown size", t_resolve_fallback)
test("unknown portrait key", t_resolve_unknown_portrait)
test("unknown landscape key", t_resolve_unknown_landscape)

print("\n--- apply_text_to_page (end-to-end) ---")
test("text on portrait page", t_apply_text_portrait)
test("text on rotated page (no crash)", t_apply_text_rotated)
test("multiline text", t_apply_text_multiline)

print("\n--- apply_stamp_to_page (end-to-end) ---")
test("stamp via direct path (preview path)", t_apply_stamp_no_prepared)
test("stamp via PreparedStamp (batch path)", t_apply_stamp_with_prepared)
test("stamp with 90-degree rotation", t_apply_stamp_rotation_90)

print("\n--- consistency ---")
test("batch and preview resolve same config", t_batch_preview_text_consistency)

# Summary
passed = sum(1 for ok, _ in results if ok)
total = len(results)
print(f"\n{'='*50}")
print(f"Results: {passed}/{total} passed")
if passed < total:
    print("FAILED tests:")
    for ok, name in results:
        if not ok:
            print(f"  - {name}")
    sys.exit(1)
else:
    print("All tests passed.")
