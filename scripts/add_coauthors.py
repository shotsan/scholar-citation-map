"""Add the co-author list to each target in an existing targets and raw file.

setup_profile.py records co-authors when it resolves a profile. This backfills them
for target files made before that, so self-citation marking works without
re-collecting the citing papers.
"""
import argparse
import json
import os
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

ap = argparse.ArgumentParser()
ap.add_argument("--targets", default="targets_resolved.json")
ap.add_argument("--raw", nargs="*", default=["raw_all.json", "raw.json"])
ARGS = ap.parse_args()


def get(url, tries=5, pause=8.0):
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


def crossref_authors(doi):
    d = get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/."))
    m = (d or {}).get("message") or {}
    return [" ".join(x for x in [a.get("given"), a.get("family")] if x).strip()
            for a in m.get("author", [])]


def s2_authors(pid):
    d = get(f"https://api.semanticscholar.org/graph/v1/paper/"
            f"{urllib.parse.quote(pid, safe=':./')}?fields=authors")
    return [a["name"] for a in (d or {}).get("authors") or [] if a.get("name")]


targets = json.load(open(os.path.join(HERE, ARGS.targets)))
for key, t in targets.items():
    if t.get("coauthors"):
        continue
    names = []
    for doi in t.get("dois") or []:
        names = crossref_authors(doi)
        if names:
            break
        time.sleep(0.4)
    if not names:
        # Papers Crossref does not carry, such as NeurIPS proceedings and preprints.
        for pid in t.get("s2_ids") or []:
            if pid.startswith("DOI:"):
                continue
            names = s2_authors(pid)
            if names:
                break
            time.sleep(8)
    t["coauthors"] = names
    print(f"{key}: {len(names)} co-authors {names[:3]}")

json.dump(targets, open(os.path.join(HERE, ARGS.targets), "w"), indent=1)
print("updated", ARGS.targets)

# Match raw-file papers to targets on key first, then on title.
by_key = {k: v.get("coauthors") or [] for k, v in targets.items()}
by_title = {(v["title"] or "").lower(): v.get("coauthors") or []
            for v in targets.values()}
for name in ARGS.raw:
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        print("skip", name, "(not present)")
        continue
    raw = json.load(open(path))
    n = 0
    for p in raw["papers"]:
        ca = by_key.get(p["key"]) or by_title.get((p.get("title") or "").lower()) or []
        if ca:
            p["coauthors"] = ca
            n += 1
    json.dump(raw, open(path, "w"))
    print(f"{name}: co-authors set on {n} of {len(raw['papers'])} papers")
