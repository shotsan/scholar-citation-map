"""Turn a list of publication titles into the target file the pipeline reads.

Three ways to get the titles, in decreasing order of reliability:

  --titles FILE        one title per line, taken from your Scholar profile
  --s2-author ID       every paper Semantic Scholar attributes to that author id
  --find-author NAME   print candidate author ids, then rerun with --s2-author

Titles are resolved to DOIs through Crossref, and a match is accepted only when
the returned title agrees with the one asked for. Co-authors are read off the
matched records, so self-citations are detected without a hand-written list.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Crossref and OpenAlex ask for a contact address in the User-Agent to get
# their faster "polite pool". Set CITATION_MAP_EMAIL to your own address.
UA = "citation-map/1.0 (mailto:%s)" % os.environ.get(
    "CITATION_MAP_EMAIL", "anonymous@example.com")
# Files are read and written relative to the current directory, so run the
# scripts from wherever you want the output to land.
HERE = os.getcwd()
S2 = "https://api.semanticscholar.org/graph/v1"

# Words that mark a title as a patent or a whole proceedings volume. No
# bibliographic API indexes these, so they are recorded and skipped.
SKIP_WORDS = ("us patent", "patent app", "patent no")


def get(url, tries=6, pause=8.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(pause * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(pause * (i + 1))
    return None


def norm(t):
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())


def similarity(a, b):
    """0 when the titles disagree, else the common prefix as a share of the longer."""
    x, y = norm(a), norm(b)
    if not x or not y:
        return 0.0
    n = 0
    for cx, cy in zip(x, y):
        if cx != cy:
            break
        n += 1
    # A short generic title prefixes several unrelated works, so a match needs
    # real length as well as a high share.
    if n < 25:
        return 0.0
    return n / max(len(x), len(y))


def slug(title, taken):
    base = "_".join(re.findall(r"[a-z0-9]+", title.lower())[:3]) or "paper"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    return key


def find_author(name):
    d = get(f"{S2}/author/search?query={urllib.parse.quote(name)}"
            "&fields=authorId,name,affiliations,paperCount,citationCount&limit=20")
    rows = (d or {}).get("data") or []
    if not rows:
        print("No author found. Check the spelling.")
        return
    print(f"{len(rows)} candidate profile(s). Semantic Scholar often splits one\n"
          "person across several ids, so pick the one with the paper count you expect:\n")
    for a in sorted(rows, key=lambda r: -(r.get("citationCount") or 0)):
        aff = "; ".join(a.get("affiliations") or []) or "no affiliation listed"
        print(f"  --s2-author {a['authorId']:<12} {a['name']:<24} "
              f"{a.get('paperCount') or 0:>3} papers, "
              f"{a.get('citationCount') or 0:>5} citations   {aff}")
    print("\nThen: python3 setup_profile.py --s2-author <id>")


def s2_author_titles(author_id):
    d = get(f"{S2}/author/{author_id}/papers"
            "?fields=title,year,venue,citationCount,externalIds&limit=500")
    rows = (d or {}).get("data") or []
    rows.sort(key=lambda p: -(p.get("citationCount") or 0))
    out = []
    for p in rows:
        if not p.get("title"):
            continue
        venue = p.get("venue") or ""
        year = p.get("year") or ""
        out.append({
            "title": p["title"],
            "venue": f"{venue} {year}".strip(),
            "scholar_citations": p.get("citationCount") or 0,
            "dois": [(p.get("externalIds") or {}).get("DOI", "").lower()] if
                    (p.get("externalIds") or {}).get("DOI") else [],
        })
    print(f"Semantic Scholar lists {len(out)} papers for author {author_id}")
    return out


def read_titles(path):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # optional "title | venue | citations"
            parts = [p.strip() for p in line.split("|")]
            out.append({
                "title": parts[0],
                "venue": parts[1] if len(parts) > 1 else "",
                "scholar_citations": int(parts[2]) if len(parts) > 2 and
                parts[2].isdigit() else 0,
                "dois": [],
            })
    print(f"read {len(out)} titles from {path}")
    return out


def crossref_resolve(title):
    """Best-matching Crossref record for a title, or None."""
    u = ("https://api.crossref.org/works?rows=6&select=DOI,title,container-title,"
         "issued,is-referenced-by-count,author&query.bibliographic="
         + urllib.parse.quote(title))
    d = get(u, tries=4, pause=3.0)
    items = ((d or {}).get("message") or {}).get("items") or []
    scored = [(similarity((it.get("title") or [""])[0], title), it) for it in items]
    scored = [(s, it) for s, it in scored if s >= 0.55]
    if not scored:
        return None, 0.0
    s, it = max(scored, key=lambda p: p[0])
    return it, s


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--titles", metavar="FILE")
    src.add_argument("--s2-author", metavar="ID")
    src.add_argument("--find-author", metavar="NAME")
    ap.add_argument("--out", default="targets_resolved.json")
    args = ap.parse_args()

    if args.find_author:
        find_author(args.find_author)
        return

    entries = (read_titles(args.titles) if args.titles
               else s2_author_titles(args.s2_author))
    if not entries:
        sys.exit("no publications found")

    out, taken = {}, set()
    for e in entries:
        key = slug(e["title"], taken)
        taken.add(key)
        rec = {"title": e["title"], "venue": e["venue"],
               "scholar_citations": e["scholar_citations"], "cluster": "",
               "patent": False, "oa_ids": [], "dois": list(e["dois"]),
               "coauthors": []}

        if any(w in (e["title"] + " " + e["venue"]).lower() for w in SKIP_WORDS):
            rec["patent"] = True
            print(f"{key}: patent or application, no API indexes these")
            out[key] = rec
            continue

        it, score = (None, 0.0) if rec["dois"] else crossref_resolve(e["title"])
        if it:
            rec["dois"] = [it["DOI"].lower()]
            rec["_score"] = round(score, 3)
        if rec["dois"]:
            if it:
                rec["coauthors"] = [
                    " ".join(x for x in [a.get("given"), a.get("family")] if x).strip()
                    for a in it.get("author", [])]
            print(f"{key}: {rec['dois'][0]}")
        else:
            print(f"{key}: no DOI found - {e['title'][:56]}")
        rec["s2_ids"] = ["DOI:" + d for d in rec["dois"]]
        out[key] = rec
        time.sleep(0.6)

    # One DOI belongs to one entry; the closer title keeps it, so a journal paper
    # and its poster or preprint do not both claim the same record.
    owner = {}
    for key, v in out.items():
        for d in v["dois"]:
            sc = v.get("_score", 1.0)
            if d not in owner or sc > owner[d][1]:
                owner[d] = (key, sc)
    for key, v in out.items():
        v["dois"] = [d for d in v["dois"] if owner.get(d, (None,))[0] == key]
        v["s2_ids"] = ["DOI:" + d for d in v["dois"]]
        v.pop("_score", None)

    json.dump(out, open(os.path.join(HERE, args.out), "w"), indent=1)
    resolved = sum(1 for v in out.values() if v["dois"])
    patents = sum(1 for v in out.values() if v["patent"])
    print(f"\nwrote {args.out}: {len(out)} entries, {resolved} with a DOI, "
          f"{patents} patents skipped")
    unresolved = [k for k, v in out.items() if not v["dois"] and not v["patent"]]
    if unresolved:
        print("no DOI (add one by hand in the file if you have it):",
              ", ".join(unresolved))


if __name__ == "__main__":
    main()
