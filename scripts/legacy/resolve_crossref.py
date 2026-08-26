"""Resolve each Scholar entry to a DOI via Crossref, accepting only agreeing titles."""
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


def similarity(a, b):
    """0 when the titles disagree, else the prefix overlap as a share of the longer."""
    x, y = norm(a), norm(b)
    if not x or not y:
        return 0.0
    n = 0
    for cx, cy in zip(x, y):
        if cx != cy:
            break
        n += 1
    # A short generic title such as "Seeing the Unseen" prefixes several unrelated
    # works, so a match needs real length as well as a high share.
    if n < 25:
        return 0.0
    return n / max(len(x), len(y))


def agrees(a, b):
    return similarity(a, b) >= 0.55


out = {}
for key, title, venue, cites, cluster, is_patent in SCHOLAR:
    entry = {"title": title, "venue": venue, "scholar_citations": cites,
             "cluster": cluster, "patent": is_patent, "oa_ids": [], "dois": []}
    if is_patent:
        print(f"{key}: patent, not indexed by Crossref")
        out[key] = entry
        continue
    u = ("https://api.crossref.org/works?rows=6&select=DOI,title,container-title,"
         "issued,is-referenced-by-count&query.bibliographic="
         + urllib.parse.quote(title))
    d = get(u)
    items = ((d or {}).get("message") or {}).get("items") or []
    hits = [it for it in items if agrees((it.get("title") or [""])[0], title)]
    entry["dois"] = [it["DOI"].lower() for it in hits]
    entry["scores"] = {it["DOI"].lower(): similarity((it.get("title") or [""])[0], title)
                       for it in hits}
    print(f"{key}: {len(hits)} DOI(s)")
    for it in hits:
        print(f"    {it['DOI']} refs={it.get('is-referenced-by-count')} "
              f"| {(it.get('container-title') or [''])[0][:38]}")
    out[key] = entry
    time.sleep(0.6)

# A DOI belongs to one Scholar entry. Where two entries claim the same DOI, the
# closer title keeps it, so the journal paper and its poster stay separate.
owner = {}
for key, v in out.items():
    for doi, sc in v.get("scores", {}).items():
        if doi not in owner or sc > owner[doi][1]:
            owner[doi] = (key, sc)
for key, v in out.items():
    v["dois"] = [d for d in v["dois"] if owner.get(d, (None,))[0] == key]
    v.pop("scores", None)

# Entries the title search cannot place, each identifier checked against Crossref or
# Semantic Scholar directly. The two posters and the workshop paper are stored under
# short titles ("BeamSurfer", "Terra"), which the length floor above rejects.
FALLBACK = {
    "neurwin": {"s2_ids": ["10e7ae23fc58bfdb829bfa5694c59f2d7fb8a275"],
                "oa_ids": ["W3132046977"], "dois": []},
    "ground_reflections": {"s2_ids": ["arXiv:2110.13884"], "oa_ids": [], "dois": []},
    "beamsurfer_poster": {"dois": ["10.1145/3405837.3411374"], "oa_ids": []},
    "terra_poster": {"dois": ["10.1145/3546037.3546063"], "oa_ids": []},
    "reveal_s3": {"dois": ["10.1145/3615591.3615678"], "oa_ids": []},
}
for key, v in FALLBACK.items():
    out[key].update(v)
for key, v in out.items():
    v.setdefault("s2_ids", ["DOI:" + d for d in v["dois"]])

json.dump(out, open(os.path.join(HERE, "targets_resolved.json"), "w"), indent=1)
print("\nwrote targets_resolved.json")
print("no DOI:", [k for k, v in out.items() if not v["patent"] and not v["dois"]])
