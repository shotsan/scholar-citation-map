"""Collect citing papers, authors and institutions for Santosh Ganji's top-cited papers.

Citing papers come from Semantic Scholar and OpenAlex, unioned by DOI or title.
Affiliations come from OpenAlex authorships.
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
OUT = os.getcwd()
S2 = "https://api.semanticscholar.org/graph/v1"
OA = "https://api.openalex.org"

# The /paper/search endpoint is heavily throttled, so papers are addressed by id.
TARGETS = [
    {
        "key": "neurwin",
        "title": "NeurWIN: Neural Whittle Index Network for Restless Bandits via Deep RL",
        "venue": "NeurIPS 2021",
        "scholar_citations": 74,
        "scholar_cluster": "15114473685997353079",
        "s2_ids": ["10e7ae23fc58bfdb829bfa5694c59f2d7fb8a275"],
        "oa_ids": ["W3132046977"],
    },
    {
        "key": "nbiot_access",
        "title": "Scheduling and Decoding of Downlink Control Channel in 3GPP Narrowband-IoT",
        "venue": "IEEE Access 2020",
        "scholar_citations": 16,
        "scholar_cluster": "12445178730793979866",
        "s2_ids": ["DOI:10.1109/ACCESS.2020.3026077"],
        "oa_ids": ["W3089319993"],
    },
    {
        "key": "beamsurfer",
        "title": "BeamSurfer: Minimalist Beam Management of Mobile mm-wave Devices",
        "venue": "IEEE TWC 2022",
        "scholar_citations": 13,
        "scholar_cluster": "5531327131859727774",
        "s2_ids": ["DOI:10.1109/TWC.2022.3171189", "arXiv:2110.01744"],
        "oa_ids": ["W3201844557", "W4306403163", "W3200087701"],
    },
    {
        "key": "nbiot_pimrc",
        "title": "Downlink Control Channel Scheduling for 3GPP Narrowband-IoT",
        "venue": "IEEE PIMRC 2018",
        "scholar_citations": 13,
        "scholar_cluster": "5088929058679659133",
        "s2_ids": ["DOI:10.1109/PIMRC.2018.8580749"],
        "oa_ids": ["W2907818434"],
    },
]


def get(url, tries=8, pause=8.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                print("    retry", e.code, int(pause * (i + 1)), "s")
                time.sleep(pause * (i + 1))
                continue
            print("    HTTP", e.code, url[:90])
            return None
        except Exception as e:
            print("    ERR", type(e).__name__)
            time.sleep(pause * (i + 1))
    print("    GIVE UP", url[:110])
    return None


S2_FIELDS = ("title,year,venue,publicationVenue,citationCount,externalIds,"
             "authors,fieldsOfStudy,isInfluential")


def s2_citations(pid):
    rows, offset = [], 0
    while True:
        u = f"{S2}/paper/{urllib.parse.quote(pid, safe=':./')}/citations?fields={S2_FIELDS}&limit=100&offset={offset}"
        d = get(u)
        if not d:
            break
        batch = d.get("data", [])
        rows.extend(batch)
        print(f"    s2 {pid[:30]} offset {offset} -> {len(batch)}")
        if len(batch) < 100 or "next" not in d:
            break
        offset = d["next"]
        time.sleep(8)
    time.sleep(8)
    return rows


OA_SELECT = ("id,doi,display_name,publication_year,type,cited_by_count,"
             "authorships,primary_location,referenced_works")


def oa_citations(wid):
    rows, cursor = [], "*"
    while cursor:
        u = f"{OA}/works?filter=cites:{wid}&per-page=200&cursor={cursor}&select={OA_SELECT}"
        d = get(u, tries=4, pause=3.0)
        if not d:
            break
        rows.extend(d.get("results", []))
        cursor = d.get("meta", {}).get("next_cursor")
        if not d.get("results"):
            break
        time.sleep(0.3)
    print(f"    oa {wid} -> {len(rows)}")
    return rows


def oa_by_dois(dois):
    found = {}
    for i in range(0, len(dois), 40):
        chunk = dois[i:i + 40]
        f = "|".join("https://doi.org/" + d for d in chunk)
        u = (f"{OA}/works?per-page=100&filter=doi:"
             + urllib.parse.quote(f, safe="|:/.") + f"&select={OA_SELECT}")
        d = get(u, tries=4, pause=3.0)
        if d:
            for w in d.get("results", []):
                if w.get("doi"):
                    found[w["doi"].lower().replace("https://doi.org/", "")] = w
        time.sleep(0.3)
    return found


def oa_by_title(title):
    q = urllib.parse.quote(title[:250])
    u = f"{OA}/works?per-page=1&filter=title.search:{q}&select={OA_SELECT}"
    d = get(u, tries=3, pause=3.0)
    if d and d.get("results"):
        return d["results"][0]
    return None


def main():
    papers = []
    for t in TARGETS:
        print("===", t["key"])
        t = dict(t)
        s2_rows = []
        for pid in t["s2_ids"]:
            s2_rows.extend(s2_citations(pid))
        oa_rows = []
        for wid in t["oa_ids"]:
            oa_rows.extend(oa_citations(wid))
        t["s2_citing"] = s2_rows
        t["oa_citing"] = oa_rows
        print(f"  totals: s2={len(s2_rows)} oa={len(oa_rows)} (scholar says {t['scholar_citations']})")
        papers.append(t)

    # affiliations for every S2 citing paper that OpenAlex did not already return
    have = set()
    for p in papers:
        for w in p["oa_citing"]:
            if w.get("doi"):
                have.add(w["doi"].lower().replace("https://doi.org/", ""))

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

    enriched = oa_by_dois(sorted(need_doi))
    print("  matched by doi:", len(enriched))
    by_title = {}
    for tt in sorted(need_title):
        w = oa_by_title(tt)
        if w:
            by_title[tt] = w
        time.sleep(0.3)
    print("  matched by title:", len(by_title))

    out = {"papers": papers, "oa_extra_by_doi": enriched, "oa_extra_by_title": by_title}
    with open(os.path.join(OUT, "raw.json"), "w") as f:
        json.dump(out, f)
    print("wrote raw.json")


if __name__ == "__main__":
    main()
