"""Pull citing papers for every resolved Scholar entry, from Semantic Scholar and OpenAlex.

Writes raw_all.json in the same shape build_all.py expects.
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
HERE = os.path.dirname(os.path.abspath(__file__))
S2 = "https://api.semanticscholar.org/graph/v1"
OA = "https://api.openalex.org"

S2_FIELDS = ("title,year,venue,publicationVenue,citationCount,externalIds,"
             "authors,fieldsOfStudy,isInfluential")
OA_SELECT = ("id,doi,display_name,publication_year,type,cited_by_count,"
             "authorships,primary_location")


def get(url, tries=6, pause=8.0, label=""):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(pause * (i + 1))
                continue
            print(f"    HTTP {e.code} {label}")
            return None
        except Exception as e:
            print(f"    {type(e).__name__} {label}")
            time.sleep(pause * (i + 1))
    print(f"    gave up {label}")
    return None


def s2_citations(pid):
    rows, offset = [], 0
    while True:
        u = (f"{S2}/paper/{urllib.parse.quote(pid, safe=':./')}/citations"
             f"?fields={S2_FIELDS}&limit=100&offset={offset}")
        d = get(u, label=pid)
        if not d:
            break
        batch = d.get("data", [])
        rows.extend(batch)
        if len(batch) < 100 or "next" not in d:
            break
        offset = d["next"]
        time.sleep(8)
    time.sleep(8)
    return rows


def oa_citations(wid):
    rows, cursor = [], "*"
    while cursor:
        u = f"{OA}/works?filter=cites:{wid}&per-page=200&cursor={cursor}&select={OA_SELECT}"
        d = get(u, tries=4, pause=3.0, label=wid)
        if not d:
            break
        rows.extend(d.get("results", []))
        cursor = d.get("meta", {}).get("next_cursor")
        if not d.get("results"):
            break
        time.sleep(0.3)
    return rows


def oa_by_dois(dois):
    found = {}
    for i in range(0, len(dois), 40):
        f = "|".join("https://doi.org/" + d for d in dois[i:i + 40])
        u = (f"{OA}/works?per-page=100&filter=doi:"
             + urllib.parse.quote(f, safe="|:/.") + "&select=" + OA_SELECT)
        d = get(u, tries=4, pause=3.0, label="doi batch")
        if d:
            for w in d.get("results", []):
                if w.get("doi"):
                    found[w["doi"].lower().replace("https://doi.org/", "")] = w
        time.sleep(0.3)
    return found


def oa_by_title(title):
    import re
    q = urllib.parse.quote(re.sub(r"[^\w\s-]", " ", title)[:220])
    d = get(f"{OA}/works?per-page=1&filter=title.search:{q}&select={OA_SELECT}",
            tries=3, pause=3.0, label="title")
    if d and d.get("results"):
        return d["results"][0]
    return None


ap = argparse.ArgumentParser()
ap.add_argument("--skip-openalex", action="store_true",
                help="OpenAlex meters requests daily; skip it and fill affiliations later")
ap.add_argument("--out", default="raw_all.json")
ARGS = ap.parse_args()

targets = json.load(open(os.path.join(HERE, "targets_resolved.json")))
papers = []
for key, t in targets.items():
    if t["patent"]:
        print(f"{key}: patent, skipped")
        papers.append({"key": key, "title": t["title"], "venue": t["venue"],
                       "scholar_citations": t["scholar_citations"],
                       "scholar_cluster": t["cluster"], "patent": True,
                       "s2_citing": [], "oa_citing": []})
        continue
    s2_rows = []
    for pid in t.get("s2_ids") or ["DOI:" + d for d in t["dois"]]:
        s2_rows.extend(s2_citations(pid))
    oa_rows = []
    if not ARGS.skip_openalex:
        for wid in t["oa_ids"]:
            oa_rows.extend(oa_citations(wid))
    print(f"{key}: s2={len(s2_rows)} oa={len(oa_rows)} scholar={t['scholar_citations']}")
    papers.append({"key": key, "title": t["title"], "venue": t["venue"],
                   "scholar_citations": t["scholar_citations"],
                   "scholar_cluster": t["cluster"], "patent": False,
                   "s2_citing": s2_rows, "oa_citing": oa_rows})

# affiliations for citing papers OpenAlex did not already return
have = {w["doi"].lower().replace("https://doi.org/", "")
        for p in papers for w in p["oa_citing"] if w.get("doi")}
need_doi, need_title = set(), set()
for p in papers:
    for c in p["s2_citing"]:
        cp = c.get("citingPaper") or {}
        doi = ((cp.get("externalIds") or {}).get("DOI") or "").lower()
        if doi:
            if doi not in have:
                need_doi.add(doi)
        elif cp.get("title"):
            need_title.add(cp["title"])
print("enrich by doi:", len(need_doi), "| by title:", len(need_title))

extra_doi, extra_title = {}, {}
if ARGS.skip_openalex:
    print("  OpenAlex skipped; run enrich_openalex.py once its budget resets")
else:
    extra_doi = oa_by_dois(sorted(need_doi))
    print("  matched by doi:", len(extra_doi))
    for tt in sorted(need_title):
        w = oa_by_title(tt)
        if w:
            extra_title[tt] = w
        time.sleep(0.3)
    print("  matched by title:", len(extra_title))

json.dump({"papers": papers, "oa_extra_by_doi": extra_doi,
           "oa_extra_by_title": extra_title, "oc_resolved_oa": {}},
          open(os.path.join(HERE, "raw_all.json"), "w"))
print("wrote raw_all.json")
