"""Resolve each Scholar entry to OpenAlex work IDs and a DOI, so citations can be pulled.

Matches are accepted only when the OpenAlex title agrees with the Scholar title, to
avoid the wrong-DOI mistakes that guessing produces.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from all_targets import SCHOLAR

# Crossref and OpenAlex ask for a contact address in the User-Agent to get
# their faster "polite pool". Set CITATION_MAP_EMAIL to your own address.
UA = "citation-map/1.0 (mailto:%s)" % os.environ.get(
    "CITATION_MAP_EMAIL", "anonymous@example.com")
# Files are read and written relative to the current directory, so run the
# scripts from wherever you want the output to land.
HERE = os.getcwd()
SELECT = "id,doi,display_name,publication_year,type,cited_by_count"


def get(url, tries=4, pause=3.0):
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


def agrees(a, b):
    x, y = norm(a), norm(b)
    if not x or not y:
        return False
    return x.startswith(y[:35]) or y.startswith(x[:35])


out = {}
for key, title, venue, cites, cluster, is_patent in SCHOLAR:
    if is_patent:
        print(f"{key}: patent, not indexed by OpenAlex or Semantic Scholar")
        out[key] = {"title": title, "venue": venue, "scholar_citations": cites,
                    "cluster": cluster, "patent": True, "oa_ids": [], "dois": []}
        continue
    q = urllib.parse.quote(re.sub(r"[^\w\s-]", " ", title)[:220])
    d = get(f"https://api.openalex.org/works?per-page=8&filter=title.search:{q}&select={SELECT}")
    time.sleep(0.3)
    hits = [w for w in (d or {}).get("results", []) if agrees(w.get("display_name"), title)]
    oa_ids = [w["id"].split("/")[-1] for w in hits]
    dois = [(w.get("doi") or "").replace("https://doi.org/", "") for w in hits if w.get("doi")]
    print(f"{key}: {len(hits)} OpenAlex record(s) -> {oa_ids}")
    for w in hits:
        print(f"    {w['id'].split('/')[-1]} {w.get('cited_by_count')} {w.get('type')} "
              f"| {(w.get('display_name') or '')[:60]}")
    out[key] = {"title": title, "venue": venue, "scholar_citations": cites,
                "cluster": cluster, "patent": False, "oa_ids": oa_ids, "dois": dois}

json.dump(out, open(os.path.join(HERE, "targets_resolved.json"), "w"), indent=1)
print("\nwrote targets_resolved.json")
missing = [k for k, v in out.items() if not v["patent"] and not v["oa_ids"]]
print("no OpenAlex match:", missing)
