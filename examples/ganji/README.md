# Example: Santosh Ganji

Worked output for Google Scholar profile `MA3CvN0AAAAJ`, 20 entries and 192
citations, collected on 26 August 2026.

Two datasets sit side by side. Files prefixed `all_` cover every entry on the
profile; unprefixed files cover only the four most-cited papers.

## Results

- 96 distinct citing papers, 41 of them self-citations by the author or a co-author.
- 229 distinct citing authors, 210 outside the co-author group.
- 71 institutions across 13 countries. The United States accounts for 27
  institution-to-paper links, France 24, India 15 and China 11.
- Most frequent external citing authors: Milind Tambe (10 papers), Konstantin
  Avrachenkov (7), Aparna Taneja (6), Guojun Xiong (6).
- Most frequent institutions: Harvard University and Texas A&M University at 5
  papers each, then Northwestern Polytechnical University, National University of
  Kaohsiung and IIT Hyderabad at 4.

## Coverage

118 rows were collected against Scholar's 192 citations. Where the shortfall falls:

| Cause | Citations |
|---|---:|
| Three patents, indexed by no bibliographic API | 24 |
| Thinly indexed venues, mostly the older COMSNETS papers | the remainder |

Per paper, the largest gaps are NeurWIN at 52 collected of 74, the IEEE Access
NB-IoT paper at 9 of 16, and the PIMRC NB-IoT paper at 8 of 13. Six entries were
collected in full.

Affiliations are patchier than the paper list: 49 of 118 rows carry an
institution, and 92 of 210 external authors have their own affiliation recorded.
The OpenAlex daily budget ran out partway through, which is the main reason;
rerunning `enrich_openalex.py` improves it.

## Reproducing

From this directory:

```
export CITATION_MAP_EMAIL=you@example.com
python3 ../../scripts/run.py --titles ganji_titles.txt --name "Santosh Ganji"
```

That writes the unprefixed dataset. The `all_` files came from the same raw
responses, with the stages run separately:

```
python3 ../../scripts/build.py --raw data/raw_all.json --prefix all_ --out-dir . \
        --title "Santosh Ganji's publications"
python3 ../../scripts/make_html.py --data data/all_data.json \
        --out web/citation_map_all.html --heading "Who cites Santosh Ganji's work"
```

Citation counts move, so a fresh run will not reproduce these numbers exactly.

`ganji_titles.txt` was transcribed from the Scholar profile. Running
`setup_profile.py` on it resolves 11 of the 20 entries, flags the 3 patents, and
leaves 6 without a DOI: the NeurIPS paper, the arXiv preprint, both SIGCOMM
posters, the ACM S3 workshop paper and the proceedings volume. Crossref either
stores these under a short title such as "Terra" or does not carry them at all.
Their identifiers are already present in `data/targets_resolved.json`; a fresh run
needs them added by hand, as the main README describes.

## Files

| Path | Contents |
|---|---|
| `tables/` | the four CSVs, both datasets |
| `graphs/` | PNG, GraphML and GEXF for the paper, author and institution graphs |
| `web/` | the interactive pages; open either file directly in a browser |
| `data/` | raw API responses, the resolved target list, and the cleaned records |
| `ganji_titles.txt` | input to `setup_profile.py` |
