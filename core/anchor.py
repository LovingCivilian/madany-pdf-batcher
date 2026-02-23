from __future__ import annotations
from typing import Tuple, Dict, Any, Final

# Constants
MM_TO_PTS_FACTOR: Final[float] = 72.0 / 25.4
DEFAULT_MARGIN_MM: Final[float] = 10.0


def mm_to_points(mm: float) -> float:
    """Convert millimeters to PDF points."""
    return mm * MM_TO_PTS_FACTOR


def compute_anchor_for_pdf(
    page_w_pts: float,
    page_h_pts: float,
    block_w_pts: float,
    block_h_pts: float,
    cfg: Dict[str, Any],
) -> Tuple[float, float]:
    """
    Compute the TOP-LEFT anchor (x, y) of a text block on a PDF page.

    Args:
        page_w_pts: Page width in points.
        page_h_pts: Page height in points.
        block_w_pts: Text block width in points.
        block_h_pts: Text block height in points.
        cfg: Configuration dictionary containing:
             - 'position': String (e.g., "Top Left", "Center", "Bottom Right").
             - 'h_margin': Horizontal margin in mm.
             - 'v_margin': Vertical margin in mm.

    Returns:
        (x, y) tuple representing the top-left corner of the block.
    """
    position = cfg.get("position") or "Top Left"
    
    # Margin conversion
    margin_h_mm = cfg.get("h_margin", DEFAULT_MARGIN_MM)
    margin_v_mm = cfg.get("v_margin", DEFAULT_MARGIN_MM)

    margin_x_pts = mm_to_points(margin_h_mm)
    margin_y_pts = mm_to_points(margin_v_mm)

    # ------------------------------------------------------------------
    # Vertical Calculation (Y)
    # ------------------------------------------------------------------
    # Default to Vertical Center (Middle Row)
    y_pos = (page_h_pts - block_h_pts) / 2.0  

    if "Top" in position:
        y_pos = margin_y_pts
    elif "Bottom" in position:
        y_pos = page_h_pts - margin_y_pts - block_h_pts

    # ------------------------------------------------------------------
    # Horizontal Calculation (X)
    # ------------------------------------------------------------------
    # Default to Horizontal Center (Center Column)
    x_pos = (page_w_pts - block_w_pts) / 2.0  

    if "Left" in position:
        x_pos = margin_x_pts
    elif "Right" in position:
        x_pos = page_w_pts - margin_x_pts - block_w_pts

    return x_pos, y_pos