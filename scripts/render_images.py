"""Render PNGs of an interactive citation map, for slides, posters and papers.

Drives headless Chrome over the page written by make_html.py. Needs Chrome or
Chromium installed; set CHROME to override the search.
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

VIEWS = {"papers": "paper", "authors": "author", "institutions": "inst"}

CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]

# The page sizes .wrap off the viewport, so the canvas runs past a headless
# window unless the body is made a flex column that ends at 100vh.
FIT_WINDOW = """
 body { display:flex; flex-direction:column; height:100vh; overflow:hidden; }
 .wrap { flex:1; height:auto !important; min-height:0; }
"""

# Graph only: no title, no filter chips, no totals panel.
GRAPH_ONLY = """
 header, .chips, .side { display:none !important; }
 body { height:100vh; overflow:hidden; }
 .wrap { grid-template-columns:1fr !important; height:100vh !important; }
"""

INJECT = """
<style>%s</style>
<script>
setTimeout(() => { MODE = "%s"; resize(); relayout(); }, 150);
</script>
"""


def find_chrome():
    env = os.environ.get("CHROME")
    if env:
        return env
    for c in CANDIDATES:
        found = c if os.path.isfile(c) else shutil.which(c)
        if found:
            return found
    sys.exit("no Chrome or Chromium found; install one or set CHROME")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default="citation_map.html", help="output of make_html.py")
    ap.add_argument("--out-dir", default="images")
    ap.add_argument("--views", default="papers,authors,institutions")
    ap.add_argument("--width", type=int, default=2400)
    ap.add_argument("--height", type=int, default=1400)
    ap.add_argument("--scale", type=float, default=1.0,
                    help="device pixel ratio; 2 doubles the pixels for print")
    ap.add_argument("--graph-only", action="store_true",
                    help="drop the title, chips and totals panel")
    args = ap.parse_args()

    chrome = find_chrome()
    page = pathlib.Path(args.page).resolve()
    if not page.is_file():
        sys.exit(f"{page} not found; run make_html.py first")
    out_dir = pathlib.Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    css = GRAPH_ONLY if args.graph_only else FIT_WINDOW
    html = page.read_text()
    if "relayout()" not in html:
        sys.exit(f"{page} predates the fit in make_html.py; regenerate it first")

    with tempfile.TemporaryDirectory() as tmp:
        for name in [v.strip() for v in args.views.split(",") if v.strip()]:
            if name not in VIEWS:
                sys.exit(f"unknown view {name!r}; pick from {', '.join(VIEWS)}")
            shot = out_dir / f"{page.stem}_{name}.png"
            staged = pathlib.Path(tmp) / f"{name}.html"
            staged.write_text(html + INJECT % (css, VIEWS[name]))
            subprocess.run([
                chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                f"--window-size={args.width},{args.height}",
                f"--force-device-scale-factor={args.scale}",
                "--virtual-time-budget=9000", f"--screenshot={shot}",
                staged.as_uri(),
            ], check=True, capture_output=True)
            print("wrote", shot, os.path.getsize(shot), "bytes")


if __name__ == "__main__":
    main()
