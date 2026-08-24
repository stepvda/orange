# Changelog

Notable changes to the Innovation Radar, most recent first. Defects are recorded
alongside features, because several of the defects are more instructive than the
features that exposed them.

---

## A scoping assistant on the Generate screen

**Changed.** The free-text box at the bottom of the Generate screen ("Or
describe one opportunity space") is now a conversation, selected from a tab
beside the grid form. The box asked for one thing and gave one piece of
feedback — a character count, which is the only failure that did not matter. An
opportunity space is a vertical × use case × technology plus a buyer's problem
and a place, and somebody who knows their market but not the taxonomy
under-specified two of those every time. They found out minutes later, from a
run that created nothing.

* **The assistant reads the corpus while you talk.** Every turn re-retrieves
  from the whole transcript against the same signal vectors the run will read,
  at the same similarity floor, and what came back is shown beside the
  conversation with publisher, date and cosine. It is also given the
  theme-cluster map, the geography and signal-type distribution, and the
  taxonomy cells already occupied — so it asks about the geography the evidence
  is actually in rather than asking which geography.
* **It interviews in a fixed order.** The three slots that *are* the space
  first, then the buyer's problem, geography, buyer and deal shape — ranked by
  how much each changes retrieval. The questions are configuration
  (`prompts.SCOPING_SLOTS`), reviewable as a set the way the vocabularies are.
* **The button is enabled by the corpus, not by the model.** Every brief the
  assistant proposes is put back through the retrieval the job will perform. One
  that returns nothing above the floor is shown with the reason and cannot be
  selected. Asked whether it has enough, a model says yes; where the two
  disagree the screen says so.
* **Similarity is not support.** Retrieval clearing the floor only means the
  corpus contains text that READS like the brief. A brief for municipal digital
  signage retrieved French public-sector IT tenders at 0.64 cosine — the same
  closest score as a well-evidenced brief about turbine gearboxes — and
  synthesis then produced two candidates whose every claim the critic correctly
  rejected, for citing tenders that were about employment services. So a brief
  must also be SUPPORTED: at least three retrieved signals about its use case or
  its technology, not merely its sector. The test is the one
  `config/settings.yaml` already prescribes for enrichment
  (`require_taxonomy_corroboration`), reused rather than reinvented, with the
  vertical deliberately excluded — it is the axis that corroborates every brief
  ever written about a well-covered sector.
* **Two stages, cheapest first.** The vocabulary test is free and precise but
  has poor recall: a report on a utility's compromised RTUs is unmistakably
  about threat detection for energy operators and will never contain the string
  "SIEM and SOAR". Where it comes up short, one cheap model call is spent on the
  same retrieved documents — the same trade §4.4.4 makes for the entailment
  check. A provider failure keeps the vocabulary answer rather than turning
  every brief into a refusal.
* **Neither the assistant's own hedge nor the user's "yes" is permission.** If
  the assistant writes "the evidence is thin", it must set `ready` false and
  propose nothing; saying it is thin and proposing it anyway reads as a warning
  and behaves as a recommendation. It may not resolve thin evidence by asking
  "shall I proceed?" — the person cannot see the corpus and it can.
* **Closed vocabularies, in both directions.** What someone says is resolved
  through the vocabulary's own synonyms — "banking" becomes
  `financial_services` — and what cannot be resolved is dropped and named rather
  than carried through to fail validation three stages later.
* **DR-03 is said before the run.** A brief landing on an occupied triple names
  the space it would refresh, while there is still a choice about it.
* **One conversation can produce several spaces.** Distinct triples become
  distinct briefs and distinct synthesis passes inside a single run
  (`POST /api/generate/briefs`), because synthesis holds the only write lock on
  that identity. The briefs are editable before they run, and the run re-checks
  whatever is actually submitted.
* Stateless: the transcript lives in the browser and is posted whole each turn.
  No session table, nothing to expire. The opening turn is written rather than
  generated, so it costs no model call.

---

## The Planner

**Added.** A portfolio planner: stated constraints in, a selected set of
opportunity spaces out, with five years of revenue and profit and a written
business plan explaining them. Assumptions in `config/economics.yaml`, versioned
as `economics_version` and carried on every plan.

* **Selection is an optimisation, not a ranking.** A mixed-integer program
  (scipy `optimize.milp`, HiGHS) maximises the objective subject to entry slots
  per year, capability-pool headcount, concentration caps per vertical and
  technology, and a target now/next/later mix. Greedy fallback when HiGHS is
  unavailable.
* **Capability is a real constraint.** Entry effort is charged against
  capability pools at a stated availability, so a pool at its ceiling is the
  reason a plan is the size it is — and the plan says which constraint bound it.
* **Obtainable share is not additive.** Spaces in the same vertical compete for
  one buying centre, so the aggregate is discounted before it is summed. Naive
  sums implied 42–90% of segment revenue; the discounted plan lands at 6–9%.
* **The money comes from Orange's own filings.** Margin (7.9% segment EBITDAaL)
  and discount rate (7.3% post-tax) are quoted from the 2025 Universal
  Registration Document. Nothing in the projection is a chosen number.
* **A plausibility check that fires.** Year-5 revenue above a stated share of
  filed segment revenue is flagged on the plan rather than left for the reader.
* **The narrative may not state a figure.** Every number is the optimiser's;
  sections that introduce one are stripped and listed.
* **Export to PDF** — inputs (with the effective value of anything unstated and
  where it came from), the projection with charts, every selected space with the
  one-paragraph summary from its own long-form description, the business plan,
  and the assumptions with their owner and versions. Read inside the browser on
  a Document tab; downloadable from there.
* Two new tables (`plans`, `plan_selections`) and five columns recording the
  export, added through the additive migration list.
* Two new CLI commands: `plan` (with `--narrate` and `--pdf`) and `plans`.
* A full-screen Planner module with six hand-drawn SVG charts.

**Fixed — an unstated input read as an absent one.** The export listed only the
parameters a user had set, which misrepresented what the optimiser actually ran
with: an unset parameter falls back to the economics default and the plan is
built against *that*. Every row now carries its effective value and its source.

**Fixed — a concentration cap could make every plan infeasible.** With one
group, `count ≤ cap × total` implies `total ≤ 0`, so the optimiser returned
nothing at all. The cap is now skipped where there is only one group, and an
infeasible problem raises naming the binding constraints instead of returning an
empty portfolio.

---

## Competitor intelligence

**Added.** A subsystem that reads what each competitor publishes about itself and
turns it into per-topic competitive analysis. Full detail in
[COMPETITOR_INTELLIGENCE.md](COMPETITOR_INTELLIGENCE.md).

* `competitor_intel.py` — robots-aware, sitemap-guided crawler and profile
  builder. **1,745 pages across 53 of 65 competitors**; the other 12 recorded
  with a reason.
* `competitor_analysis.py` — the per-topic join (arithmetic, always present) and
  the written comparison (one model call, absent until asked for).
* **A differentiation paragraph per competitor** — how Orange differentiates
  against *that* company for *this* opportunity, anchored on an Orange asset
  actually linked to the topic, with a concession of what they do better.
* Three new tables: `competitor_pages`, `competitor_profiles`,
  `topic_competitor_analysis`.
* Three new CLI commands: `competitor-scrape`, `competitor-profile`,
  `competitor-analysis`.
* Three new endpoints: `/api/competitors`, `/api/competitors/{id}`,
  `/api/topics/{id}/competitor-analysis` (GET and POST).
* A third tab on the full-screen space view, between the space and the brief.
* A **competitor analysis section in the PDF brief**, per competitor.
* A **competitive picture** section in the Coverage view: three progress bars and
  the unread competitors named individually.
* A fifth synthesis lens — *competitor movement* — plus cell targeting: where two
  or more profiled competitors sell into a taxonomy cell the radar has no topic
  for, that cell is promoted to the front of the target list.

**Register.** All 65 competitors gained a `website` and a `scrape` status.

**Schema.** `topic_briefs.brief_schema`, applied by the first additive migration
(`db.MIGRATIONS`) so an existing database — including the deployed one — gains
the column without being recreated.

### Defects found and fixed

| Defect | Consequence | Fix |
|---|---|---|
| **Model echoed the vocabulary list.** Asked for OVHcloud's technologies it returned the first eight ids *in vocabulary order* — every one valid, so closed-vocabulary validation passed all eight. OVHcloud's pages mention 5G zero times. | Wrong tags fed topic seeding and the per-topic join. | Vocabulary tags now require corroboration in the source text, word-boundary matched, minimum four characters. All 53 profiles rebuilt. |
| **A citation proved a page was read, not that it said this.** "Accenture LED Flashlight" arrived as a named offer with a page id attached. | Fabricated product names in a competitive briefing. | Offer names must also appear in the corpus. |
| **Lens rotation never reached the last lens.** `index % len(LENSES)` with 3 passes over 4 lenses meant the cross-vertical lens **never fired, for the life of the pipeline** — and the new competitor lens would have been dead on arrival. | A quarter of the designed generation diversity was unreachable. | The lens window is offset per cluster. |
| **A failed crawl recorded no status.** Eight competitors looked identical to never-attempted. | Coverage counted a refusal as a pending gap. | Every failed crawl records why; the eight were re-run patiently and four recovered. |
| **A failed request rendered as a finding.** The competitor pane checked `!data \|\| entries.length === 0` before checking `error`, so a request that never completed printed *"No competitor from the register is matched to this space"*. | The product's core failure mode, reproduced in its own interface. | Error state renders first, with the message; "not assessed yet" is distinguished from "assessed, matched nobody". |
| **Truncated JSON lost whole artefacts.** Large inputs hit the completion budget mid-string. Two profiles and 23 analyses failed. | The whole artefact was lost rather than its tail. | `max_tokens` raised on both call sites (6000 / 8000); all failures re-run. |
| **Locale detection was too eager.** Any two-letter path segment was treated as a locale, so `/ai/platform` collapsed to `/platform`. | Two genuinely different pages merged into one. | An allowlist of unambiguous language codes; `ai`, `it`, `id`, `is`, `no` are deliberately excluded. |

**Tests.** `tests/test_competitor_intel.py` — 23 tests, including a regression
for each defect above.

---

## Documentation

**Added.** [`API.md`](API.md), [`DATA_MODEL.md`](DATA_MODEL.md),
[`OPERATIONS.md`](OPERATIONS.md), [`DECISIONS.md`](DECISIONS.md),
[`COMPETITOR_INTELLIGENCE.md`](COMPETITOR_INTELLIGENCE.md), this changelog, and a
[docs index](README.md).

`API.md` and `DATA_MODEL.md` are generated from the running application and the
live schema, so they cannot drift from the code.

**Updated.** The Functional Design Document and the Technical Architecture, both
regenerated with the competitor subsystem, the new tables and current figures.
The README.

---

## Earlier

### Documentation set

The Functional Design Document and Technical Architecture were written as Word
documents with 21 programmatically generated diagrams, including a full
crow's-foot ERD across four subject areas. Speaker notes for the deck were
produced from the recorded walkthrough.

### Sources and generation

* Source catalogue grew to **42 catalogued, 33 enabled**, across 17 connector
  types.
* `pipeline/query_grid.py` — collection queries are now derived from the
  taxonomy rather than hand-written literals. `config/sources.yaml` had claimed
  this was already true; it was not, and the first corpus showed it: whole
  branches of a 59-use-case vocabulary had no query at all.
* `connectors/demand.py` — SEC EDGAR full-text search and Adzuna job postings.
  Demand-side leading indicators that precede a tender rather than report it.
* `generation.py` and the Generate screen — on-demand, constrained synthesis
  bounded to a slice of the taxonomy, scoped so that serving five new spaces does
  not re-score the whole radar.
* `internal.py` — internal signal intake with a moderation gate, entering at
  tier 3.

### Serving and deployment

* `bootstrap.py` — a serving instance that cannot open its database now starts,
  says so, and keeps answering. A readable 503 is worth more than an invisible
  restart loop, and on a Free plan a crash loop destroys the evidence of its own
  first failure.
* The read model was rewritten to fetch each table once for the whole set:
  `/api/view` went from **1.69 s and ~1,670 queries to 0.05 s and 11**.

### Interface

Seven independent adversarial reviewers, 82 findings, each handed to a separate
reviewer to refute against the code. Confirmed findings fixed — keyboard
reachability of the primary browsing surface, contrast measured rather than
eyeballed across 10,056 rendered text elements in both themes, server-computed
facet counts, and both radar encodings rescaled to the band the data actually
occupies.
