"""Add citing papers from OpenCitations, with metadata from Crossref.

Crossref records are converted to the OpenAlex authorship shape so the build step
needs no special case. Affiliations come from Crossref's author.affiliation, which
is present on some publishers' records and absent on others.
"""
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


def get(url, tries=4, pause=3.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(pause * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(pause * (i + 1))
    return None


def opencitations(doi):
    d = get("https://api.opencitations.net/index/v2/citations/doi:" + doi)
    if not d:
        return []
    out = []
    for row in d:
        for tok in (row.get("citing") or "").split():
            if tok.startswith("doi:"):
                out.append(tok[4:].lower())
    return sorted(set(out))


def as_openalex(doi, m):
    """Crossref message -> the subset of the OpenAlex work shape the build step reads."""
    authorships = []
    for a in m.get("author", []):
        name = " ".join(x for x in [a.get("given"), a.get("family")] if x).strip()
        if not name:
            continue
        affs = [f["name"] for f in (a.get("affiliation") or []) if f.get("name")]
        authorships.append({
            "author": {"display_name": name},
            "institutions": [{"display_name": f, "country_code": "", "ror": ""} for f in affs],
            "raw_affiliation_strings": affs,
        })
    return {
        "id": "crossref:" + doi,
        "doi": "https://doi.org/" + doi,
        "display_name": (m.get("title") or [""])[0],
        "publication_year": (m.get("issued", {}).get("date-parts") or [[None]])[0][0],
        "type": m.get("type") or "",
        "cited_by_count": m.get("is-referenced-by-count") or 0,
        "primary_location": {"source": {"display_name": (m.get("container-title") or [""])[0]}},
        "authorships": authorships,
        "_source": "Crossref",
    }


targets = json.load(open(os.path.join(HERE, "targets_resolved.json")))
raw = json.load(open(os.path.join(HERE, "raw_all.json")))
by_key = {p["key"]: p for p in raw["papers"]}

# citing DOIs already held from Semantic Scholar, per target
known = {}
for p in raw["papers"]:
    s = set()
    for c in p["s2_citing"]:
        doi = ((c.get("citingPaper") or {}).get("externalIds") or {}).get("DOI")
        if doi:
            s.add(doi.lower())
    for w in p["oa_citing"]:
        if w.get("doi"):
            s.add(w["doi"].lower().replace("https://doi.org/", ""))
    known[p["key"]] = s

wanted = {}
for key, t in targets.items():
    if t["patent"] or not t["dois"]:
        continue
    fresh = set()
    for d in t["dois"]:
        got = opencitations(d)
        print(f"{key}: opencitations {d} -> {len(got)}")
        fresh |= {x for x in got if x not in known[key]}
        time.sleep(0.8)
    if fresh:
        wanted[key] = sorted(fresh)
        print(f"  {len(fresh)} new")

all_dois = sorted({d for v in wanted.values() for d in v})
print("new citing DOIs to fetch from Crossref:", len(all_dois))

meta = {}
for d in all_dois:
    r = get("https://api.crossref.org/works/" + urllib.parse.quote(d, safe="/."))
    if r and r.get("message"):
        meta[d] = as_openalex(d, r["message"])
    time.sleep(0.4)
print("Crossref metadata retrieved:", len(meta))
with_aff = sum(1 for w in meta.values()
               if any(a["institutions"] for a in w["authorships"]))
print("  of which carry affiliations:", with_aff)

added = 0
for key, dois in wanted.items():
    for d in dois:
        if d in meta:
            by_key[key]["oa_citing"].append(meta[d])
            added += 1
print("records added:", added)

json.dump(raw, open(os.path.join(HERE, "raw_all.json"), "w"))
print("updated raw_all.json")
