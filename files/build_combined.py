"""
build_combined.py
------------------
Inlines dashboard_data.js and dashboard.js into dashboard.html so the
whole dashboard is a single self-contained file (no relative file
references, no sandbox/CORS issues when previewing).

Usage:
    python3 build_combined.py
Produces:
    dashboard_combined.html
"""

from pathlib import Path

html = Path("dashboard_standalone.html").read_text(encoding="utf-8")
data_js = Path("dashboard_data.js").read_text(encoding="utf-8")
logic_js = Path("dashboard.js").read_text(encoding="utf-8")

marker = '<script src="./dashboard_data.js"></script>\n<script src="./dashboard.js"></script>'
replacement = f"<script>\n{data_js}\n</script>\n<script>\n{logic_js}\n</script>"

assert marker in html, "Marker not found — check dashboard_standalone.html script tags"
combined = html.replace(marker, replacement)

Path("dashboard_combined.html").write_text(combined, encoding="utf-8")
print(f"Wrote dashboard_combined.html ({Path('dashboard_combined.html').stat().st_size/1024:.1f} KB)")
