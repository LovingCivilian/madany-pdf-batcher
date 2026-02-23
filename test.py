import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor, QGuiApplication


def extract_ultimate_palette():
    app = QApplication(sys.argv)
    app.setStyle("fusion")
    palette = app.palette()

    # Auto-detect if the system is currently in Dark or Light mode
    win_color = palette.color(QPalette.Window)
    is_dark = win_color.lightness() < 128
    var_name = "dark_palette" if is_dark else "light_palette"

    # Get system accent color (Windows 10/11, macOS, some Linux DEs)
    accent_color = None
    
    # Method 1: Try to get from style hints (Qt 6.6+)
    if hasattr(QGuiApplication, 'styleHints'):
        hints = QGuiApplication.styleHints()
        if hasattr(hints, 'accentColor'):
            accent_color = hints.accentColor()
            if accent_color.isValid():
                print(f"# System accent color detected: {accent_color.name()}")
    
    # Method 2: Fall back to the Highlight color from system palette
    if accent_color is None or not accent_color.isValid():
        # Get the native palette before Fusion overrides it
        native_palette = QGuiApplication.palette()
        accent_color = native_palette.color(QPalette.Active, QPalette.Highlight)
        print(f"# Using Highlight as accent color: {accent_color.name()}")

    # All color roles needed for a complete theme
    roles = [
        (QPalette.Window, "Window"),
        (QPalette.WindowText, "WindowText"),
        (QPalette.Base, "Base"),
        (QPalette.AlternateBase, "AlternateBase"),
        (QPalette.ToolTipBase, "ToolTipBase"),
        (QPalette.ToolTipText, "ToolTipText"),
        (QPalette.PlaceholderText, "PlaceholderText"),
        (QPalette.Text, "Text"),
        (QPalette.Button, "Button"),
        (QPalette.ButtonText, "ButtonText"),
        (QPalette.BrightText, "BrightText"),
        (QPalette.Light, "Light"),
        (QPalette.Midlight, "Midlight"),
        (QPalette.Dark, "Dark"),
        (QPalette.Mid, "Mid"),
        (QPalette.Shadow, "Shadow"),
        (QPalette.Highlight, "Highlight"),
        (QPalette.HighlightedText, "HighlightedText"),
        (QPalette.Link, "Link"),
        (QPalette.LinkVisited, "LinkVisited"),
        (QPalette.Accent, "Accent"),  # Qt 6.6+ accent role
    ]

    # All UI states (Active, Inactive, Disabled)
    groups = [
        (QPalette.Active, "Active"),
        (QPalette.Inactive, "Inactive"),
        (QPalette.Disabled, "Disabled"),
    ]

    # Override the palette's Highlight/Accent with system accent color
    if accent_color and accent_color.isValid():
        for group, _ in groups:
            palette.setColor(group, QPalette.Highlight, accent_color)
            if hasattr(QPalette, 'Accent'):
                palette.setColor(group, QPalette.Accent, accent_color)
        
        # Create a lighter/darker variant for Link colors based on accent
        link_color = accent_color.lighter(110) if is_dark else accent_color
        link_visited = accent_color.darker(110) if is_dark else accent_color.darker(120)
        for group, _ in groups:
            palette.setColor(group, QPalette.Link, link_color)
            palette.setColor(group, QPalette.LinkVisited, link_visited)

    print("-" * 60)
    print(f"COPY THIS BLOCK INTO YOUR APP ({'DARK' if is_dark else 'LIGHT'} MODE):")
    print("-" * 60)
    print(f"{var_name} = QPalette()")

    for group, group_name in groups:
        print(f"\n    # --- {group_name} Group ---")
        for role, role_name in roles:
            # Skip Accent if not available in this Qt version
            if role_name == "Accent" and not hasattr(QPalette, 'Accent'):
                continue
            c = palette.color(group, role)
            print(
                f"    {var_name}.setColor(QPalette.{group_name}, QPalette.{role_name}, "
                f"QColor({c.red()}, {c.green()}, {c.blue()}, {c.alpha()}))"
            )

    # Also print the raw accent color for reference
    print("\n    # --- System Accent Color Reference ---")
    if accent_color and accent_color.isValid():
        print(f"    # Accent: QColor({accent_color.red()}, {accent_color.green()}, {accent_color.blue()}, {accent_color.alpha()})")

    print("-" * 60)


if __name__ == "__main__":
    extract_ultimate_palette()