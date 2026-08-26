# Citation map for Santosh Ganji's publications

Who cites the work, which authors they are, and which institutions those authors
belong to. Google Scholar identifies the publications and gives the reference
citation counts; the citing records come from APIs, because Scholar's "Cited by"
pages are behind a CAPTCHA.

Two datasets are built from the same code. Files with no prefix cover the four
most-cited papers. Files prefixed `all_` cover every entry on the profile.

## Coverage per publication

From profile `MA3CvN0AAAAJ`, ranked by Scholar citation count.

| Publication | Venue | Scholar | Collected |
|---|---|---:|---:|
| NeurWIN | NeurIPS 2021 | 74 | 52 |
| Scheduling and Decoding of DL Control Channel in NB-IoT | IEEE Access 2020 | 16 | 9 |
| Efficient beam sweeping at a mobile device receiver | US Patent 11,178,628 | 14 | 0 |
| BeamSurfer | IEEE TWC 2022 | 13 | 11 |
| Downlink Control Channel Scheduling for NB-IoT | IEEE PIMRC 2018 | 13 | 8 |
| Unblock | COMSNETS 2021 | 9 | 6 |
| Managing power resources of an IoE device | US Patent App. 15/191,757 | 9 | 0 |
| TERRA | IEEE TWC 2024 | 6 | 6 |
| Beamsurfer (poster) | SIGCOMM'20 Posters | 6 | 6 |
| A directional MAC protocol for 5G mm-wave LANs | COMSNETS 2018 | 6 | 1 |
| Overcoming pedestrian blockage using ground reflections | arXiv 2021 | 4 | 2 |
| Iris | COMSNETS 2019 | 4 | 1 |
| Novel rate matching scheme for DL control channel | COMSNETS 2018 | 4 | 4 |
| Terra (poster) | SIGCOMM'22 Posters | 3 | 3 |
| Realtime intelligent control for NextG RAN | MobiSys 2022 | 3 | 3 |
| Improved physical downlink control channel | COMSNETS 2018 | 3 | 3 |
| Seeing the Unseen (REVEAL) | IEEE TWC 2024 | 2 | 2 |
| Seeing the Unseen (REVEAL) | ACM S3 Workshop 2023 | 1 | 1 |
| Cellular system utilizing beam coherence interval metric | US Patent App. 17/741,188 | 1 | 0 |
| Communication Systems and Networks (COMSNETS 2018) | Springer 2019 | 1 | 0 |

## Totals

All publications (`all_` files):

- 96 distinct citing papers, of which 39 are self-citations by the author or a co-author.
- 229 distinct citing authors, 210 of them outside the co-author group.
- 71 institutions across 13 countries. The US leads with 27 institution-to-paper
  links, then France with 24, India with 15 and China with 11.
- Most frequent external citing authors: Milind Tambe (10 papers), Konstantin
  Avrachenkov (7), Aparna Taneja (6), Guojun Xiong (6).
- Most frequent institutions: Harvard University and Texas A&M University (5
  papers each), then Northwestern Polytechnical University, National University
  of Kaohsiung and IIT Hyderabad (4 each).

Four most-cited papers only (unprefixed files): 77 citing papers, 165 authors,
66 institutions, 15 countries.

## Data sources

| Source | Role | Notes |
|---|---|---|
| Google Scholar | publication list, reference counts, cluster IDs | profile page is fetchable; `/scholar?cites=` returns a CAPTCHA |
| Semantic Scholar | citing papers | best coverage; `/paper/search` is throttled, `/paper/{id}` is not |
| OpenAlex | citing papers, author affiliations, ROR, country | the only source here with clean institution names |
| Crossref | DOI resolution, citing metadata, some affiliations | affiliations are postal addresses, reduced to the organisation name |
| OpenCitations | citing papers | added 7 records the other sources lacked |

Per source, the 118 (publication, citing paper) rows break down as: Semantic
Scholar 86, Semantic Scholar and OpenAlex together 18, OpenAlex 7, Crossref 7.

## Coverage limits

The three patents hold 24 citations between them and none are reachable. No
bibliographic API here indexes patents, so those need Scholar or Google Patents.

Of the 192 citations Scholar reports, 118 rows were retrieved. Besides the
patents, the missing records are ones Scholar indexes and these APIs do not:
theses, workshop papers, unindexed preprints and non-English venues. Closing
that gap needs Scholar itself, through SerpAPI or a browser-driven scraper.

Affiliations are thinner than the paper list: 49 of 118 rows carry an
institution, and 92 of 210 external authors have their own affiliation recorded.
OpenAlex often stores no institution for IEEE conference records and arXiv
preprints, and OpenAlex metering interrupted the affiliation pass; rerunning
`enrich_openalex.py` after the daily reset improves this.

Author names are merged on surname plus first initial, so "M. Tambe" and "Milind
Tambe" count once. Two authors sharing both would be merged incorrectly.

## Corrections applied

Three OpenAlex affiliation mappings were wrong, each checked against the record's
raw affiliation strings: Harvard authors carried the ROR of Harvard University
Press, and ARMMAN carried that of the American Rock Mechanics Association. Both
are remapped in `build.py`. Crossref postal affiliations are reduced to the
organisation name by `tidy_affiliation`.

## Files

Unprefixed files cover the four most-cited papers; `all_` covers everything.

- `citing_papers.csv` — one row per (cited paper, citing paper), with authors, institutions, countries, self-citation flag and source.
- `citing_authors.csv` — per author: papers, whether they are a co-author, which papers they cite, own institutions.
- `citing_institutions.csv` — per institution: country, papers, authors, ROR.
- `citing_countries.csv` — institution-to-paper links per country.
- `citation_map.html`, `citation_map_all.html` — interactive graph, switchable between papers, authors and institutions. Opens offline, no dependencies.
- `graph_papers`, `graph_authors`, `graph_institutions` — `.png`, plus `.graphml` and `.gexf` for Gephi or Cytoscape.
- `raw.json`, `raw_all.json`, `data.json`, `all_data.json` — raw API responses and the cleaned records.

## Rebuilding

```
python3 resolve_crossref.py                      # Scholar entries -> DOIs
python3 collect_all.py --skip-openalex           # citing papers from Semantic Scholar
python3 collect_oc_all.py                        # OpenCitations plus Crossref metadata
python3 merge_prior.py                           # reuse OpenAlex data from the four-paper run
python3 build.py --raw raw_all.json --prefix all_
python3 make_html.py --data all_data.json --out citation_map_all.html
```

Once the OpenAlex budget resets, these two add the affiliations it alone supplies,
then the build and page steps are rerun:

```
python3 resolve_all.py                           # fills OpenAlex work IDs per entry
python3 enrich_openalex.py --raw raw_all.json    # affiliations for citing papers
```

The four-paper dataset is built by `collect2.py`, `collect3.py` and `collect4.py`,
then `build.py` and `make_html.py` with no `--prefix`.

Semantic Scholar is unauthenticated, so `collect_all.py` paces itself at roughly
one request every eight seconds and takes about five minutes. An API key removes
that wait. OpenAlex meters requests daily and resets at midnight UTC.

Crossref and OpenAlex serve requests faster when the User-Agent carries a contact
address. Set one before running:

```
export CITATION_MAP_EMAIL=you@example.com
```
