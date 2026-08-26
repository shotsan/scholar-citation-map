"""Add OpenCitations citing DOIs to raw.json, resolved through OpenAlex for affiliations."""
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
OA_SELECT = ("id,doi,display_name,publication_year,type,cited_by_count,"
             "authorships,primary_location")

# DOIs for each target, including preprint versions Scholar merges into one entry.
TARGET_DOIS = {
    "neurwin": ["10.48550/arXiv.2110.02128"],
    "nbiot_access": ["10.1109/ACCESS.2020.3026077"],
    # The SIGCOMM'20 poster (10.1145/3405837.3411374) is a separate Scholar entry
    # with its own count, so it is not merged here.
    "beamsurfer": ["10.1109/TWC.2022.3171189", "10.48550/arXiv.2110.01744"],
    "nbiot_pimrc": ["10.1109/PIMRC.2018.8580749"],
}


def get(url, tries=5, pause=4.0, follow=True):
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
    u = "https://api.opencitations.net/index/v2/citations/doi:" + doi
    d = get(u)
    if not d:
        return []
    out = []
    for row in d:
        # "citing" looks like: "doi:10.1109/x omid:br/123"
        for tok in (row.get("citing") or "").split():
            if tok.startswith("doi:"):
                out.append(tok[4:].lower())
    return sorted(set(out))


def oa_by_dois(dois):
    found = {}
    for i in range(0, len(dois), 40):
        chunk = dois[i:i + 40]
        f = "|".join("https://doi.org/" + d for d in chunk)
        u = ("https://api.openalex.org/works?per-page=100&filter=doi:"
             + urllib.parse.quote(f, safe="|:/.") + "&select=" + OA_SELECT)
        d = get(u)
        if d:
            for w in d.get("results", []):
                if w.get("doi"):
                    found[w["doi"].lower().replace("https://doi.org/", "")] = w
        time.sleep(0.3)
    return found


def crossref(doi):
    d = get("https://api.crossref.org/works/" + doi)
    if not d:
        return None
    return d.get("message")


raw = json.load(open(os.path.join(HERE, "raw.json")))

# every citing DOI already known, so only new ones get fetched
known = set()
for p in raw["papers"]:
    for w in p["oa_citing"]:
        if w.get("doi"):
            known.add(w["doi"].lower().replace("https://doi.org/", ""))
    for c in p["s2_citing"]:
        doi = ((c.get("citingPaper") or {}).get("externalIds") or {}).get("DOI")
        if doi:
            known.add(doi.lower())
print("already known citing DOIs:", len(known))

oc_new = {}
for p in raw["papers"]:
    dois = []
    for d in TARGET_DOIS.get(p["key"], []):
        got = opencitations(d)
        print(f"  opencitations {d} -> {len(got)}")
        dois.extend(got)
        time.sleep(1.0)
    fresh = sorted({d for d in dois if d not in known})
    print(f"  {p['key']}: {len(fresh)} new from OpenCitations")
    oc_new[p["key"]] = fresh

all_new = sorted({d for v in oc_new.values() for d in v})
print("new DOIs total:", len(all_new))
resolved = oa_by_dois(all_new)
print("resolved in OpenAlex:", len(resolved))

# Crossref fallback for anything OpenAlex does not have
cr = {}
for d in all_new:
    if d not in resolved:
        m = crossref(d)
        if m:
            cr[d] = {
                "title": (m.get("title") or [""])[0],
                "year": (m.get("issued", {}).get("date-parts") or [[None]])[0][0],
                "venue": (m.get("container-title") or [""])[0],
                "authors": [" ".join(x for x in [a.get("given"), a.get("family")] if x)
                            for a in m.get("author", [])],
                "affiliations": [aff.get("name") for a in m.get("author", [])
                                 for aff in (a.get("affiliation") or []) if aff.get("name")],
            }
        time.sleep(0.4)
print("resolved in Crossref:", len(cr))

raw["opencitations_new"] = oc_new
raw["oc_resolved_oa"] = resolved
raw["oc_resolved_crossref"] = cr
json.dump(raw, open(os.path.join(HERE, "raw.json"), "w"))
print("updated raw.json")
