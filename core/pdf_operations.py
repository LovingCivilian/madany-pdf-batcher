from __future__ import annotations
from typing import Dict, Tuple, Optional, Any
from PIL import Image, ImageEnhance

import io
import fitz  # PyMuPDF

# Add this import to calculate positions
from core.anchor import compute_anchor_for_pdf

# Default constants
DEFAULT_PAD_X = 3
DEFAULT_PAD_Y = 3


class PDFOperations:
    """Handles PDF text insertion using PyMuPDF with optional background, underline, and strike."""

    def __init__(self) -> None:
        # Cache PyMuPDF Font objects by key (fontfile path or base14 name)
        self._font_cache: Dict[str, fitz.Font] = {}

    # ------------------------------------------------------------------
    # Color Helpers
    # ------------------------------------------------------------------
    def hex_to_rgb(self, hex_color: str) -> Tuple[float, float, float]:
        """Convert hex color string (#RRGGBB) to RGB tuple (0.0–1.0 range)."""
        clean_hex = hex_color.strip().lstrip("#")
        
        # Expand shorthand format (e.g., "FFF" -> "FFFFFF")
        if len(clean_hex) == 3:
            clean_hex = "".join(c * 2 for c in clean_hex)
            
        try:
            r = int(clean_hex[0:2], 16) / 255.0
            g = int(clean_hex[2:4], 16) / 255.0
            b = int(clean_hex[4:6], 16) / 255.0
        except ValueError:
            return (0.0, 0.0, 0.0)
            
        return (r, g, b)

    # ------------------------------------------------------------------
    # Font Management
    # ------------------------------------------------------------------
    def get_font(self, font_key: str, fontfile: Optional[str] = None) -> fitz.Font:
        """Get a fitz.Font object with caching."""
        cache_key = fontfile or font_key
        
        if cache_key not in self._font_cache:
            if fontfile:
                self._font_cache[cache_key] = fitz.Font(fontfile=fontfile)
            else:
                self._font_cache[cache_key] = fitz.Font(font_key)
                
        return self._font_cache[cache_key]

    def resolve_font_path(self, config: dict, font_families: dict) -> Optional[str]:
        """Helper to pick the right font file (Bold/Italic) from the map."""
        family = config.get("font_family", "Arial")
        bold = config.get("bold", False)
        italic = config.get("italic", False)
        
        fam_map = font_families.get(family)
        if not fam_map: 
            return None # Will fall back to standard PDF fonts (helv)

        if bold and italic:
            return fam_map.get("bolditalic") or fam_map.get("bold") or fam_map.get("italic") or fam_map.get("regular")
        if bold:
            return fam_map.get("bold") or fam_map.get("regular")
        if italic:
            return fam_map.get("italic") or fam_map.get("regular")
        return fam_map.get("regular")

    def _calculate_vertical_metrics(
        self, font: fitz.Font, font_size: int, pad_y: int, line_gap: int
    ) -> Tuple[float, float, float]:
        """Internal helper to calculate vertical metrics."""
        ascender = font.ascender * font_size
        descender = abs(font.descender * font_size)

        if ascender or descender:
            line_height = ascender + descender + (pad_y * 2) + line_gap
        else:
            line_height = font_size + (pad_y * 2) + line_gap

        return ascender, descender, line_height

    # ------------------------------------------------------------------
    # Metrics Calculation
    # ------------------------------------------------------------------
    def compute_text_block_metrics(
        self, 
        text: str, 
        font: fitz.Font, 
        font_size: int, 
        pad_x: int = DEFAULT_PAD_X, 
        pad_y: int = DEFAULT_PAD_Y, 
        line_gap: int = 0
    ) -> Dict[str, Any]:
        """Compute metrics for a multiline text block."""
        asc, desc, line_height = self._calculate_vertical_metrics(
            font, font_size, pad_y, line_gap
        )
        
        lines = text.split("\n") if text else [""]
        line_widths = [font.text_length(line, fontsize=font_size) for line in lines]
        block_width = max(line_widths) if line_widths else 0.0
        
        base_height = asc + desc + (pad_y * 2)
        
        if len(lines) <= 1:
            total_height = base_height
        else:
            total_height = (base_height * len(lines)) + (line_gap * (len(lines) - 1))
        
        return {
            "asc": asc,
            "desc": desc,
            "line_height": line_height,
            "lines": lines,
            "widths": line_widths,
            "total_h": total_height,
            "block_width": block_width,
        }

    # ------------------------------------------------------------------
    # Text Insertion
    # ------------------------------------------------------------------
    def insert_text_with_background(
        self,
        page: fitz.Page,
        text: str,
        x_origin: float,
        y_baseline: float,
        font_key: str,
        font_size: int,
        text_color_hex: str,
        text_opacity: float,
        bg_color_hex: str,
        bg_opacity: float,
        underline: bool = False,
        strikethrough: bool = False,
        fontfile: Optional[str] = None,
        align: str = "left",
        pad_x: int = DEFAULT_PAD_X,
        pad_y: int = DEFAULT_PAD_Y,
        line_gap: int = 0,
    ) -> None:
        """Insert text (possibly multiline) with optional background, underline, and strikethrough."""
        if not text:
            return

        rgb_text = self.hex_to_rgb(text_color_hex)
        rgb_bg = self.hex_to_rgb(bg_color_hex)

        font = self.get_font(font_key, fontfile=fontfile)
        asc_height, desc_height, line_height = self._calculate_vertical_metrics(
            font, font_size, pad_y, line_gap
        )

        lines = text.split("\n")
        text_writer = fitz.TextWriter(page.rect)

        line_widths = [font.text_length(line, fontsize=font_size) for line in lines]
        max_width = max(line_widths) if line_widths else 0.0

        bg_shape = page.new_shape() if bg_opacity > 0 else None

        for i, line_text in enumerate(lines):
            line_width = line_widths[i]

            align_lower = align.lower()
            if align_lower == "left":
                x_pos = x_origin + pad_x
            elif align_lower == "right":
                x_pos = x_origin + (max_width - line_width) - pad_x
            else:
                x_pos = x_origin + (max_width - line_width) / 2.0

            current_baseline_y = y_baseline + (i * line_height)

            if bg_shape is not None and line_width > 0:
                rect = fitz.Rect(
                    x_pos - pad_x,
                    current_baseline_y - asc_height - pad_y,
                    x_pos + line_width + pad_x,
                    current_baseline_y + desc_height + pad_y,
                )
                bg_shape.draw_rect(rect)

            if line_text:
                text_writer.append(
                    (x_pos, current_baseline_y),
                    line_text,
                    fontsize=font_size,
                    font=font
                )

                quad = fitz.Quad(
                    fitz.Point(x_pos, current_baseline_y - asc_height),
                    fitz.Point(x_pos + line_width, current_baseline_y - asc_height),
                    fitz.Point(x_pos, current_baseline_y + desc_height),
                    fitz.Point(x_pos + line_width, current_baseline_y + desc_height),
                )

                if underline:
                    annot = page.add_underline_annot(quad)
                    annot.set_colors(stroke=rgb_text)
                    annot.set_opacity(text_opacity)
                    annot.update()

                if strikethrough:
                    annot = page.add_strikeout_annot(quad)
                    annot.set_colors(stroke=rgb_text)
                    annot.set_opacity(text_opacity)
                    annot.update()

        if bg_shape is not None:
            bg_shape.finish(fill=rgb_bg, fill_opacity=bg_opacity, color=None, width=0)
            bg_shape.commit()

        text_writer.write_text(page, color=rgb_text, opacity=text_opacity)

    # ------------------------------------------------------------------
    # High-Level Logic (Shared between Thread and UI)
    # ------------------------------------------------------------------
    def apply_text_to_page(self, page: fitz.Page, text: str, config: dict, font_families: dict):
        """
        High-level wrapper to calculate position, resolve font, and insert text.
        This allows both the UI (Preview) and the Worker Thread to use identical logic.
        """
        # 0. Normalize the content stream so existing transforms don't affect our text
        page.clean_contents()

        # 1. Get Page Dimensions (Corrected for Rotation)
        rect = page.rect
        if page.rotation in (90, 270):
            page_w, page_h = rect.height, rect.width
        else:
            page_w, page_h = rect.width, rect.height

        # 2. Resolve Font
        font_path = self.resolve_font_path(config, font_families)
        font_size = config.get("font_size", 12)
        # If font_path is None, we use 'helv' as safe fallback
        font_key = font_path if font_path else "helv" 
        
        # 3. Load Font & Compute Metrics
        font_obj = self.get_font(font_key, fontfile=font_path)
        
        metrics = self.compute_text_block_metrics(
            text, font_obj, font_size, 
            pad_x=config.get("pad_x", 0), 
            pad_y=config.get("pad_y", 0), 
            line_gap=config.get("line_gap", 0)
        )

        # 4. Compute Position (Anchor)
        block_x, block_y = compute_anchor_for_pdf(
            page_w, page_h, metrics["block_width"], metrics["total_h"], config
        )
        baseline = block_y + config.get("pad_y", 0) + metrics["asc"]

        # 5. Determine Alignment
        pos_cfg = config.get("position", "Top Left")
        align = "center"
        if pos_cfg.endswith("Left"): align = "left"
        elif pos_cfg.endswith("Right"): align = "right"

        # 6. Draw
        self.insert_text_with_background(
            page, text, block_x, baseline, font_key, font_size,
            config.get("text_color", "#000000"),
            config.get("text_opacity", 100) / 100,
            config.get("bg_color", "#ffff00"),
            config.get("bg_opacity", 0) / 100,
            underline=config.get("underline", False),
            strikethrough=config.get("strike", False),
            fontfile=font_path,
            align=align,
            pad_x=config.get("pad_x", 0), 
            pad_y=config.get("pad_y", 0), 
            line_gap=config.get("line_gap", 0)
        )

    # ------------------------------------------------------------------
    # Stamp Processing
    # ------------------------------------------------------------------
    def process_stamp_image(
        self,
        stamp_path: str,
        max_pixels: int = 2000, # Increased cap, but utilized differently
        opacity: float = 1.0,
    ) -> bytes:
        """
        Process stamp image and return PNG bytes.
        OPTIMIZED: Faster compression, smarter resizing to prevent memory spikes.
        """
        try:
            with Image.open(stamp_path) as img:
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')

                w, h = img.size
                
                # --- OPTIMIZATION 1: Smart Resizing ---
                # Only upscale if image is tiny (blurry text). 
                # Don't upscale if it's already decent quality (e.g. > 500px).
                # Cap the maximum size to prevent memory crashes.
                
                target_scale = 1.0
                if w < 1000 or h < 1000:
                    # It's small, let's upscale it to look crisp
                    target_scale = 3.0

                if target_scale > 1.0:
                    # Use premultiplied alpha for clean resizing
                    img = img.convert('RGBa')
                    new_w = int(w * target_scale)
                    new_h = int(h * target_scale)
                    img = img.resize((new_w, new_h), resample=Image.Resampling.BILINEAR)
                    img = img.convert('RGBA')

                    # Only sharpen if we actually upscaled
                    enhancer = ImageEnhance.Sharpness(img)
                    img = enhancer.enhance(1.2)
            
                # --- OPTIMIZATION 2: Opacity ---
                if opacity < 1.0:
                    alpha = img.getchannel('A')
                    alpha = alpha.point(lambda p: int(p * opacity))
                    img.putalpha(alpha)
            
                # --- OPTIMIZATION 3: Speed over Size ---
                # optimize=False: Don't spend CPU trying to make the PNG small
                # compress_level=1: Fast compression (Level 6 is default and slow)
                # The final PDF save will compress it anyway!
                img_buffer = io.BytesIO()
                img.save(
                    img_buffer, 
                    format='PNG', 
                    optimize=False, 
                    compress_level=1
                )
                return img_buffer.getvalue()

        except Exception as e:
            print(f"Error processing stamp image: {e}")
            return b""

    def insert_stamp_bytes(
        self,
        page: fitz.Page,
        img_bytes: bytes,
        x_origin: float,
        y_origin: float,
        width: float,
        height: float,
        rotation: int = 0,
    ) -> Tuple[float, float]:
        """
        Insert pre-processed stamp bytes. Fast - no image processing.
        
        Args:
            page: The PDF page to insert the stamp on.
            img_bytes: Pre-processed PNG bytes.
            x_origin: X coordinate for stamp placement.
            y_origin: Y coordinate for stamp placement.
            width: Target width in points.
            height: Target height in points.
            rotation: Rotation angle (0, 90, 180, or 270 degrees only).
        
        Returns:
            Tuple of (width, height) of the inserted stamp.
        """
        if not img_bytes:
            return (0.0, 0.0)

        try:
            # Normalize the content stream so existing transforms don't affect our stamp
            page.clean_contents()

            target_rect = fitz.Rect(
                x_origin, y_origin,
                x_origin + width, y_origin + height
            )

            page.insert_image(
                target_rect,
                stream=img_bytes,
                keep_proportion=False,
                overlay=True,
                rotate=rotation
            )
            
            return (width, height)
        
        except Exception as e:
            print(f"Error inserting stamp: {e}")
            return (0.0, 0.0)

    def insert_stamp(
        self,
        page: fitz.Page,
        stamp_path: str,
        x_origin: float,
        y_origin: float,
        width: float,
        height: float,
        rotation: int = 0,
        opacity: float = 1.0,
        max_pixels: int = 1200,
    ) -> Tuple[float, float]:
        """
        Insert a stamp image with optional rotation and opacity.
        For batch processing, use PreparedStamp class instead.
        """
        if opacity <= 0.0:
            return (0.0, 0.0)
        
        try:
            img_bytes = self.process_stamp_image(stamp_path, max_pixels, opacity)
            return self.insert_stamp_bytes(
                page, img_bytes, x_origin, y_origin, width, height, rotation
            )
        except Exception as e:
            print(f"Error inserting stamp: {e}")
            return (0.0, 0.0)

    def get_stamp_dimensions(
        self,
        stamp_path: str,
        scale: float = 1.0
    ) -> Tuple[float, float]:
        """Get the dimensions of a stamp image file in points."""
        try:
            pixmap = fitz.Pixmap(stamp_path)
            width = pixmap.width * scale
            height = pixmap.height * scale
            pixmap = None
            return (width, height)
        except Exception:
            return (0.0, 0.0)


class PreparedStamp:
    """
    Pre-processed stamp with lazy caching by opacity.
    
    Usage:
        # Before batch loop
        prepared_stamp = PreparedStamp(stamp_path, pdf_ops)
        
        # In loop - automatically caches by opacity
        stamp_bytes = prepared_stamp.get_bytes(opacity)
    """
    
    def __init__(self, stamp_path: str, pdf_ops: PDFOperations, max_pixels: int = 1200):
        self.stamp_path = stamp_path
        self.pdf_ops = pdf_ops
        self.max_pixels = max_pixels
        self._cache: Dict[float, bytes] = {}
    
    def get_bytes(self, opacity: float) -> bytes:
        """Get processed bytes for opacity (processes once per opacity, caches automatically)."""
        key = round(opacity, 2)
        if key not in self._cache:
            self._cache[key] = self.pdf_ops.process_stamp_image(
                self.stamp_path, self.max_pixels, opacity
            )
        return self._cache[key]
    
    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()