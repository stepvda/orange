# Build status and data sources

## Where the build stands

Read live from the working database, not typed here.

|                         |                                                                                                                                                  |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Opportunity spaces      | **449** — 363 active, 40 watchlist, 29 fading, 17 candidate                                                                                      |
| Grid coverage           | 15 of 15 verticals · 51 of 59 use cases · 35 of 38 technologies                                                                                  |
| Signals                 | **11,498** from 33 enabled sources, plus internal intake · 7,341 tier-1 · 1,054 French-language                                                  |
| Evidence attachment     | 11,602 signal-to-topic attachments across 325 theme clusters                                                                                     |
| Business graph          | 5,217 typed links onto 181 nodes and 182 edges                                                                                                   |
| Qualification           | 752 market-size computations over 449 spaces · 336 with a bottom-up estimate · 213 competitive assessments                                       |
| Competitor intelligence | 1,745 pages from 53 of 65 competitors · 53 profiles · 176 per-topic analyses                                                                     |
| Outputs                 | 173 long-form descriptions · 173 PDF briefs · 15 pre-sales artefacts built across 5 formats                                                      |
| Reference data          | 56,385 Eurostat observations across five series                                                                                                  |
| Planning                | 8 stored plans — the baseline parameter plan selects 51 spaces from 231 admissible; the workflow plan takes every committed space and drops none |
| Workflow                | 449 on the board — 446 Shortlisted, 2 Demand-tested, 1 Packaged                                                                                  |
| Tests                   | **486 passing**                                                                                                                                  |

Four numbers worth reading as gaps rather than achievements: **all 5,217 links
are machine-proposed and unconfirmed** — LK-06 wants a named human on the first
occurrence of each pattern; **236 of 449 spaces have no competitive assessment
yet**, so their competitor tab is empty; **113 spaces have no bottom-up market
size**, which is what makes them invisible to the Planner rather than merely
unqualified; and **the stage gate has three cards past Shortlisted**, so a
workflow-sourced plan currently describes a portfolio of three. All four are
surfaced in the interface rather than left to be discovered. They are the same
three limitations set out in [question 2](INTERVIEW_GUIDE.md#2-the-top-three-limitations-and-next-steps).

## Data sources

**33 of 42 catalogued sources are wired and fetching**, across 17 connector types. The remaining nine are
catalogued in `config/sources.yaml` with the reason they are not — the catalogue
is the requirements record from Appendix A, not only runtime config.

Collection is **parallel**: sources are independent and network-bound, so they
run in a thread pool (`max_parallel_sources`, default 8); database writes stay
serial because dedup is a read-modify-write over the whole signal table.

Collection queries are **derived from the taxonomy** (`pipeline/query_grid.py`)
rather than hand-written. `config/sources.yaml` had claimed this was already true
and it was not — the first corpus showed the consequence, with whole branches of
a 59-use-case vocabulary carrying no query at all while manufacturing and public
sector ran away with the topic count.

| Source                             | Category    | Signals    | Notes                                                                                     |
| ---------------------------------- | ----------- | ---------- | ----------------------------------------------------------------------------------------- |
| TED                                | Procurement | 4,267      | Above-threshold EU tenders with CPV, country, buyer, value                                |
| Google News (EN)                   | Signals     | 1,488      | Queries derived from the taxonomy grid                                                    |
| OpenAlex                           | Technology  | 910        | Carries an Orange-affiliation flag (§2.5)                                                 |
| Google News (FR)                   | Signals     | 765        | French-language coverage                                                                  |
| Crossref                           | Technology  | 603        | Peer-reviewed output by concept                                                           |
| Google News (ES/DE/IT/NL/MEA/APAC) | Signals     | 966        | Six further language and region editions                                                  |
| GDELT                              | Signals     | 296        | Rate-limited, see below                                                                   |
| BOAMP                              | Procurement | 289        | French below-threshold tenders (§4.3.3)                                                   |
| CERT-BUND                          | Regulation  | 243        | German national regulator                                                                 |
| arXiv                              | Technology  | 236        |                                                                                           |
| Bing News                          | Signals     | 177        |                                                                                           |
| Find a Tender                      | Procurement | 173        | UK post-Brexit notices                                                                    |
| EC "Have your say"                 | Regulation  | 171        | Consultations with their feedback **deadline**                                            |
| Trade press                        | Signals     | 156        | Curated industry titles                                                                   |
| SEC EDGAR                          | Demand      | 142        | Named enterprises describing their own deployments, under legal obligation to be accurate |
| EUR-Lex                            | Regulation  | 86         | Dated legal instruments, stage inferred                                                   |
| CORDIS                             | Technology  | 77         | EU-funded projects — what Europe decided to fund                                          |
| TenderNed                          | Procurement | 77         | Dutch notices                                                                             |
| National regulators                | Regulation  | 86         | ANSSI, ACER, the EU financial regulators and peers                                        |
| Hacker News                        | Signals     | 66         | Practitioner attention, tier 3                                                            |
| UK Contracts Finder                | Procurement | 63         |                                                                                           |
| IETF Datatracker                   | Technology  | 51         | Standards timelines                                                                       |
| NIST · CISA · NCSC-UK · CERT-EU    | Regulation  | 100        | Standards and advisories                                                                  |
| Internal signals                   | Internal    | 10         | Moderated conversations and RFP themes, tier 3 (§2.5)                                     |
| **Total**                          |             | **11,498** | 7,341 tier-1 · 1,054 French-language                                                      |

Not wired, with the reason: Ofcom (403 to automated clients), BNetzA and BIPT
(documented feed paths 404), ENISA (retired its RSS endpoints), 3GPP and ETSI
(publish HTML, not feeds), EPO OPS (needs registration), PatentsView and ACLED
(DNS failures), Eurostat and World Bank (reachable, but they are _reference_
data for bottom-up sizing rather than dated signals — see below).

### Three sampling bugs worth knowing about

Each of these produced a plausible-looking corpus that was quietly wrong. All
three were found by looking at what actually landed in the database.

- **TED returned 40 of 14,485 matching notices, all from one day.** The API
  accepts no sort parameter and returns publication-date ascending, so a single
  capped request samples only the oldest day in the window — 182 of 218 notices
  from one date. Momentum (§4.6) is the slope of signal volume over trailing
  periods, so that corpus made every procurement-driven momentum figure
  meaningless. Fixed by slicing the window into 14-day chunks and querying each:
  now 827 notices across 35 distinct dates spanning the full 90 days.
- **CORDIS returned nothing at all.** It leaks its own localisation template and
  emits dates as `1 {{month_11}} 2023`, which failed date parsing, so every
  project was rejected as undated (DR-04) — silently, with no error.
- **EUR-Lex yielded 20 distinct acts from 120 rows.** CELLAR returns one row per
  expression title and several titles share a work, so rows collapsed on URL
  dedup. The limit was raised to compensate; a EuroVoc-concept query is the
  proper Sprint 0 fix.

**GDELT caveat.** The connector is correct and does return data, but GDELT
applies an aggressive per-IP cooldown and 429'd most requests during the build.
It is paced at one request per 6s. Two guards keep one sick source from damaging
a refresh:

- **Graceful degradation** — a failing source is recorded in the refresh stats
  and never aborts the run.
- **Circuit breaker** — after two exhausted requests to a host, the rest of that
  host's requests are skipped and the host is reported in `collect.errors`.
  Without it, ten blocked GDELT queries cost eleven minutes for zero data. GDELT
  is the long pole in every refresh: everything else finishes in 45 seconds
  while it takes up to 11 minutes alone.

**Reference data is wired, on its own path.** Five Eurostat series feed market
sizing and are stored as reference observations rather than signals, for the
reason given in the sizing section above:

| Series                         | Dataset            | Observations | What it gives                                                                             |
| ------------------------------ | ------------------ | ------------ | ----------------------------------------------------------------------------------------- |
| Structural business statistics | `sbs_sc_ovw`       | 27,958       | Enterprise counts and turnover by NACE division, size class and country — the denominator |
| Enterprise cloud use           | `isoc_cicce_usen2` | 6,885        | Paid cloud adoption by NACE aggregate                                                     |
| Enterprise AI use              | `isoc_eb_ain2`     | 11,440       | AI adoption by technology and NACE aggregate                                              |
| Enterprise IoT use             | `isoc_eb_iotn2`    | 2,759        | IoT adoption by purpose                                                                   |
| ICT security measures          | `isoc_cisce_ran2`  | 7,343        | Security practice by measure                                                              |

30 geographies (EU27 aggregate plus member states, Norway and Switzerland), the
last three published periods each, refetched only when older than the configured
age — these are annual statistics, not a feed. The AI series carries its own
trajectory, which the UI shows as an adoption trend: machine learning in EU
vehicle manufacturing went 3.2% (2023) → 4.8% (2024) → 7.8% (2025), which is a
dated, attributable growth statement rather than a generated one.

Still not wired **as reference data**: OECD, ITU, IEA and the national statistics
offices from Table 19. They matter for topics outside the European business
economy — today those are sized on the covered subset and the shortfall is
reported. SEC EDGAR is in the same Table 19 row and _is_ wired, but as a signal
source (142 items above): filings are dated, attributable statements of what a
named enterprise deployed, not a statistical denominator, so they feed discovery
rather than sizing.

