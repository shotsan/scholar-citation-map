"""Carry the OpenAlex data already fetched for the four-paper run into raw_all.json.

The four target keys are identical in both files, so their citing lists and the
affiliation lookups transfer directly and cost no OpenAlex budget.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
prior = json.load(open(os.path.join(HERE, "raw.json")))
raw = json.load(open(os.path.join(HERE, "raw_all.json")))

for bag in ("oa_extra_by_doi", "oa_extra_by_title", "oc_resolved_oa"):
    before = len(raw.get(bag) or {})
    merged = dict(raw.get(bag) or {})
    merged.update(prior.get(bag) or {})
    raw[bag] = merged
    print(f"{bag}: {before} -> {len(merged)}")

prior_citing = {p["key"]: p["oa_citing"] for p in prior["papers"]}
for p in raw["papers"]:
    extra = prior_citing.get(p["key"])
    if not extra:
        continue
    have = {(w.get("doi") or w.get("display_name") or "").lower()
            for w in p["oa_citing"]}
    added = [w for w in extra
             if (w.get("doi") or w.get("display_name") or "").lower() not in have]
    p["oa_citing"].extend(added)
    print(f"{p['key']}: +{len(added)} OpenAlex citing records")

json.dump(raw, open(os.path.join(HERE, "raw_all.json"), "w"))
print("updated raw_all.json")
