# Guide

Reference for running the pipeline. The [README](../README.md) covers the three
steps. This file covers the options and the stages behind them.

## The short path

```
python3 scripts/run.py --titles my_papers.txt --name "Your Name" --images
```

`run.py` runs resolve, collect and build in order, printing each stage. Useful
flags:

| Flag | Effect |
|---|---|
| `--titles FILE` or `--s2-author ID` | where the publication list comes from |
| `--out-dir DIR` | everything is written here; defaults to the current directory |
| `--images` | also write a PNG per view, via `render_images.py` |
| `--theme light\|dark` | the map's colours; light is the default |
| `--skip-openalex` | OpenAlex is metered daily; skip it and enrich later |
| `--skip-collect` | reuse `raw_all.json` and only rebuild the output |

After the resolve stage it reports how many publications carry an identifier.
Anything without one collects nothing, so fix those before waiting on the
collection.

The rest of this guide covers the five scripts `run.py` calls.

## Requirements

Python 3.9 or later.

```
pip install -r requirements.txt
```

No API keys are needed. Set a contact address so Crossref and OpenAlex serve
from their faster pool:

```
export CITATION_MAP_EMAIL=you@example.com
```

Scripts read and write relative to the current directory. Run them from the
folder the output should land in, not from `scripts/`.

## Building the target list

The pipeline needs the publications resolved to DOIs. Three ways to get there.

**From a list of titles.** The most reliable, because the contents are under
your control. Copy the titles from the Scholar profile into a text file, one per
line. Venue and citation count may follow a `|`:

```
NeurWIN: Neural Whittle index network for restless bandits via deep RL | NeurIPS 2021 | 74
BeamSurfer: Minimalist beam management of mobile mm-wave devices | IEEE TWC 2022 | 13
```

```
mkdir -p ~/my-citations && cd ~/my-citations
python3 /path/to/scripts/setup_profile.py --titles my_papers.txt
```

The citation count only feeds the coverage comparison. Leave it out to skip the
transcription.

**From a Semantic Scholar author id.** Nothing to transcribe. Semantic Scholar
often splits one person across several author ids, so check the paper count
before choosing:

```
python3 scripts/setup_profile.py --find-author "Your Name"
python3 scripts/setup_profile.py --s2-author 2067185293
```

**Fixing what does not resolve.** Titles are matched against Crossref and a
match is accepted only when the returned title agrees, so some entries come back
without a DOI. Patents are flagged and skipped, because no bibliographic API
indexes them. For anything else, open `targets_resolved.json` and add the DOI to
that entry's `dois` list by hand.

## Collecting the citing papers

```
python3 scripts/collect_all.py       # Semantic Scholar and OpenAlex
python3 scripts/collect_oc_all.py    # OpenCitations, with Crossref metadata
```

`collect_all.py` takes about twenty seconds per publication. Semantic Scholar is
unauthenticated here, so it paces itself at one request every eight seconds; an
API key removes that wait. Add `--skip-openalex` if OpenAlex has cut you off and
run `enrich_openalex.py` after the reset.

## Building the tables, graphs and page

```
python3 scripts/build.py --raw raw_all.json --out-dir . --title "My publications"
python3 scripts/make_html.py --data data/data.json --out citation_map.html \
        --heading "Who cites my work" --theme light
```

`build.py` writes `tables/`, `graphs/` and `data/` under `--out-dir`. Add
`--prefix` to keep several datasets side by side in one directory.

`make_html.py --theme` takes `light` or `dark`. Light is the default, because it
prints and drops into a slide without inverting.

## Images for slides and posters

```
python3 scripts/render_images.py --page citation_map.html --out-dir images \
        --graph-only
```

This drives headless Chrome over the page and writes one PNG per view. Chrome or
Chromium must be installed; set `CHROME` to point at a specific binary.

| Flag | Effect |
|---|---|
| `--graph-only` | drop the title, filter chips and totals panel |
| `--views papers,authors,institutions` | pick which views to write |
| `--width` and `--height` | window size in pixels; defaults to 2400 by 1400 |
| `--scale 2` | double the pixels, for print |

## Outputs

| File | Contents |
|---|---|
| `tables/citing_papers.csv` | one row per (your paper, citing paper): authors, institutions, countries, self-citation flag, source |
| `tables/citing_authors.csv` | per citing author: how many of your papers they cite, whether they are your co-author, their own institutions |
| `tables/citing_institutions.csv` | per institution: country, papers, authors, ROR id |
| `tables/citing_countries.csv` | institution-to-paper links per country |
| `citation_map.html` | interactive graph, switchable between papers, authors and institutions; opens offline with no dependencies |
| `graphs/graph_papers`, `graph_authors`, `graph_institutions` | `.png`, plus `.graphml` and `.gexf` for Gephi or Cytoscape |
| `data/raw_all.json`, `data/data.json` | raw API responses and the cleaned records |

Self-citations are marked, not dropped. `setup_profile.py` reads the co-author
list off each publication, so the flag needs no configuration.

## Rate limits

**Semantic Scholar** throttles unauthenticated callers. `/paper/search` is the
strictest endpoint and the scripts avoid it, addressing papers by DOI instead.
The eight-second pacing in `collect_all.py` is what makes the run reliable
without a key.

**OpenAlex** meters requests against a small daily budget that resets at
midnight UTC. Exceeding it returns `Insufficient budget` rather than an HTTP 429.
OpenAlex is the only one of the four sources with clean institution names, so a
run that hits the limit will have thin affiliation data. Recover with:

```
python3 scripts/collect_all.py --skip-openalex   # get citing papers today
python3 scripts/resolve_all.py                   # after reset: OpenAlex work ids
python3 scripts/enrich_openalex.py --raw raw_all.json   # after reset: affiliations
```

**Crossref and OpenCitations** have no practical limit for this workload.

## Known limits

**Coverage is below Scholar's counts.** Scholar indexes theses, workshop papers,
unindexed preprints and non-English venues that these APIs do not. Older or
smaller conference venues are affected most. The per-paper collected-versus-
Scholar table in the build output shows where the gap falls. Closing it needs
Scholar itself, through SerpAPI or a browser-driven scraper such as
[étudier](https://github.com/edsu/etudier), which requires solving CAPTCHAs by
hand.

**Patents are not covered at all.** None of the four APIs index them.

**Affiliations are patchier than the paper list.** OpenAlex often stores no
institution for IEEE conference records and arXiv preprints. Crossref stores the
author's full postal address rather than an institution name; `tidy_affiliation`
in `build.py` reduces these to the organisation, which is a heuristic and will
occasionally pick the wrong part of an address.

**Author names are merged on surname plus first initial**, so "M. Tambe" and
"Milind Tambe" count once. Two distinct authors sharing both would be merged
incorrectly.

**OpenAlex affiliation mappings are sometimes wrong.** Two were found while
building the example: Harvard authors carried the ROR of Harvard University
Press, and ARMMAN carried that of the American Rock Mechanics Association. Both
are corrected in `INSTITUTION_ALIASES` in `build.py`. Expect to add further
entries there and to check them against each record's raw affiliation strings.

## Script reference

| Script | Role |
|---|---|
| `run.py` | runs the five below in order |
| `render_images.py` | PNGs of the map's three views |
| `setup_profile.py` | publications to `targets_resolved.json`, resolving DOIs and co-authors |
| `collect_all.py` | citing papers from Semantic Scholar and OpenAlex |
| `collect_oc_all.py` | citing papers from OpenCitations, metadata from Crossref |
| `resolve_all.py` | fills OpenAlex work ids per publication |
| `enrich_openalex.py` | affiliations for citing papers already collected |
| `add_coauthors.py` | backfills co-authors into a target file made before `setup_profile.py` |
| `merge_prior.py` | copies OpenAlex data from an earlier run so it is not re-fetched |
| `build.py` | tables, graph files and PNGs |
| `make_html.py` | the interactive page |

`scripts/legacy/` holds `collect2.py`, `collect3.py`, `collect4.py`,
`resolve_crossref.py` and `all_targets.py`, which built the example before the
generic path existed. They are kept so it stays reproducible; new runs should use
`setup_profile.py`.
