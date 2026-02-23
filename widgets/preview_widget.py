"""
Reusable PDF Preview Widget.

Provides a consistent preview rendering with:
- Gray background
- Centered page with margins
- Drop shadow effect
- Optional overlay guides for margins
- Zoom support via viewport-based sizing
"""

from typing import Dict, Optional

from PySide6.QtCore import Qt, QEvent, QSize, QRect
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QPalette, QPaintEvent, QWheelEvent
from PySide6.QtWidgets import QWidget, QSizePolicy, QScrollArea

import fitz


class PDFPreviewWidget(QWidget):
    """
    A widget for rendering PDF page previews with
    consistent styling (gray background, shadow, margins).

    Uses paintEvent for efficient rendering — Qt only paints the
    visible region, which keeps zoom at any level responsive.
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

        # --- Initialize attributes FIRST ---
        self._current_image: Optional[QImage] = None
        self._source_pixmap: Optional[QPixmap] = None
        self._overlay_config: Optional[Dict] = None
        self._overlay_scale: float = 1.0
        self._user_zoom: float = 1.0
        self._viewport_size: Optional[QSize] = None
        self._scrollbar_margin: int = 0  # set by PreviewScrollArea
        self._rendering: bool = False

        # Cached display state (computed in _prepare_display, used in paintEvent)
        self._paper_rect: Optional[QRect] = None   # dest rect for the page on the canvas
        self._display_scale: float = 1.0
        self._bg_color: QColor = QColor(self.BG_LIGHT)

        self.setAutoFillBackground(True)
        self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(100, 100)

    def clear_preview(self) -> None:
        """Clear the preview display and show disabled state."""
        self._current_image = None
        self._source_pixmap = None
        self._overlay_config = None
        self._paper_rect = None
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
        self._source_pixmap = QPixmap.fromImage(image)
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

    def set_user_zoom(self, zoom: float, render: bool = True) -> None:
        """Set the user zoom level."""
        self._user_zoom = zoom
        if render:
            self._render()

    def set_viewport_size(self, size: QSize) -> None:
        """Set the viewport size (from the scroll area) and re-render."""
        self._viewport_size = size
        self._render()

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
        return self.palette().color(QPalette.Window).lightness() < 128

    def _render(self) -> None:
        """Prepare display state and schedule a repaint."""
        # Guard against re-entrant calls (resize -> viewport change -> _render loop)
        if self._rendering:
            return
        self._rendering = True
        try:
            self._prepare_display()
        finally:
            self._rendering = False

    def _prepare_display(self) -> None:
        """Compute layout geometry, resize widget, schedule repaint.

        No pixmap scaling here — paintEvent draws the source pixmap
        directly into a dest rect, so QPainter only processes visible pixels.
        """
        # Use viewport size as the base if available, otherwise own size
        if self._viewport_size is not None:
            base_w = self._viewport_size.width()
            base_h = self._viewport_size.height()
        else:
            base_w = self.width()
            base_h = self.height()

        if base_w <= 0 or base_h <= 0:
            return

        is_dark = self._is_dark_mode()

        if self._current_image is None or self._source_pixmap is None:
            # --- Disabled State ---
            self._bg_color = QColor(self.DISABLED_BG_DARK if is_dark else self.DISABLED_BG_LIGHT)
            self._paper_rect = None
            self.resize(base_w, base_h)
            self.update()
            return

        # --- Active State ---
        self._bg_color = QColor(self.BG_DARK if is_dark else self.BG_LIGHT)

        available_width = base_w - 2 * self.PADDING
        available_height = base_h - 2 * self.PADDING

        if available_width <= 0 or available_height <= 0:
            return

        img_width = self._source_pixmap.width()
        img_height = self._source_pixmap.height()

        # fit_scale: Source Pixels -> Screen Pixels at 100% zoom
        fit_scale = min(available_width / img_width, available_height / img_height)

        # Apply user zoom
        self._display_scale = fit_scale * self._user_zoom
        scaled_width = int(img_width * self._display_scale)
        scaled_height = int(img_height * self._display_scale)

        # Canvas = max of viewport or page+padding.
        # Snap to viewport when overflow is smaller than the scrollbar
        # margin — this prevents the oscillation where a scrollbar
        # appearing/disappearing changes the viewport by that exact amount.
        content_w = scaled_width + 2 * self.PADDING
        content_h = scaled_height + 2 * self.PADDING
        sb = self._scrollbar_margin
        canvas_w = base_w if content_w <= base_w + sb else content_w
        canvas_h = base_h if content_h <= base_h + sb else content_h

        # Center the page on the canvas
        paper_x = (canvas_w - scaled_width) // 2
        paper_y = (canvas_h - scaled_height) // 2
        self._paper_rect = QRect(paper_x, paper_y, scaled_width, scaled_height)

        # Resize widget — drives scroll area scrollbars
        self.resize(canvas_w, canvas_h)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint only the visible region — efficient at any zoom level."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        exposed = event.rect()

        # Fill only the exposed area with background
        painter.fillRect(exposed, self._bg_color)

        if self._paper_rect is not None and self._source_pixmap is not None:
            # Draw source pixmap scaled into dest rect.
            # QPainter only processes pixels within the exposed/clipped region,
            # so this is fast regardless of zoom level.
            painter.drawPixmap(self._paper_rect, self._source_pixmap)

            # Draw overlay guides
            if self._overlay_config is not None:
                effective_scale = self._display_scale * self._overlay_scale
                self._draw_overlay_guides(
                    painter,
                    self._paper_rect.x(), self._paper_rect.y(),
                    self._paper_rect.width(), self._paper_rect.height(),
                    self._overlay_config, effective_scale
                )

        painter.end()

    def _draw_overlay_guides(self, painter: QPainter, x: int, y: int,
                              w: int, h: int, config: Dict, scale: float) -> None:
        """Draw margin guide lines on the preview."""
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

    def resizeEvent(self, event) -> None:
        """Re-render on resize (only when no viewport is set as fallback)."""
        super().resizeEvent(event)
        if self._viewport_size is None:
            self._render()


class PreviewScrollArea(QScrollArea):
    """A scroll area that forwards its viewport size to the preview widget.

    Reports the actual viewport size and provides the scrollbar margin to the
    child widget so it can snap canvas sizes that barely overflow, preventing
    oscillation when scrollbars toggle on/off.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom_callback = None

    def set_zoom_callback(self, callback):
        """Set a callback(delta, mouse_pos) for Ctrl+Scroll zoom.

        delta: +1 (zoom in) or -1 (zoom out)
        mouse_pos: QPoint position of cursor relative to viewport
        """
        self._zoom_callback = callback

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.ControlModifier and self._zoom_callback:
            delta = 1 if event.angleDelta().y() > 0 else -1
            mouse_vp = event.position().toPoint()
            self._zoom_callback(delta, mouse_vp)
            event.accept()
        else:
            super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        widget = self.widget()
        if widget is not None and hasattr(widget, 'set_viewport_size'):
            sb = max(
                self.verticalScrollBar().sizeHint().width(),
                self.horizontalScrollBar().sizeHint().height(),
            )
            widget._scrollbar_margin = sb
            widget.set_viewport_size(self.viewport().size())


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
