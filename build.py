"""Turn raw.json into citing-paper, author and institution tables plus citation graphs."""
import argparse
import csv
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

HERE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser()
ap.add_argument("--raw", default="raw.json")
ap.add_argument("--prefix", default="")
ap.add_argument("--title", default="Santosh Ganji's four most-cited papers")
ARGS = ap.parse_args()
RAW = json.load(open(os.path.join(HERE, ARGS.raw)))
RAW["papers"] = [p for p in RAW["papers"] if not p.get("patent")]

def short_label(p):
    head = re.split(r"[:\u2014]", p["title"])[0].strip()
    return f"{head[:34]} ({p.get('venue', '')})"

SHORT = {p["key"]: short_label(p) for p in RAW["papers"]}
PALETTE = ["#c0392b", "#2471a3", "#1e8449", "#b9770e", "#7d3c98", "#117a65",
           "#a93226", "#1f618d", "#af601a", "#4a235a", "#0e6251", "#7e5109",
           "#512e5f", "#154360", "#6e2c00", "#1b4f72", "#78281f", "#0b5345",
           "#5b2c6f", "#873600"]
TCOL = {p["key"]: PALETTE[i % len(PALETTE)] for i, p in enumerate(RAW["papers"])}

# Co-authors on the four papers, used to mark self-citations. Several appear under
# more than one name form, and akey() keys on surname, so each form is listed.
COAUTHORS = [
    "Santosh Ganji", "Venkata Siva Santosh Ganji", "Ganji Santosh", "G Santosh",
    "P R Kumar", "Panganamala Kumar",
    "Khaled Nakhleh", "Ping-Chun Hsieh", "I-Hong Hou", "Srinivas Shakkottai",
    "Pavan Reddy Manne", "M Pavan Reddy", "Abhinav Kumar", "Kiran Kuchi",
    "Tzu-Hsiang Lin", "Franklin Espinal",
    # co-authors on the remaining profile entries
    "Bharadwaj Satchidanandan", "Sinan Yau", "Ashraf Aziz", "Amal Ekbal",
    "Nikhil Kundargi", "Jim McCoy", "Rohit Sonigra", "Jaewon Kim",
    "Hosseinali Dureppagari", "Ujwal Dinesha", "Rui Wu", "Woo-Hyun Ko",
    "Nikhil Dhar", "Gopal Vasudevan", "Abhijit Bera",
]

# Two OpenAlex affiliation mappings are wrong on these papers, checked against the
# raw_affiliation_strings: "Harvard University" carries the ROR of Harvard University
# Press, and "ARMMAN" carries that of the American Rock Mechanics Association.
INSTITUTION_ALIASES = {
    "Harvard University Press": "Harvard University",
    "American Rock Mechanics Association": "ARMMAN",
}


ORG_WORDS = ("university", "institute", "academy", "college", "school", "laboratory",
             "centre", "center", "bureau", "ministry", "hospital", "polytechnic")


def tidy_affiliation(s):
    """Reduce a Crossref postal affiliation to the organisation name.

    Crossref stores the author's whole address, so "Department of Communications
    Engineering, Feng Chia University, Taichung 407, Taiwan" becomes the university.
    """
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) < 2:
        return s.strip()
    ranked = sorted(
        (p for p in parts if any(w in p.lower() for w in ORG_WORDS)),
        key=lambda p: (0 if "university" in p.lower() or "institute" in p.lower() else 1,
                       parts.index(p)))
    return ranked[0] if ranked else max(parts, key=len)


def resolve_inst(name, raw_strings):
    name = INSTITUTION_ALIASES.get(name, name)
    # Only Crossref-sourced names carry an address; OpenAlex names are already clean.
    if name.count(",") >= 2:
        name = tidy_affiliation(name)
    return name


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())[:90]


def akey(name):
    """Surname + first initial, so 'M. Tambe' and 'Milind Tambe' collapse to one key."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z\s\-']", " ", s).strip()
    parts = [p for p in re.split(r"\s+", s) if p]
    if not parts:
        return ""
    last = parts[-1].lower()
    first = parts[0][0].lower() if len(parts) > 1 else ""
    return f"{last}|{first}"


COAUTHOR_KEYS = {akey(a) for a in COAUTHORS}


def oa_lookup(doi, title):
    """Candidate OpenAlex records, preferring one that actually carries affiliations."""
    cands = []
    for bag in ("oa_extra_by_doi", "oc_resolved_oa"):
        if doi and doi.lower() in RAW.get(bag, {}):
            cands.append(RAW[bag][doi.lower()])
    if title and title in RAW.get("oa_extra_by_title", {}):
        cands.append(RAW["oa_extra_by_title"][title])
    for w in cands:
        if insts_of(w):
            return w
    return cands[0] if cands else None


def insts_of(work):
    out = []
    for a in work.get("authorships", []):
        raws = a.get("raw_affiliation_strings") or []
        for i in a.get("institutions", []) or []:
            nm = i.get("display_name")
            if nm:
                out.append((resolve_inst(nm, raws), i.get("country_code") or "",
                            i.get("ror") or ""))
    return out


def author_insts(work):
    """Institutions per author, so an author is not credited with the whole paper's list."""
    out = defaultdict(set)
    for a in work.get("authorships", []):
        nm = (a.get("author") or {}).get("display_name")
        if not nm:
            continue
        raws = a.get("raw_affiliation_strings") or []
        for i in a.get("institutions", []) or []:
            if i.get("display_name"):
                out[nm].add(resolve_inst(i["display_name"], raws))
    return {k: sorted(v) for k, v in out.items()}


# ---------------------------------------------------------------- union
records = []
for p in RAW["papers"]:
    seen = {}

    def put(key, row):
        old = seen.get(key)
        if old is None:
            seen[key] = row
            return
        if len(row["authors"]) > len(old["authors"]):
            old["authors"] = row["authors"]
        if row["institutions"] and not old["institutions"]:
            old["institutions"] = row["institutions"]
        for k, v in row.get("ainsts", {}).items():
            old.setdefault("ainsts", {}).setdefault(k, [])
            old["ainsts"][k] = sorted(set(old["ainsts"][k]) | set(v))
        old["sources"] = sorted(set(old["sources"]) | set(row["sources"]))
        old["doi"] = old["doi"] or row["doi"]
        old["venue"] = old["venue"] or row["venue"]
        old["cited_by"] = max(old["cited_by"], row["cited_by"])

    for w in p["oa_citing"]:
        auths = [(a.get("author") or {}).get("display_name") for a in w.get("authorships", [])]
        insts, ainsts = insts_of(w), author_insts(w)
        if not insts:
            alt = oa_lookup((w.get("doi") or "").replace("https://doi.org/", ""),
                            w.get("display_name"))
            if alt:
                insts, ainsts = insts_of(alt), author_insts(alt)
        put(norm_title(w.get("display_name")), {
            "target": p["key"],
            "title": w.get("display_name") or "",
            "year": w.get("publication_year") or "",
            "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or "",
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "cited_by": w.get("cited_by_count") or 0,
            "authors": [a for a in auths if a],
            "institutions": insts,
            "ainsts": ainsts,
            "sources": [w.get("_source", "OpenAlex")],
        })

    for c in p["s2_citing"]:
        cp = c.get("citingPaper") or {}
        if not cp.get("title"):
            continue
        doi = ((cp.get("externalIds") or {}).get("DOI") or "")
        auths = [a.get("name") for a in (cp.get("authors") or []) if a.get("name")]
        w = oa_lookup(doi, cp["title"])
        insts = insts_of(w) if w else []
        ainsts = author_insts(w) if w else {}
        if w and not auths:
            auths = [(a.get("author") or {}).get("display_name") for a in w.get("authorships", [])]
            auths = [a for a in auths if a]
        put(norm_title(cp["title"]), {
            "target": p["key"],
            "title": cp["title"],
            "year": cp.get("year") or "",
            "venue": cp.get("venue") or ((cp.get("publicationVenue") or {}) or {}).get("name") or "",
            "doi": doi,
            "cited_by": cp.get("citationCount") or 0,
            "authors": auths,
            "institutions": insts,
            "ainsts": ainsts,
            "sources": ["SemanticScholar"],
        })

    # OpenAlex sometimes stores a truncated title ("Terra" for "Terra: blockage
    # resilience..."), so keys that prefix a longer key are folded into it.
    keys = sorted(seen, key=len)
    for i, short in enumerate(keys):
        if short not in seen or len(short) < 5:
            continue
        for long in keys[i + 1:]:
            if long in seen and long.startswith(short):
                put(long, seen.pop(short))
                break

    records.extend(seen.values())

for r in records:
    r["self_citation"] = any(akey(a) in COAUTHOR_KEYS for a in r["authors"])

print("(cited paper, citing paper) pairs:", len(records))
print("distinct citing papers:", len({norm_title(r['title']) for r in records}))
print("self-citations among them:", sum(1 for r in records if r["self_citation"]))

# canonical display name per author key: longest spelling seen
name_forms = defaultdict(Counter)
for r in records:
    for a in r["authors"]:
        k = akey(a)
        if k:
            name_forms[k][a] += 1
canon = {k: max(v, key=lambda n: (len(n), v[n])) for k, v in name_forms.items()}
print("distinct author keys:", len(canon))


# ---------------------------------------------------------------- tables
def write(name, header, rows):
    name = ARGS.prefix + name
    with open(os.path.join(HERE, name), "w", newline="") as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)
    print("wrote", name, len(rows), "rows")


rows = []
for r in sorted(records, key=lambda x: (x["target"], -(x["cited_by"] or 0))):
    rows.append([SHORT[r["target"]], r["title"], r["year"], r["venue"], r["doi"],
                 r["cited_by"], "yes" if r["self_citation"] else "no",
                 "; ".join(r["authors"]),
                 "; ".join(sorted({i[0] for i in r["institutions"]})),
                 "; ".join(sorted({i[1] for i in r["institutions"] if i[1]})),
                 "+".join(r["sources"])])
write("citing_papers.csv",
      ["cited_paper", "citing_title", "year", "venue", "doi", "citing_paper_citations",
       "self_citation", "citing_authors", "institutions", "countries", "source"], rows)

auth_papers, auth_targets, auth_inst, auth_self = (defaultdict(set), defaultdict(set),
                                                   defaultdict(set), {})
for r in records:
    for a in r["authors"]:
        k = akey(a)
        if not k:
            continue
        auth_papers[k].add(norm_title(r["title"]))
        auth_targets[k].add(SHORT[r["target"]])
        for nm in r.get("ainsts", {}).get(a, []):
            auth_inst[k].add(nm)
        auth_self[k] = k in COAUTHOR_KEYS
write("citing_authors.csv",
      ["citing_author", "citing_papers", "is_ganji_coauthor",
       "cites_which_ganji_papers", "own_institutions"],
      [[canon[k], len(auth_papers[k]), "yes" if auth_self.get(k) else "no",
        "; ".join(sorted(auth_targets[k])), "; ".join(sorted(auth_inst[k]))]
       for k in sorted(auth_papers, key=lambda x: (-len(auth_papers[x]), canon[x]))])

inst_papers, inst_targets, inst_authors = defaultdict(set), defaultdict(set), defaultdict(set)
inst_country, inst_ror = {}, {}
for r in records:
    for nm, cc, ror in r["institutions"]:
        inst_papers[nm].add(norm_title(r["title"]))
        inst_country[nm] = cc
        inst_ror[nm] = ror
        inst_targets[nm].add(SHORT[r["target"]])
        for a in r["authors"]:
            if akey(a) and nm in r.get("ainsts", {}).get(a, []):
                inst_authors[nm].add(canon[akey(a)])
write("citing_institutions.csv",
      ["institution", "country", "citing_papers", "authors_on_those_papers",
       "cites_which_ganji_papers", "ror"],
      [[nm, inst_country.get(nm, ""), len(inst_papers[nm]), len(inst_authors[nm]),
        "; ".join(sorted(inst_targets[nm])), inst_ror.get(nm, "")]
       for nm in sorted(inst_papers, key=lambda x: (-len(inst_papers[x]), x))])

cc_count = Counter()
for nm, ps in inst_papers.items():
    if inst_country.get(nm):
        cc_count[inst_country[nm]] += len(ps)
write("citing_countries.csv", ["country", "institution_to_paper_links"],
      [[k, v] for k, v in cc_count.most_common()])


# ---------------------------------------------------------------- graphs
def draw(G, path, title, color, size, figsize=(20, 15), k=0.55):
    path = os.path.join(os.path.dirname(path), ARGS.prefix + os.path.basename(path))
    pos = nx.spring_layout(G, k=k, iterations=240, seed=7)
    plt.figure(figsize=figsize)
    nx.draw_networkx_edges(G, pos, alpha=0.22, width=0.7, edge_color="#8a8f98")
    ns = list(G.nodes())
    nx.draw_networkx_nodes(G, pos, nodelist=ns, node_color=[color(n) for n in ns],
                           node_size=[size(n) for n in ns],
                           linewidths=0.6, edgecolors="white")
    nx.draw_networkx_labels(
        G, pos, {n: G.nodes[n].get("label", n) for n in ns if G.nodes[n].get("show_label")},
        font_size=8)
    plt.title(title, fontsize=15)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print("wrote", os.path.basename(path))


def save(G, stem):
    stem = ARGS.prefix + stem
    nx.write_graphml(G, os.path.join(HERE, stem + ".graphml"))
    nx.write_gexf(G, os.path.join(HERE, stem + ".gexf"))


def key_of(label):
    return next(k for k, v in SHORT.items() if v == label)


G = nx.DiGraph()
for k_, lbl in SHORT.items():
    G.add_node("T:" + k_, label=lbl, kind="ganji_paper", show_label=True)
for r in records:
    n = "P:" + norm_title(r["title"])
    G.add_node(n, label=r["title"][:70], kind="citing_paper", show_label=False,
               year=str(r["year"]), venue=r["venue"][:70], cited_by=r["cited_by"],
               self_citation=str(r["self_citation"]))
    G.add_edge(n, "T:" + r["target"])
save(G, "graph_papers")
draw(G, os.path.join(HERE, "graph_papers.png"),
     f"Papers citing {ARGS.title}",
     lambda n: TCOL[n[2:]] if n.startswith("T:") else
     ("#d98880" if G.nodes[n].get("self_citation") == "True" else "#7f8c8d"),
     lambda n: 2600 if n.startswith("T:") else 130)

GI = nx.Graph()
for k_, lbl in SHORT.items():
    GI.add_node("T:" + k_, label=lbl, kind="ganji_paper", show_label=True)
for nm, ps in inst_papers.items():
    GI.add_node("I:" + nm, label=nm, kind="institution", show_label=len(ps) >= 2,
                country=inst_country.get(nm, ""), papers=len(ps))
    for t in inst_targets[nm]:
        GI.add_edge("I:" + nm, "T:" + key_of(t))
save(GI, "graph_institutions")
draw(GI, os.path.join(HERE, "graph_institutions.png"),
     f"Institutions citing {ARGS.title}",
     lambda n: TCOL[n[2:]] if n.startswith("T:") else "#8e44ad",
     lambda n: 2600 if n.startswith("T:") else 90 + 140 * GI.nodes[n].get("papers", 1))

GA = nx.Graph()
for k_, lbl in SHORT.items():
    GA.add_node("T:" + k_, label=lbl, kind="ganji_paper", show_label=True)
for k, ps in auth_papers.items():
    GA.add_node("A:" + k, label=canon[k], kind="author", show_label=len(ps) >= 3,
                papers=len(ps), coauthor=str(bool(auth_self.get(k))))
    for t in auth_targets[k]:
        GA.add_edge("A:" + k, "T:" + key_of(t))
save(GA, "graph_authors")
draw(GA, os.path.join(HERE, "graph_authors.png"),
     f"Authors citing {ARGS.title}",
     lambda n: TCOL[n[2:]] if n.startswith("T:") else
     ("#d98880" if GA.nodes[n].get("coauthor") == "True" else "#16a085"),
     lambda n: 2600 if n.startswith("T:") else 60 + 110 * GA.nodes[n].get("papers", 1),
     figsize=(26, 20), k=0.30)

# ---------------------------------------------------------------- data for the web page
d3 = {
    "targets": [{"key": k, "label": v, "color": TCOL[k],
                 "scholar_citations": next(p["scholar_citations"] for p in RAW["papers"]
                                           if p["key"] == k),
                 "collected": len({norm_title(r["title"]) for r in records
                                   if r["target"] == k})}
                for k, v in SHORT.items()],
    "records": [{"target": r["target"], "title": r["title"], "year": r["year"],
                 "venue": r["venue"], "doi": r["doi"], "cited_by": r["cited_by"],
                 "self_citation": r["self_citation"],
                 "authors": [canon.get(akey(a), a) for a in r["authors"]],
                 "institutions": sorted({i[0] for i in r["institutions"]}),
                 "countries": sorted({i[1] for i in r["institutions"] if i[1]}),
                 "sources": r["sources"]} for r in records],
}
json.dump(d3, open(os.path.join(HERE, ARGS.prefix + "data.json"), "w"), indent=1)
print("wrote", ARGS.prefix + "data.json")

print("\nSUMMARY")
print(" distinct citing papers :", len({norm_title(r['title']) for r in records}))
print(" distinct citing authors:", len(auth_papers))
print(" distinct institutions  :", len(inst_papers))
print(" countries              :", len(cc_count))
for p in RAW["papers"]:
    n = len({norm_title(r["title"]) for r in records if r["target"] == p["key"]})
    print(f"   {SHORT[p['key']]}: {n} collected / {p['scholar_citations']} on Scholar")
print("\nTop institutions:")
for nm, ps in sorted(inst_papers.items(), key=lambda x: -len(x[1]))[:20]:
    print(f"  {len(ps):2d}  {nm} ({inst_country.get(nm,'')})")
print("\nMost frequent citing authors (excluding co-authors):")
ext = [(k, ps) for k, ps in auth_papers.items() if not auth_self.get(k)]
for k, ps in sorted(ext, key=lambda x: -len(x[1]))[:20]:
    print(f"  {len(ps):2d}  {canon[k]}")
