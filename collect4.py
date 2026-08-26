"""Fill affiliations for citing papers that still have none, via OpenAlex title search."""
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
HERE = os.path.dirname(os.path.abspath(__file__))
SELECT = ("id,doi,display_name,publication_year,type,cited_by_count,"
          "authorships,primary_location")


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


raw = json.load(open(os.path.join(HERE, "raw.json")))
data = json.load(open(os.path.join(HERE, "data.json")))

todo = sorted({r["title"] for r in data["records"] if not r["institutions"]})
print("citing papers without affiliations:", len(todo))

extra = dict(raw.get("oa_extra_by_title", {}))
hits = 0
for t in todo:
    if t in extra and extra[t].get("authorships"):
        continue
    # quoted phrase search keeps the match tight
    q = urllib.parse.quote('"' + re.sub(r'["\\]', " ", t)[:200] + '"')
    d = get(f"https://api.openalex.org/works?per-page=3&filter=title.search:{q}&select={SELECT}")
    time.sleep(0.3)
    cands = (d or {}).get("results") or []
    if not cands:
        d = get("https://api.openalex.org/works?per-page=3&filter=title.search:"
                + urllib.parse.quote(re.sub(r"[^\w\s-]", " ", t)[:200]) + f"&select={SELECT}")
        time.sleep(0.3)
        cands = (d or {}).get("results") or []
    for w in cands:
        a, b = norm(w.get("display_name")), norm(t)
        if a and b and (a.startswith(b[:40]) or b.startswith(a[:40])):
            insts = [i for au in w.get("authorships", []) for i in (au.get("institutions") or [])]
            if insts:
                extra[t] = w
                hits += 1
                print("  +", len(insts), "inst |", t[:64])
            break

print("newly affiliated:", hits)
raw["oa_extra_by_title"] = extra
json.dump(raw, open(os.path.join(HERE, "raw.json"), "w"))
print("updated raw.json")
