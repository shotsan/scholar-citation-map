"""Fill affiliations into raw_all.json from OpenAlex.

OpenAlex meters requests daily, so DOIs go up in batches of 40 and title lookups,
which cost one request each, are capped.
"""
import argparse
import json
import os
import re
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
SELECT = ("id,doi,display_name,publication_year,type,cited_by_count,"
          "authorships,primary_location")

ap = argparse.ArgumentParser()
ap.add_argument("--raw", default="raw_all.json")
ap.add_argument("--max-title-lookups", type=int, default=60)
ARGS = ap.parse_args()


def get(url, tries=3, pause=4.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            if "Rate limit exceeded" in body or "Insufficient budget" in body:
                print("  OpenAlex budget exhausted; resets at midnight UTC")
                return "BUDGET"
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(pause * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(pause * (i + 1))
    return None


raw = json.load(open(os.path.join(HERE, ARGS.raw)))
extra_doi = raw.get("oa_extra_by_doi") or {}
extra_title = raw.get("oa_extra_by_title") or {}

need_doi, need_title = set(), set()
for p in raw["papers"]:
    for c in p["s2_citing"]:
        cp = c.get("citingPaper") or {}
        doi = ((cp.get("externalIds") or {}).get("DOI") or "").lower()
        if doi:
            if doi not in extra_doi:
                need_doi.add(doi)
        elif cp.get("title") and cp["title"] not in extra_title:
            need_title.add(cp["title"])
print(f"need affiliations: {len(need_doi)} by doi, {len(need_title)} by title")

dois = sorted(need_doi)
for i in range(0, len(dois), 40):
    chunk = dois[i:i + 40]
    f = "|".join("https://doi.org/" + d for d in chunk)
    u = ("https://api.openalex.org/works?per-page=100&filter=doi:"
         + urllib.parse.quote(f, safe="|:/.") + "&select=" + SELECT)
    d = get(u)
    if d == "BUDGET":
        break
    if d:
        for w in d.get("results", []):
            if w.get("doi"):
                extra_doi[w["doi"].lower().replace("https://doi.org/", "")] = w
    print(f"  doi batch {i // 40 + 1}: have {len(extra_doi)}")
    time.sleep(0.4)

for n, tt in enumerate(sorted(need_title)):
    if n >= ARGS.max_title_lookups:
        print(f"  stopped after {n} title lookups")
        break
    q = urllib.parse.quote(re.sub(r"[^\w\s-]", " ", tt)[:220])
    d = get(f"https://api.openalex.org/works?per-page=1&filter=title.search:{q}&select={SELECT}")
    if d == "BUDGET":
        break
    if d and d.get("results"):
        extra_title[tt] = d["results"][0]
    time.sleep(0.4)

raw["oa_extra_by_doi"] = extra_doi
raw["oa_extra_by_title"] = extra_title
json.dump(raw, open(os.path.join(HERE, ARGS.raw), "w"))
print(f"wrote {ARGS.raw}: {len(extra_doi)} by doi, {len(extra_title)} by title")
