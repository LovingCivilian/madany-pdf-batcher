"""
Reusable PDF Preview Widget.

Provides a consistent preview rendering with:
- Gray background
- Centered page with margins
- Drop shadow effect
- Optional overlay guides for margins
"""

from typing import Dict, Optional, Callable

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QPalette
from PySide6.QtWidgets import QLabel, QSizePolicy, QFrame

import fitz


class PDFPreviewWidget(QLabel):
    """
    A QLabel-based widget for rendering PDF page previews with
    consistent styling (gray background, shadow, margins).
    """
    
    # --- Style Constants ---
    
    # Active Background (Image present)
    BG_LIGHT = "#d4d4d7"
    BG_DARK = "#2a2a2e"
    
    # Disabled Background (No image)
    DISABLED_BG_LIGHT = "#d4d4d7"
    DISABLED_BG_DARK = "#2a2a2e"
    
    # Shadow
    SHADOW_LIGHT = "#a0a0a0"
    SHADOW_DARK = "#151515"
    
    SHADOW_OFFSET = 3
    PADDING = 20
    
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- FIX: Initialize attributes FIRST ---
        # This prevents crashes if setBackgroundRole triggers an early changeEvent
        self._current_image: Optional[QImage] = None
        self._overlay_config: Optional[Dict] = None
        self._overlay_scale: float = 1.0

        self.setAlignment(Qt.AlignCenter)
        self.setAutoFillBackground(True)
        self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(100, 100)
        self.setFrameStyle(QFrame.StyledPanel)
    
    def clear_preview(self) -> None:
        """Clear the preview display and show disabled state."""
        self._current_image = None
        self._overlay_config = None
        # We don't call self.clear() because we want to render the disabled background
        self._render()
    
    def set_image(self, image: QImage, overlay_config: Optional[Dict] = None, scale: float = 1.0) -> None:
        """
        Set the preview image and trigger a render.
        
        Args:
            image: The QImage to display
            overlay_config: Optional config dict for drawing margin guides
            scale: Scale factor (zoom) used to generate the image relative to PDF points.
                   If image is 1:1 with PDF points (72 DPI), scale should be 1.0.
        """
        self._current_image = image
        self._overlay_config = overlay_config
        self._overlay_scale = scale
        self._render()
    
    def set_page(self, page: fitz.Page, zoom: float = 1.5, 
                 overlay_config: Optional[Dict] = None) -> None:
        """
        Render a fitz.Page directly to the preview.
        
        Args:
            page: The PyMuPDF page to render
            zoom: Zoom factor for rendering
            overlay_config: Optional config dict for drawing margin guides
        """
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        
        fmt = QImage.Format_RGB888 if pixmap.n == 3 else QImage.Format_RGBA8888
        image = QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, fmt).copy()
        
        self.set_image(image, overlay_config, zoom)
    
    def changeEvent(self, event: QEvent) -> None:
        """
        Handle system events, specifically palette changes.
        This ensures the preview background and shadow update immediately when switching themes.
        """
        if event.type() == QEvent.PaletteChange:
            self._render()
        super().changeEvent(event)

    def _is_dark_mode(self) -> bool:
        """Heuristic to detect if the application is in dark mode."""
        # If the Window background is dark (< 128 lightness), assume dark mode.
        return self.palette().color(QPalette.Window).lightness() < 128

    def _render(self) -> None:
        """Render the current image (or disabled state) with styling."""
        canvas_width = self.width()
        canvas_height = self.height()
        
        if canvas_width <= 0 or canvas_height <= 0:
            return
        
        # Determine Theme Colors
        is_dark = self._is_dark_mode()
        
        if self._current_image is None:
            # --- Disabled State Rendering ---
            bg_color = QColor(self.DISABLED_BG_DARK if is_dark else self.DISABLED_BG_LIGHT)
            
            final_image = QImage(canvas_width, canvas_height, QImage.Format_RGB888)
            final_image.fill(bg_color)
            
            # Optional: Draw a "No Preview" text or symbol?
            # For now, just the distinct background color as requested.
            
            self.setPixmap(QPixmap.fromImage(final_image))
            return

        # --- Active State Rendering ---
        bg_color = QColor(self.BG_DARK if is_dark else self.BG_LIGHT)
        shadow_color = QColor(self.SHADOW_DARK if is_dark else self.SHADOW_LIGHT)

        # Calculate available space with padding
        available_width = canvas_width - 2 * self.PADDING
        available_height = canvas_height - 2 * self.PADDING
        
        if available_width <= 0 or available_height <= 0:
            return
        
        # Scale the image to fit
        img_width = self._current_image.width()
        img_height = self._current_image.height()
        
        # 'fit_scale' converts Image Pixels -> Screen Pixels
        fit_scale = min(available_width / img_width, available_height / img_height)
        scaled_width = int(img_width * fit_scale)
        scaled_height = int(img_height * fit_scale)
        
        scaled_pixmap = QPixmap.fromImage(self._current_image).scaled(
            scaled_width, scaled_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # Create final image with background
        final_image = QImage(canvas_width, canvas_height, QImage.Format_RGB888)
        final_image.fill(bg_color)
        
        painter = QPainter(final_image)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        # Center the page
        paper_x = (canvas_width - scaled_pixmap.width()) // 2
        paper_y = (canvas_height - scaled_pixmap.height()) // 2
        
        # Draw shadow
        # painter.fillRect(
        #     paper_x + self.SHADOW_OFFSET,
        #     paper_y + self.SHADOW_OFFSET,
        #     scaled_pixmap.width(),
        #     scaled_pixmap.height(),
        #     shadow_color
        # )
        
        # Draw the page
        painter.drawPixmap(paper_x, paper_y, scaled_pixmap)
        
        # Draw overlay guides if configured
        if self._overlay_config is not None:
            # FIX: Multiply fit_scale by _overlay_scale (zoom) to get ratio: Screen Pixels / PDF Points
            effective_scale = fit_scale * self._overlay_scale
            
            self._draw_overlay_guides(
                painter, paper_x, paper_y,
                scaled_pixmap.width(), scaled_pixmap.height(),
                self._overlay_config, effective_scale
            )
        
        painter.end()
        self.setPixmap(QPixmap.fromImage(final_image))
    
    def _draw_overlay_guides(self, painter: QPainter, x: int, y: int, 
                              w: int, h: int, config: Dict, scale: float) -> None:
        """Draw margin guide lines on the preview."""
        # Save painter state and set clipping to paper bounds
        painter.save()
        painter.setClipRect(x, y, w, h)
        
        pen = QPen(QColor(0, 0, 255))
        pen.setWidth(1)
        pen.setStyle(Qt.DotLine)
        painter.setPen(pen)
        
        h_margin_mm = config.get("h_margin", 10.0)
        v_margin_mm = config.get("v_margin", 10.0)
        
        # 1 mm = 2.83465 points
        pts_per_mm = 72 / 25.4
        
        mx_px = int(h_margin_mm * pts_per_mm * scale)
        my_px = int(v_margin_mm * pts_per_mm * scale)
        
        pos_str = config.get("position", "Top Left")
        
        # Extend lines beyond clip region to ensure they reach edges visually
        extend = 5
        
        # Vertical Lines (Left / Right)
        # Removed 'mx_px < w' check to match old behavior strictly, 
        # though clipping handles it anyway.
        if pos_str.endswith("Left"):
            painter.drawLine(x + mx_px, y - extend, x + mx_px, y + h + extend)
        elif pos_str.endswith("Right"):
            painter.drawLine(x + w - mx_px, y - extend, x + w - mx_px, y + h + extend)
        
        # Horizontal Lines (Top / Bottom)
        if pos_str.startswith("Top"):
            painter.drawLine(x - extend, y + my_px, x + w + extend, y + my_px)
        elif pos_str.startswith("Bottom"):
            painter.drawLine(x - extend, y + h - my_px, x + w + extend, y + h - my_px)
        
        # Restore painter state
        painter.restore()
    
    def resizeEvent(self, event) -> None:
        """Re-render on resize."""
        super().resizeEvent(event)
        self._render()


def render_pdf_preview(page: fitz.Page, canvas_width: int, canvas_height: int,
                       overlay_config: Optional[Dict] = None,
                       padding: int = 20, shadow_offset: int = 3,
                       bg_color: str = "#d0d0d0", shadow_color: str = "#a0a0a0") -> QImage:
    """
    Standalone function to render a PDF page preview with styling.
    """
    if canvas_width < 50 or canvas_height < 50:
        img = QImage(max(1, canvas_width), max(1, canvas_height), QImage.Format_RGB888)
        img.fill(QColor(bg_color))
        return img
    
    # Get page dimensions
    rect = page.rect
    page_w, page_h = rect.width, rect.height
    
    # Calculate scale to fit within canvas with padding
    available_width = canvas_width - 2 * padding
    available_height = canvas_height - 2 * padding
    
    scale = min(available_width / page_w, available_height / page_h)
    
    # Render the page
    matrix = fitz.Matrix(scale, scale)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    
    fmt = QImage.Format_RGB888 if pixmap.n == 3 else QImage.Format_RGBA8888
    pdf_image = QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, fmt).copy()
    
    # Create final canvas
    final_image = QImage(canvas_width, canvas_height, QImage.Format_RGB888)
    final_image.fill(QColor(bg_color))
    
    painter = QPainter(final_image)
    painter.setRenderHint(QPainter.Antialiasing, False)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    
    # Center the page
    paper_x = (canvas_width - pixmap.width) // 2
    paper_y = (canvas_height - pixmap.height) // 2
    
    # Draw shadow
    painter.fillRect(
        paper_x + shadow_offset,
        paper_y + shadow_offset,
        pixmap.width,
        pixmap.height,
        QColor(shadow_color)
    )
    
    # Draw the page
    painter.drawImage(paper_x, paper_y, pdf_image)
    
    # Draw overlay guides if configured
    if overlay_config is not None:
        _draw_guides(painter, paper_x, paper_y, pixmap.width, pixmap.height, overlay_config, scale)
    
    painter.end()
    return final_image


def _draw_guides(painter: QPainter, x: int, y: int, w: int, h: int, 
                 config: Dict, scale: float) -> None:
    """Internal helper to draw margin guides."""
    painter.save()
    painter.setClipRect(x, y, w, h)
    
    pen = QPen(QColor(0, 0, 255))
    pen.setWidth(1)
    pen.setStyle(Qt.DotLine)
    painter.setPen(pen)
    
    h_margin_mm = config.get("h_margin", 10.0)
    v_margin_mm = config.get("v_margin", 10.0)
    
    pts_per_mm = 72 / 25.4
    
    mx_px = int(h_margin_mm * pts_per_mm * scale)
    my_px = int(v_margin_mm * pts_per_mm * scale)
    
    pos_str = config.get("position", "Top Left")
    extend = 5
    
    if pos_str.endswith("Left"):
        painter.drawLine(x + mx_px, y - extend, x + mx_px, y + h + extend)
    elif pos_str.endswith("Right"):
        painter.drawLine(x + w - mx_px, y - extend, x + w - mx_px, y + h + extend)
    
    if pos_str.startswith("Top"):
        painter.drawLine(x - extend, y + my_px, x + w + extend, y + my_px)
    elif pos_str.startswith("Bottom"):
        painter.drawLine(x - extend, y + h - my_px, x + w + extend, y + h - my_px)
    
    painter.restore()