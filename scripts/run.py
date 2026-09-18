"""Run the whole pipeline: resolve the publications, collect citations, build output.

Wraps setup_profile, collect_all, collect_oc_all, build and make_html so one
command does the job. The individual scripts still work on their own.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

SCRIPTS = pathlib.Path(__file__).resolve().parent


def run(script, args, cwd):
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print(f"\n$ {' '.join(cmd[1:])}\n", flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def report_targets(out_dir):
    """Prints which publications resolved, since unresolved ones collect nothing."""
    path = out_dir / "targets_resolved.json"
    targets = json.load(open(path))
    patents = [k for k, t in targets.items() if t["patent"]]
    unresolved = [k for k, t in targets.items()
                  if not t["patent"] and not t["dois"] and not t.get("s2_ids")]
    ready = len(targets) - len(patents) - len(unresolved)
    print(f"\n{ready} of {len(targets)} publications are ready to collect.")
    if patents:
        print(f"{len(patents)} patents skipped; no bibliographic API indexes them.")
    if unresolved:
        print(f"No identifier found for {len(unresolved)}, which collect nothing: "
              + ", ".join(unresolved))
        print(f"Add a DOI to each entry's \"dois\" list in {path} to include them.")


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--titles", metavar="FILE", help="one publication title per line")
    src.add_argument("--s2-author", metavar="ID", help="Semantic Scholar author id")
    ap.add_argument("--name", default="", help="your name, used in headings")
    ap.add_argument("--out-dir", default=".", help="everything is written here")
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--images", action="store_true",
                    help="also write PNGs of the three views, for slides")
    ap.add_argument("--skip-openalex", action="store_true",
                    help="OpenAlex meters requests daily; skip it and enrich later")
    ap.add_argument("--skip-collect", action="store_true",
                    help="reuse raw_all.json and only rebuild the output")
    args = ap.parse_args()

    out_dir = pathlib.Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    whose = f"{args.name}'s" if args.name else "these"
    started = time.time()

    if not args.skip_collect:
        if not (args.titles or args.s2_author):
            ap.error("one of --titles or --s2-author is required")
        if args.titles:
            titles = pathlib.Path(args.titles).resolve()
            if not titles.is_file():
                sys.exit(f"{titles} not found")
            run("setup_profile.py", ["--titles", str(titles)], out_dir)
        else:
            run("setup_profile.py", ["--s2-author", args.s2_author], out_dir)
        report_targets(out_dir)

        collect = ["--skip-openalex"] if args.skip_openalex else []
        run("collect_all.py", collect, out_dir)
        run("collect_oc_all.py", [], out_dir)
    elif not (out_dir / "raw_all.json").is_file():
        sys.exit(f"--skip-collect needs {out_dir / 'raw_all.json'}, which is missing")

    run("build.py", ["--raw", "raw_all.json", "--out-dir", ".",
                     "--title", f"{whose} publications"], out_dir)
    run("make_html.py", ["--data", "data/data.json", "--out", "citation_map.html",
                         "--theme", args.theme,
                         "--heading", f"Who cites {whose} work"], out_dir)
    if args.images:
        run("render_images.py", ["--page", "citation_map.html", "--out-dir", "images",
                                 "--graph-only"], out_dir)

    mins = (time.time() - started) / 60
    print(f"\nDone in {mins:.0f} min. Open {out_dir / 'citation_map.html'}")
    print(f"Tables are in {out_dir / 'tables'}, graph files in {out_dir / 'graphs'}.")
    if args.images:
        print(f"PNGs are in {out_dir / 'images'}.")


if __name__ == "__main__":
    main()
