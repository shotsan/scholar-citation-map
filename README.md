# scholar-citation-map

Find out who cites a researcher's work: the citing papers, the authors who wrote
them, and the institutions those authors belong to. Produces CSV tables, citation
graphs, and a self-contained interactive page.

Google Scholar shows citation counts but its "Cited by" pages are behind a
CAPTCHA, so the citing records come from four open APIs instead: Semantic
Scholar, OpenAlex, OpenCitations and Crossref. Scholar's counts are still useful
as a reference, and the output reports collected-versus-Scholar per paper so the
gap is visible rather than hidden.

A worked example for one profile is committed under
[`examples/ganji/`](examples/ganji/). See [Example output](#example-output).

## Repository layout

```
scripts/            the pipeline
scripts/legacy/     earlier scripts, kept so the example stays reproducible
examples/ganji/     a worked example
  ganji_titles.txt  the input
  data/             raw API responses and cleaned records
  tables/           the CSVs
  graphs/           PNG, GraphML and GEXF
  web/              the interactive pages
```

Scripts read and write relative to the current directory, so run them from
wherever the output should land, not from `scripts/`.

## Requirements

Python 3.9 or later, plus:

```
pip install -r requirements.txt
```

No API keys are needed. Set a contact address so Crossref and OpenAlex serve you
from their faster pool:

```
export CITATION_MAP_EMAIL=you@example.com
```

## Running it on your own profile

### 1. Build the target list

The pipeline needs your publications resolved to DOIs. Three ways to get there.

**From a list of titles.** The most reliable, because you control what is in it.
Copy the titles from your Scholar profile into a text file, one per line.
Optionally add venue and citation count after a `|`:

```
NeurWIN: Neural Whittle index network for restless bandits via deep RL | NeurIPS 2021 | 74
BeamSurfer: Minimalist beam management of mobile mm-wave devices | IEEE TWC 2022 | 13
```

```
mkdir -p ~/my-citations && cd ~/my-citations
python3 /path/to/scripts/setup_profile.py --titles my_papers.txt
```

The citation count is only used for the coverage comparison; leave it out if you
do not want to transcribe it.

**From a Semantic Scholar author id.** No transcribing, but Semantic Scholar
often splits one person across several author ids, so check the paper count
before choosing:

```
python3 scripts/setup_profile.py --find-author "Your Name"
python3 scripts/setup_profile.py --s2-author 2067185293
```

**Fixing what does not resolve.** Titles are matched against Crossref and a match
is only accepted when the returned title agrees, so some entries come back
without a DOI. Patents are flagged and skipped, because no bibliographic API
indexes them. For anything else, open `targets_resolved.json` and add the DOI to
that entry's `dois` list by hand.

### 2. Collect the citing papers

```
python3 scripts/collect_all.py       # Semantic Scholar and OpenAlex
python3 scripts/collect_oc_all.py    # OpenCitations, with Crossref metadata
```

`collect_all.py` takes about twenty seconds per publication. Semantic Scholar is
unauthenticated here, so it paces itself at one request every eight seconds; an
API key removes that wait. Add `--skip-openalex` if OpenAlex has cut you off (see
[Rate limits](#rate-limits)) and run `enrich_openalex.py` later.

### 3. Build the tables, graphs and page

```
python3 scripts/build.py --raw raw_all.json --out-dir . --title "My publications"
python3 scripts/make_html.py --data data/data.json --out citation_map.html \
        --heading "Who cites my work"
```

`build.py` writes `tables/`, `graphs/` and `data/` under `--out-dir`. Add
`--prefix` to keep several datasets side by side in one directory.

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
list off each of your papers, so the flag needs no configuration.

## Rate limits

**Semantic Scholar** throttles unauthenticated callers. `/paper/search` is the
strictest endpoint and the scripts avoid it, addressing papers by DOI instead.
The eight-second pacing in `collect_all.py` is what makes the run reliable
without a key.

**OpenAlex** meters requests against a small daily budget that resets at midnight
UTC. Exceeding it returns `Insufficient budget` rather than an HTTP 429. OpenAlex
is the only one of the four sources with clean institution names, so a run that
hits the limit will have thin affiliation data. Recover with:

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
are corrected in `INSTITUTION_ALIASES` in `build.py`. Expect to add your own
entries there and to check them against each record's raw affiliation strings.

## Example output

[`examples/ganji/`](examples/ganji/) covers the Google Scholar profile of Santosh
Ganji (`MA3CvN0AAAAJ`), 20 entries and 192 citations. Files prefixed `all_` cover
every entry; unprefixed files cover only the four most-cited papers.

- 96 distinct citing papers, 41 of them self-citations.
- 229 citing authors, 210 outside the co-author group.
- 71 institutions across 13 countries: 27 institution-to-paper links from the US,
  24 from France, 15 from India, 11 from China.
- Most frequent external citing authors: Milind Tambe (10 papers), Konstantin
  Avrachenkov (7), Aparna Taneja (6), Guojun Xiong (6).
- Most cited paper, NeurWIN (NeurIPS 2021), returned 52 citing papers against
  Scholar's 74.

Coverage came to 118 rows against Scholar's 192 citations. Three patents hold 24
of the shortfall and are unreachable; the rest are thinly indexed venues, mostly
the older COMSNETS papers.

## Script reference

| Script | Role |
|---|---|
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
