"""Shared color palette for the Frenchie terminal interface.

All visual components should import colors from here to ensure
a consistent theme across the entire application.
"""

# ── Primary brand ────────────────────────────────────────────────────────────
CLAUDE_ORANGE = "#e5484d"  # primary red — accents, headers, brand
CLAUDE_LIGHT  = "#ff8787"  # light red — secondary accents
CLAUDE_DIM    = "#7a2020"  # dark red — borders, muted elements

# ── Semantic ─────────────────────────────────────────────────────────────────
ACCENT_GREEN  = "#5fd787"  # success, ok, connected
ACCENT_YELLOW = "#ffd75f"  # warning, safe mode, attention
ACCENT_RED    = "#ff5f5f"  # error, failure, danger
ACCENT_CYAN   = "#ff8787"  # info, data (light red — repurposed from blue)

# ── Text ─────────────────────────────────────────────────────────────────────
TEXT_PRIMARY   = "#ffffff"  # main text
TEXT_SECONDARY = "#b0b0b0"  # secondary text
TEXT_DIM       = "#6c6c6c"  # dim / metadata

# ── Backgrounds ──────────────────────────────────────────────────────────────
BG_SURFACE  = "#1a1a1a"  # default surface
BG_ELEVATED = "#242424"  # elevated / focused surface
