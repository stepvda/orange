# Changelog

Notable changes to the Innovation Radar, most recent first. Defects are recorded
alongside features, because several of the defects are more instructive than the
features that exposed them.

---

## The Planner will plan the business you have already committed to

**Added.** A second source for a plan. The Planner asked for parameters and
chose a portfolio under them; it now also takes the portfolio as given —
*Workflow selected* builds the plan from every opportunity space the
collaboration board has moved to **Demand-tested or beyond**, and computes the
rest.

* **The stage gate outranks every constraint, and none of them is applied.** A
  space at Demand-tested has a salesperson's judgement behind it. Dropping it
  for resting on a modelled size, or for sitting one level too far out on
  portfolio distance, answers a decision with an assumption band. So under this
  source there is no evidence floor, no distance cap, no concentration limit and
  no objective — because there is nothing to optimise. `selected_count` equals
  `considered_count`, and a test asserts it.
* **Horizon spreads the set across time.** Each space enters when its horizon
  says the market arrives — `now` may start in year one, `later` not before year
  three — and a cohort larger than a year's entry slots cascades into the next
  year rather than pretending the capacity exists. Within a cohort the earlier
  slots go to the largest commitments, so an over-subscribed year defers the
  smallest rather than an arbitrary set.
* **A Live space starts in year one whatever its horizon says.** The horizon
  describes when the market arrives, which is a question already answered for
  something that is already selling. Scheduling it into year three would be
  projecting a start date for something that has started. The stage pulls entry
  forward; it never pushes it back.
* **Over-commitment is the finding, not a reason to edit the portfolio.** Under
  the optimiser a capability pool cannot be over-committed — it would not have
  selected past one. Here the business already has, so nothing is dropped to
  make the numbers work: the pool that peaks above its available share is
  flagged with the size of the gap, and the plan names what closes it — hiring,
  partnering, raising the share available for new work, or moving a space back
  down the gate.
* **A committed space with no market size is declared rather than dropped.** It
  is in the plan as far as the business is concerned and absent from every
  figure on the page. Left silent it understates a portfolio the reader believes
  is complete, so it is listed by id, flagged, and the totals are described as a
  floor.
* **What is *not* in the plan says whose decision that was.** The exclusions
  list under this source names a stage rather than a constraint: still at
  Shortlisted, stopped on the board, or unsized. Nothing there was excluded by
  the Planner, and the document says so.
* **The prose knows which question it is answering.** A narrative written for a
  committed set may not describe alternatives being weighed, because none were.
  The system prompt splits on the source (`plan-v2`), the evidence block states
  where the set came from, and the exported PDF opens with *this plan did not
  select anything* — before the first figure, because everything below it reads
  differently once the reader knows that.
* **Two sources, two plans.** The source is part of the plan's fingerprint, so a
  committed plan can never quietly overwrite the parameter plan it was built to
  be compared against.
* **Failure speaks in the terms of the mode that was used.** An empty board
  sends the reader to the workflow board and says how many spaces are waiting a
  stage earlier. Telling them to loosen a confidence floor would send them to a
  control that is not on their screen.

Reachable from the Planner sidebar, from `POST /api/planner/plans` with
`source: "workflow"`, and from `radar plan --source workflow --from-stage
demand_tested`.

---

## Pre-sales collateral: twelve documents per space, in the format you work in

**Added.** A fourth tab on the full-screen view of an opportunity space. The
brief is one document for one conversation; this is what the team needs between
that conversation and a proposal — a discovery and qualification pack, an
outreach sequence, a first-meeting deck, a value hypothesis, a reference pack,
competitor battlecards, a solution outline, a PoC scoping sheet, a partner
brief, commercial model options, tender response blocks and a bid risk register.

* **One snapshot, twelve documents.** `presales.context.load` reads the space
  once and every renderer works from that. Two documents in the same pack
  quoting different SAM figures — because one was built before a sizing run and
  one after — is the failure this makes impossible rather than unlikely.
* **The format is the reader's choice, per piece.** Documents emit as PDF, Word
  or OpenDocument; decks as PowerPoint, OpenDocument or PDF. The default is the
  format the artefact wants to be: a battlecard is a PDF because it is read on a
  phone and must not have been edited since it was approved; tender blocks are
  Word because a PDF of paste-fodder is obstructive. Formats coexist — asking
  for Word after you have the PDF gives you both, because that is obviously what
  was meant. A deck is never offered as Word: one idea per page is the only
  property that made it a deck.
* **A document is described once and emitted many times.** Seven documents by
  three formats plus four decks by three is thirty-three places for the same
  battlecard to say something slightly different, and within a month two of them
  disagree. So `documents.py` and `decks.py` describe blocks, and `emitters.py`
  puts a block on a page. Adding a format is one emitter.
* **Charts are vector where it matters.** Eleven chart types drawn with exact
  geometry: a TAM/SAM/SOM funnel, a value waterfall, a payback curve, a
  competitive field map, a risk matrix, a buying-centre map, a component
  ownership map, a portfolio path, a phase timeline, a scope boundary and
  coverage bars. In PowerPoint they are NATIVE SHAPES, so an architect moves a
  box rather than redrawing the slide; in PDF they are reportlab geometry. Word
  and ODF get the same picture rasterised, because neither has a drawing model
  this code can target — the trade is deliberate and the right way round, since
  the formats people send and edit both get true vector output.
* **The palette was validated, not chosen.** Each colour does exactly one job —
  identity, order, magnitude, polarity or state — and the ordinal and
  categorical sets were run through a contrast and colour-vision check rather
  than eyeballed. The brand rule the brief established is kept: orange means
  Orange, or it means emphasis. It is never slot four of a competitor palette,
  which is why the field map names competitors instead of colouring them.
* **It looks at the public record before writing.** The corpus is refreshed on a
  cadence and a battlecard is written the morning of a meeting; a regulator's
  deadline or a competitor's announcement lives in that gap. `research.py` runs
  targeted queries through the connectors the pipeline already trusts — same
  `HttpSession`, same throttling, same robots discipline, content by reference
  only (DR-08). Anything drawn from a retrieved item must name its publisher
  inline, and every item the writer saw is listed at the back so the citation
  can be followed. Those items have not been through the radar's evidence
  validation and the document says so.
* **Stricter about numbers than the pipeline is, on purpose.** `_NUMERIC_CLAIM_RE`
  lets bare counts through, because inside the pipeline a number is about to
  meet the entailment check. Nothing here meets one — it goes to a customer. So
  "1,200 plants in scope" is stripped too: it is a claim about the customer's
  own estate, it reads as researched, and it is invented.
* **A piece whose inputs are missing still builds**, with a banner naming the
  gap. An outline saying "built without the written description" is more use
  than an error: it still carries the component map and the portfolio path.

**Fixed.** Every generated `.pptx` opened with PowerPoint's *"needs repair"*
dialog. Killing the theme's drop shadow by removing `<a:effectRef>` from
`<p:style>` breaks `CT_ShapeStyle`, which requires all four of `lnRef`,
`fillRef`, `effectRef` and `fontRef` in that order. The reference now points at
`idx="0"` — the schema's own way of saying "no effect" — so the element stays
and the shadow still goes. A file users have to click through a repair prompt
to open is worse than a drop shadow, and nothing in a rendered slide shows it:
the test asserts on the XML.

**Fixed.** Slide bullets printed on top of each other. They were advanced by a
fixed 0.5in step, which assumes one line each; the prompts ask for twelve-word
bullets and the model routinely returns paragraphs, so four bullets wrapping to
three lines apiece overprinted into an unreadable block that still looked like a
slide. Bullets are now measured and advanced by their real height, and the type
steps down when the block would not otherwise fit. The regression test asserts
on the space RESERVED against the text in it — a box-overlap test passes
trivially while the bug is present, because the boxes stay one line tall and it
is the text that spills out of them.

**Fixed.** Diagrams ran off the bottom of the slide. Layer bands and component
boxes used constant heights chosen for a slide with nothing above them; a
five-layer solution diagram ran an inch past the edge, losing the physical
layer — the row describing the customer's own estate. Bands and boxes are now
sized to the space actually left, every chart clamps its height to the room
below it, and the legend is dropped rather than the last layer.

**Fixed.** `ThreadPoolExecutor.map(timeout=)` bounds only the iteration — the
executor's `__exit__` then joins every outstanding thread, so a nominal
25-second research budget took 58 real seconds against a throttled source.
Futures, an explicit deadline and `shutdown(wait=False, cancel_futures=True)`
is what actually bounds it.

**Fixed.** `reportlab` was declared only in `requirements-azure.txt`, so a fresh
local install could not build a brief at all.

**Note.** `topic_collateral` is keyed on (space, kind, format). A database that
saw the intermediate single-format schema is rebuilt on startup — the table
holds only pointers to derived files, every row is reproducible by pressing
Generate, and left in place every request 500s on the missing column. The
generated files are left on disk.


## A sign-in in front of the whole app

**Changed.** Every `/api` path now requires a session. Until this, the deployed
radar answered every request it received: competitive analysis of named
companies, Orange's own asset graph, market estimates with the workings
attached, brief PDFs stamped *Internal*, and the stage-gate opinions of people
who work here — served to whoever found the hostname. The README named this as
the thing to fix before the app went anywhere real. This is that fix.

* **One account exists on a fresh database: `orange` / `orange`.** It is created
  only when the user table is EMPTY, which is the difference between a
  convenience and a back door — an operator who deletes it and creates their own
  must not find it resurrected by the next restart. It is flagged
  `must_change_password`, and the interface carries a banner on every screen and
  a mark beside the account name until that flag clears. A default credential
  nobody is reminded about is a permanent one.
* **The guard is an application-level dependency, not a decorator per route.**
  The failure mode of a per-route guard is the route somebody forgot, so there
  is no route-level opt-in to forget: a handler added next month inherits it.
  The test walks the router rather than naming endpoints, for the same reason.
  Being a dependency rather than middleware also puts it inside FastAPI's
  exception handling and inside CORS, so a refusal is an ordinary `detail` the
  frontend already knows how to read.
* **Nothing replayable is stored.** Passwords are PBKDF2-HMAC-SHA256 verifiers
  at OWASP's current iteration count, salted per password, with the count
  stamped into the hash so raising it re-hashes each password on its next
  sign-in rather than forcing a reset. The session cookie is stored only as its
  SHA-256. A copy of the database file is therefore neither a set of passwords
  nor a set of live logins — which matters disproportionately here, where the
  database *is* a file on an SMB share.
* **The refusal says nothing.** An unknown account and a wrong password produce
  the same message, and an unknown account still pays for a hash so a miss costs
  the same as a hit. Identical wording with a 5 ms answer for "no such user" is
  an enumeration oracle wearing a disguise.
* **Sessions in the table, not signed and stateless.** A JWT cannot be revoked
  without server state, which puts the state back anyway — and the thing an
  operator actually wants ("sign that account out everywhere, now") is one
  `DELETE` here and impossible there. Expiry is rolling with an absolute
  ceiling, and checked on read, so a session stops working the moment it expires
  rather than the next time somebody else signs in.
* **Five failed sign-ins close an account for five minutes**, including against
  the right password — a throttle that steps aside for a correct guess is not a
  throttle.
* **Accounts are managed from the command line**, `radar user add|passwd|list|
  remove|signout`. The web interface can change its own password and nothing
  else: handing the running app the power to mint logins would turn a session
  hijack into a permanent one. Changing a password ends every other session for
  the account and reissues the one that did it.
* **The bundle and `/healthz` stay open.** The login screen is part of the
  bundle, so a guard in front of it locks the door from the inside; and a
  liveness probe answering `401` makes every deployment look unhealthy, which on
  this plan means restarts until the quota runs out.

**Defect found while building it.** `:root[data-theme="dark"]` never carried the
`--status-*` group, so a reader who chose dark on a light-preference machine got
the *light* danger colour — `#b3261e` on `#1a1a19`, 2.6:1 — for the evidence-gap
badge and the warning box. Adding a delete button to the same token is what made
it worth finding. The group is now declared in both dark blocks, and text on a
danger fill uses a new `--status-serious-ink` that flips with it: the dark
palette lightens the fill to `#ff9c78`, and white on that is 2.1:1.

---

## Deleting an opportunity space

**Added.** A space can be removed, from the bottom of the detail pane and from
`radar delete-space`. It could not be before — the only way to retract a
synthesis result was to edit the database by hand, which meant nobody did, and
spaces that were wrong stayed on the radar being counted.

The `DELETE` was never the hard part; thirteen tables point at a space and the
foreign keys already cascade. What needed deciding was what a delete is allowed
to take with it, and how much of that a person is told before they agree to it.

* **The dialog reads the consequence out first.** It asks the server what would
  go — 51 evidence attachments, 11 asset links, 6 stored scores, an assessment, a
  stage-gate position, two market estimates, the description, the competitive
  read, the brief — and shows the list before it shows the button. "Are you
  sure?" over a number nobody was shown is not a confirmation. The id has to be
  typed to enable the button: this control sits near "Regenerate description",
  both are one click, and only one of them is irreversible.
* **The signals stay, and the dialog says so as loudly as it says the rest.**
  Only the attachment rows go. A signal is a reading of the world that several
  spaces may cite, kept for replay under DR-14, and a reader who believes 47
  sources are about to be destroyed will not press the button — and would be
  right not to.
* **Duplicates folded into the space go with it.** A row with `merged_into` set
  says "this triple is the same topic as that one". Clearing the pointer instead
  would resurrect duplicates against the identity rule, and `idx_os_triple`
  would refuse them anyway.
* **A space inside a portfolio plan is reported, not refused.** `plan_selections`
  cascades, so the plan loses a row while its stored projection and space count —
  computed once and immutable by design — still include it. Refusing would make
  any space that ever entered a plan permanent; silently breaking the plan would
  be worse. So the dialog names the plans, before and after.
* **Deleting is not suppression, and the dialog says that too.** Identity is the
  vertical × use case × technology triple (DR-03), so a later refresh that meets
  the same triple in the evidence will synthesise the space again, with a new id
  and none of the history removed. Removing a space is a statement about the
  corpus as it stands, not a permanent veto.

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
