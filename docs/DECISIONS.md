# Decisions

*The choices that shaped this build, each with the reason and the thing it costs.
A decision without a recorded reason gets re-litigated; a decision without a
recorded cost gets mistaken for a free win.*

---

## D-01 · Two scores, never one

**Decision.** Attractiveness and right to win travel as separate fields end to
end and are never combined into a displayed number. Conviction and competitive
intensity are third and fourth quantities beside them, not inputs to them.

**Why.** Collapsing them destroys the information the strategist needs. A topic
can be excellent for a strategist — large, early, no proof points — and useless
for a salesperson, because there is nothing to show. One number cannot say that.

**Cost.** No single "best topic" ranking exists, so every list needs a role. The
interface has to carry two visual channels (marker size and marker colour) where
one would have been simpler.

---

## D-02 · Portfolio distance drives the role modes

**Decision.** Role modes are not interface presets. Sales sees L0–L1, presales
L0–L2, strategy L1–L4, because that is what each role can act on.

**Why.** "Only topics with enough internal content to credibly back up" sounds
subjective. It has a computable definition: a delivery link at L0/L1, **and** a
published reference in the vertical, **and** no evidence gap. Enforced in the
read model, so re-sorting a list cannot bypass it.

**Cost.** A salesperson genuinely cannot reach white space, even deliberately.
That is intended and occasionally frustrating.

---

## D-03 · Supporting evidence is typed `SUP`, not `L0`

**Decision.** Certifications, analyst positions, published references and
capability pools are linked, displayed and scored — but excluded from portfolio
distance and from the role filter.

**Why.** Every L0–L4 definition in the requirements baseline describes a
*delivery* capability. Typing a certification L0 would mean any topic in a
regulated vertical scored as a direct sell purely because Orange holds ISO 27001,
which makes portfolio distance meaningless.

**Status.** This is an extension beyond the baseline and is **worth confirming
with Orange.**

---

## D-04 · Arithmetic where arithmetic will do

**Decision.** Counting, publisher diversity, recency, momentum, right-to-win and
market sizing involve no model call. Only strategic relevance, the next action,
the narrative and the competitor comparison do.

**Why.** A model asked to count will occasionally be wrong and always be
unverifiable.

**Cost.** More code than "ask the model", and the rubric prompt has to carry
written anchors because a free 0–100 request compresses every answer into the
middle of the scale.

---

## D-05 · Uncited claims are stripped, not rewritten

**Decision.** A claim that cannot cite evidence is deleted. The model is never
asked to fix it.

**Why.** Asking a model to repair an uncited claim teaches it to attach a
citation at random. The cheapest correct answer to "this claim has no source" is
to delete the claim — the remaining ones are still true.

**Cost.** Thinner output, visibly. What was stripped is listed in the interface
rather than quietly omitted, which makes the thinness obvious — deliberately.

---

## D-06 · Market size is computed, never quoted

**Decision.** Two independent methods published side by side; no headline figure
is ever repeated; where the data will not support a number, none is shown.

**Why.** Press figures originate from paid research, are quoted without
methodology, and frequently conflict by an order of magnitude.

**Cost.** Public administration has no Eurostat enterprise count, so those spaces
are sized from observed procurement only — and some are not sized at all. An
absent number is harder to sell with than a confident wrong one.

---

## D-07 · SQLite, on purpose

**Decision.** One file, no database server.

**Why.** The graph is thousands of nodes, not millions. A single file makes the
replay harness a file copy. The serving profile is read-mostly with one writer.

**Cost.** Concurrent curation would serialise. Nothing in the schema prevents a
move to a server-based store, and section 19 of the Technical Architecture
records what would force one.

---

## D-08 · Competitor sites are tier 4, and may only seed

*Added with the competitor intelligence subsystem.*

**Decision.** A competitor's own website is tier-4 "interested party" evidence
everywhere it is scored. A profile may **explain** a competitor already matched
to a topic, and it may **seed** generation. It may not lift any published score.

**Why.** It is definitionally vendor marketing. SC-09 asserts that vendor-only
evidence scores low, and a subsystem that quietly exempted 1,745 vendor pages
from that rule would have hollowed out the guarantee while leaving the test
passing.

**Alternatives considered.** Making profiles ordinary tier-4 signals (rejected:
65 vendor sites would add a lot of low-tier volume and dilute publisher
diversity), and a new tier between practitioner and interested party (rejected:
requires a new weight set and recalibration of every existing score).

**Cost.** A competitor doing something obvious and new cannot, on its own,
create a topic. It can only point at a cell where the *corpus* is then checked.

---

## D-09 · A refusal is recorded, not worked around

**Decision.** Six competitor sites answer 403 to a declared automated client and
one disallows crawling in robots.txt. A browser User-Agent gets through all of
them. It is not used.

**Why.** The project already handles refusals this way — `config/sources.yaml`
records Ofcom as unwired because it 403s automated clients. Applying a different
standard to competitors because the data is more interesting would be exactly
the kind of quiet inconsistency the rest of the design exists to prevent.

**Cost.** 12 of 65 competitors are unprofiled, including Cisco and Fortinet,
which materially thins the competitive picture on security spaces. The gap is
named per competitor in the Coverage view and counted per topic, so it is visible
rather than silent.

**This is a decision with an owner, not a technical limit.** If Orange decides
the trade is worth making, it is a one-line change.

---

## D-10 · A closed vocabulary needs corroboration

*Added after a defect.*

**Decision.** A vocabulary id supplied by a model is kept only if the term also
appears in the source text. Word boundaries, minimum four characters.

**Why.** Asked for OVHcloud's technologies, the model returned the **first eight
ids of the technology vocabulary in vocabulary order**. Every one was valid, so
closed-vocabulary validation passed all eight. OVHcloud's pages mention 5G zero
times. A list-echo is the characteristic failure of handing a model an
enumeration, and the enumeration is what makes it survive validation.

This is the rule `enrichment` already applies to signal attachment —
*"similarity alone is not evidence"* — applied to the same problem elsewhere.

**Cost.** A genuine capability described in words the vocabulary does not use is
dropped. The cost of a false negative is a thinner profile; the cost of a false
positive is a competitor credited with a capability they never claimed, in front
of a customer.

---

## D-11 · Incomplete is not the same as stale

**Decision.** `topic_briefs.brief_schema` records which section set a brief was
rendered with. A brief missing a section that current briefs carry is reported as
**incomplete**, with its own banner and its own regenerate control, separately
from **stale**.

**Why.** A stale brief was correct when it was built and has been overtaken.
An incomplete brief never carried the section, so no amount of waiting fixes it.
Conflating them hides the more actionable of the two.

**Cost.** A migration, and a version constant that has to be bumped by hand when
a section is added.

---

## D-12 · A failed request must not render as a finding

*Added after a defect.*

**Decision.** Every panel distinguishes "the request failed" from "the answer is
empty", and says which.

**Why.** The competitor pane rendered `!data || entries.length === 0` before
checking `error`. A failed fetch produces `data === null`, so a request that
never completed printed *"No competitor from the register is matched to this
space"* — the most confident possible sentence about the competitive field, at
the exact moment nothing was known about it.

That is this product's core failure mode reproduced inside its own interface,
which makes it worse than an ordinary UI bug.

**Cost.** Three states to design instead of two, on every panel that loads
asynchronously.

---

## D-13 · Generation lenses rotate per cluster

*Added after a latent bug.*

**Decision.** The evidence-lens window is offset by the cluster, not fixed at
zero.

**Why.** `GENERATION_LENSES[index % len(LENSES)]` with three passes over four
lenses meant lenses 0, 1 and 2 fired on every cluster and lens 3 fired on none.
The cross-vertical lens was **unreachable for the entire life of the pipeline**,
and every lens added after it would have been dead on arrival.

**Cost.** None. Each cluster still gets three different lenses; the corpus as a
whole now gets all five.

---

## D-14 · A plan is selected by an optimiser, not proposed by a model

**Decision.** Portfolio selection is a mixed-integer program solved by
`scipy.optimize.milp`. The model's only job in the Planner is to *write* the
plan, after every number in it is already fixed.

**Why.** Selection under constraints is a multi-dimensional knapsack. It solves
exactly, in under a second at this size, and it explains itself: which constraint
bound, and what one more euro or one more engineer would buy. A learned
recommender could do none of that, and NFR-01/NFR-03 require every number to
decompose. There are also no labels — 418 spaces and zero historical outcomes is
a spreadsheet, not a training set.

**Cost.** A dependency on scipy, and a greedy fallback that has to be maintained
beside the solver for the case where scipy is absent or the program is
infeasible. The fallback names every soft constraint it relaxed, which is the
only reason it is acceptable at all.

---

## D-15 · A committed set is scheduled, never re-selected

**Decision.** Under `source: workflow` the Planner applies no evidence floor, no
distance cap, no concentration limit and no objective. Every space the stage gate
has moved to Demand-tested or beyond is in the plan. `selected_count` equals
`considered_count`, and a test asserts it.

**Why.** A space at Demand-tested has a salesperson's judgement behind it.
Dropping it for resting on a modelled size, or for sitting one level too far out
on portfolio distance, answers a human decision with an assumption band. The
question in this mode is not "what should we do" — it is "what does what we have
already committed to actually earn, and when".

**Cost.** The two modes cannot share a code path, so scheduling, flagging,
exclusion-reporting and the narrative prompt each split on the source. Where the
committed set over-commits a capability pool the plan reports the gap rather than
resolving it, which means a plan can contain a finding the reader has to act on
rather than a set of numbers that balance.

---

## D-16 · SOM is discounted for overlap before it is summed

**Decision.** A second space in a vertical is discounted; a third sharing its use
case more so. Margin varies by portfolio distance rather than being held at the
filed segment figure.

**Why.** Obtainable share is computed per topic, against the same customers' same
budgets. The naive sum across all 418 spaces reaches 90% of Orange Business's
entire segment revenue, which is not arguable for incremental business in a
segment declining 5.8% a year — and coverage makes it worse rather than better,
which is what proves the problem is the aggregation and not the sizing. Applying
the filed 7.9% margin flat is a second version of the same error: it is a fully
loaded figure, so it understates L0 (existing offer on existing overhead) and
overstates L3 (a build carried in opex inside the window).

**Cost.** Two more assumption bands to argue about, and the discount is a
judgement rather than a measurement. Varying margin by distance moves five-year
profit by about 1.66×, and revenue concentrates at L0 — so the L0 band dominates
the answer, and one table from Orange finance is worth more here than any other
single input including build cost.

---

## D-17 · A collateral piece with missing inputs still builds

**Decision.** Nothing in the pre-sales subsystem refuses to produce a document. A
piece whose declared inputs are missing is rendered anyway, with a banner naming
the gap.

**Why.** A pre-sales engineer who asked for a solution outline and got an error
has nothing. One who got the outline with *"built without the written
description"* across the top has the component map, the portfolio path and a
clear instruction about what to do next.

**Cost.** A document can leave the building in a state its author did not
intend. The mitigation is that the gap is on the page rather than in a log, and
staleness is tracked per input rather than per space — so a pack whose battlecard
predates this month's competitor register is visible as such.

---

## D-18 · The format is the reader's choice, per piece

**Decision.** Documents emit as PDF, Word or OpenDocument; decks as PowerPoint,
OpenDocument or PDF. Formats coexist. A deck is never offered as Word.

**Why.** A battlecard is a PDF in a car park, a Word file on a bid manager's desk
and an ODF file on an estate that standardised on LibreOffice — and it is the
same battlecard in all three. Tender blocks are Word because paste-fodder as a
PDF actively obstructs. A deck flowed into a Word document stops being a deck,
because one idea per page is the only property that made it one.

**Cost.** Thirty-three (piece, format) pairs that must all say the same thing.
That is why documents are described as *blocks* and emitters walk them, rather
than each format being written out — but it is a real cost, and a chart in Word
is a raster image because Word has no drawing model this code can target.

---

## D-19 · The corpus enables the Generate button, not the model

**Decision.** `ready` on a proposed brief is whether the corpus can actually
support a run. The model's own opinion travels beside it as `model_ready`, and
the screen explains either disagreement rather than obeying one of them.

**Why.** Asked "do you have enough?" a model says yes — so overruling an
over-optimistic model is the obvious half. The other half turned out to matter as
much: the assistant is told to put a brief forward even while hedging about the
evidence, because otherwise a genuinely new idea has nothing to press Generate
on. It duly writes "the evidence is thin, marking this as not ready", which is a
fair remark about the corpus and a terrible reason to disable a button whose
brief has already passed the same corroboration check the run applies.

**Cost.** Two flags where a reader expects one, and a screen that has to explain
a disagreement in either direction.

---

## D-20 · The gate judges the brief's sentence, not its taxonomy labels

*Added after a run that produced nothing, expensively.*

**Decision.** Corroboration is decided by asking the cheap model about the
brief's own sentence, with the taxonomy labels shown as the approximation they
are. Its answer overrules a label match. The vocabulary test stays, for display,
where the two agree.

**Why.** The taxonomy is a set of closed lists, so a proposal is regularly filed
under the nearest available cell rather than an exact one. A brief for
advertising-funded municipal screens filed under `citizen_service_automation` ×
`private_5g`, because nothing closer exists. Tenders for private-5G video
surveillance corroborate the *label* perfectly and are no evidence whatsoever for
advertising screens. The gate reported four supporting signals, the button
enabled, the run spent four model calls, and the critic threw the candidate out
with precisely that reason.

**Cost.** One cheap model call per proposed brief, and a gate whose verdict is a
model's judgement rather than a string match — which is exactly what the
vocabulary test was there to avoid. Keeping the vocabulary test for display is
the compromise: *"the term 'private 5g' appears in the signal text"* is a more
checkable thing to show a reader than a model's say-so.

---

## D-21 · Sign-in is a session in the database, not a signed token

**Decision.** An `HttpOnly`, `SameSite=Lax` cookie, stored server-side only as
its SHA-256, checked by an application-level dependency rather than a decorator
per route. Passwords are PBKDF2-HMAC-SHA256 verifiers from the standard library.

**Why.** A JWT cannot be revoked without server state, which puts the state back
anyway — and the thing an operator actually wants ("sign that account out
everywhere, now") is one `DELETE` here and impossible there. The database is a
file on a share, so a copy of it must not be a set of live sessions or a set of
passwords. PBKDF2 is not the best KDF; it is the best one available with **no new
dependency**, which is what keeps the sovereign-deployment option cheap. And the
failure mode of a per-route guard is the route somebody forgot, which is why the
test walks the router rather than naming endpoints.

**Cost.** A sessions table to sweep, and a KDF weaker than argon2. Sign-in
answers *who*; it does not yet answer *may they* — per-role authorisation on the
write endpoints is still absent, and so is rate limiting on the endpoints that
spend model budget.

---

## D-22 · A delete is legible before it is taken, and signals survive it

**Decision.** The delete dialog asks the server for the impact and reads it out
before showing the button. Only attachment rows go; the signals themselves stay.
Duplicates folded into the space go with it. A plan that selected the space is
named rather than blocking the delete.

**Why.** The `DELETE` was never the hard part — thirteen tables point at a space
and the keys already cascade. A signal is evidence about the world that several
spaces may cite, collected under DR-01 and retained for replay under DR-14;
deleting a synthesis result must not delete the reading it was synthesised from.
And refusing the delete would make any space that ever appeared in a plan
permanent, while silently breaking the plan would be worse.

**Cost.** A plan's stored `projection` and `selected_count` — computed once and
immutable by design — go on counting a space that no longer exists. That is
declared rather than repaired. **Deletion is also not suppression**: identity is
the taxonomy triple, so a later refresh meeting the same triple will synthesise
the space again, with a new id.

---

## Open decisions

These need a human and are not engineering tasks.

| Question | Why it matters |
|---|---|
| **Who is the curator?** | 4,832 links are machine-proposed. The first occurrence of each pattern needs a named human, and without one quality drifts. |
| **Is the four-year contract assumption right?** | Tender notices publish a contract's whole value; annualising needs a duration. Every size moves inversely with it. |
| **May a browser User-Agent be used?** | See D-09. Twelve competitor profiles depend on the answer. |
| **What is the refresh cadence?** | Drives connector design and cost more than any other choice. Currently a 14-day period, which is also the unit the lifecycle counts in. |
| **Do internal taxonomies exist?** | The 59 use cases and 38 technologies are a drafted Sprint 0 deliverable and should be replaced if an internal catalogue exists. |
| **What is the real margin by portfolio distance?** | `config/economics.yaml` carries planning bands anchored on the filed 7.9% segment figure. Varying margin by distance rather than holding it flat moves five-year profit by about 1.66×, and revenue concentrates at L0 — so one table from Orange finance is worth more than any other single input to the Planner. |
| **How much capability-pool headcount is free for new work?** | `pool_availability` decides how many spaces a plan can start at once, and the shipped default is a guess. It is the constraint that binds first in most parameter plans. |
| **Who owns the economics assumptions?** | `owner:` currently reads `innovation-radar-curator`, which is a placeholder. Every plan prints it on its last page. |
| **Which accounts should exist, and who administers them?** | Sign-in exists; per-role authorisation on the write endpoints does not. Today every signed-in account can move a stage, delete a space and spend model budget. |
| **Terms of use** | Unconfirmed for several enabled sources. A Sprint 0 blocker, not a runtime concern. |
