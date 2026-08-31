# Testing, limitations, open questions, and security

## Tests

```bash
python3 -m pytest tests/ -q      # 486 tests
```

They cover the invariants that would be expensive to discover late: score
reproducibility (SC-11), syndication collapse and tier-4 discounting (SC-03),
vendor-only evidence scoring low (SC-09), evidence binding stripping uncited
claims, specificity validation rejecting the briefing's named negative examples,
triple-based identity and merge, link typing and portfolio distance, horizon
derivation, the lifecycle state machine, evidence-gap warnings (SC-13), and
publication-date leakage control (FR-35).

The competitor suite (23 tests) holds the line on the newest subsystem: that a
vocabulary tag the model supplied is dropped unless the pages corroborate it;
that a named offer citing a page the page does not support is dropped; that a
differentiation paragraph naming an unlinked Orange asset is stripped while the
activity half survives; that a competitor absent from the topic cannot be added
by the model; that a competitor whose site refused us is _marked_ rather than
omitted; and that re-running the cheap join never discards an expensive
comparison that still holds.

The sizing, competition and brief suites (48 tests) hold the same kind of line:
that the denominator and the adoption rate share a size base; that a crosswalk's
per-row confidence reaches the arithmetic rather than sitting in the CSV; that
only a tender whose _main object_ is an IT contract may price an engagement; that
a proxy widens the range without moving the base; that the confidence grade is
the worst factor rather than an average; that SAM never exceeds TAM; that an
uncited factual section is stripped; that a generated percentage or euro figure
kills the section carrying it; that an unsupplied organisation does the same; and
that a diagram box cannot claim an Orange asset the graph does not hold.

The planner, collateral, scoping, auth and deletion suites (137 tests) hold the
newest lines: that identical inputs give an identical plan id, so a plan cannot
be silently recomputed under changed assumptions; that a capability pool is never
over-committed under the optimiser and _is_ reported when a committed set
over-commits it; that `selected_count == considered_count` under the workflow
source, because nothing there may be dropped; that a committed space with no
market size is declared rather than quietly missing; that **every text frame on
every generated slide fits its box**; that a collateral piece with a missing
input still builds and says so; that a second format coexists with the first
rather than replacing it; that `ready` on a proposed brief is the corpus's
verdict rather than the model's; that a brief corroborated only on its vertical
is refused; that signals survive a delete while their attachments do not; and
that a plan which selected a deleted space is named rather than blocking the
delete.

The auth suite is worth one more sentence, because of _how_ it tests. It **walks
the router** rather than naming endpoints, so a route added without the guard
fails a test that already exists. The failure mode of a per-route guard is the
route somebody forgot, and a test that names endpoints has exactly the same
failure mode.

Several of these tests caught real bugs during the build:

- Shannon entropy is scale-invariant, so a uniform tier-4 discount cancelled out
  entirely — six vendor blogs scored identically to six independent outlets.
  Fixed by applying the discount to the effective publisher count.
- Certifications were typed L0, making portfolio distance meaningless for every
  topic in a regulated vertical.
- `build_graph` wiped `graph_nodes` while `opportunity_links` held a foreign key
  onto it, so a second rebuild failed. Fixed by upserting nodes and retiring the
  disappeared ones — which is also where LK-07 (withdrawn assets propagating to
  affected topics) now lives.
- The exploration slot (§4.7.6) drew from all filtered topics rather than
  role-eligible ones, so it could show a salesperson a topic with no proof point
  — bypassing the very filter §4.5.3 requires.
- A slide test that checked only the bullet column passed while four chart labels
  on the same slide overflowed off the edge. It now walks _every_ text frame on
  every slide, which is what should have been asserted the first time.
- The scoping gate corroborated a brief against its taxonomy **labels**, and the
  labels are approximations — closed lists of 15 verticals, 59 use cases and 32
  technologies mean a proposal is filed under the nearest available cell. Tenders
  for private-5G video surveillance duly "corroborated" a brief about
  advertising-funded municipal screens, the button enabled, and the critic threw
  out every candidate the run produced. The gate now judges the brief's own
  sentence.

---

## What is deliberately not built

Matching the MVP exclusions in Table 15, plus what this pass did not reach:

| Not built                   | Why                                                                                                                                                                                                                       |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CRM integration             | Deferred by the briefing; public assets give a sufficient right-to-win proxy                                                                                                                                              |
| Learned scoring models      | No labels exist on day one. The MVP ships the transparent baseline and the capture/replay harness the learned models need (§4.7)                                                                                          |
| Patent connector            | Needs EPO OPS registration or BigQuery credentials. Technology ownership currently uses a portfolio-level prior from `technologies.yaml`                                                                                  |
| Headless-browser rendering  | Three competitor sites render client-side only. Adding a browser to a pipeline that deliberately has none, for three profiles of sixty-five, is not the trade                                                             |
| Learned per-role ranking    | Needs 300–600 expert comparisons; the capture widget ships first                                                                                                                                                          |
| Backtest evaluation harness | The replay path exists (FR-35); the metrics of §4.7.5 are not implemented                                                                                                                                                 |
| Per-role authorisation      | Sign-in answers _who_; it does not yet answer _may they_. Every signed-in account can currently move a stage, delete a space and spend model budget                                                                       |
| Rate limiting on generation | Sign-in bounds who can reach the endpoints that spend model budget, not how often they may                                                                                                                                |
| ROI on a plan               | There is no cost data at the granularity a space would need — not in the filings, not anywhere the pipeline can reach. Revenue and profit are defensible from what exists; an ROI would require inventing the denominator |

Two rows moved out of this table during this pass and are worth naming, because
both were listed as _not built_ in an earlier edition of this README:
**collaboration workflow (FR-25)** is the stage gate and per-role assessment
described above, and **slide export** now exists — not as a PowerPoint variant of
the brief, but as four of the twelve pre-sales artefacts, which is what the
request was actually for.

---

## Open questions for Orange

§4.13 lists thirteen. The four that most affect the code as written:

1. **Refresh cadence** — drives connector design and cost more than any other
   decision. Currently `period_days: 14`.
2. **Sovereign deployment** — may an external model API be used during the MVP?
   The abstraction supports Ollama today; the question is whether it must be
   exercised now.
3. **Internal taxonomies** — the 59 use cases and 38 technologies are a drafted
   Sprint 0 deliverable. If an internal catalogue exists it should replace them.
4. **Who is the curator?** 5,217 links are currently unconfirmed. LK-06 requires a
   named human to adjudicate the first occurrence of each link pattern, and
   without one, quality drifts. The same question now applies twice over: the
   sizing assumptions in `config/sizing.yaml` (contract duration, size-class
   weights, obtainable share) and the 65-entry competitor register both carry
   `innovation-radar-curator` as a placeholder owner, and both will appear in
   front of customers.
5. **Is the four-year contract assumption right?** TED publishes a contract's
   whole value, and annualising it needs a duration. Four years is the figure
   used and printed; an Orange bid team will have a better one, and every size in
   the radar moves inversely with it.
6. **May a browser user agent be used for competitor profiling?** Six competitor
   sites — including Cisco and Fortinet — answer 403 to a declared automated
   client. A browser agent gets through all of them, and not using one costs
   twelve profiles that thin the competitive picture on security spaces most.
   Recorded as a refusal rather than routed around; the decision is Orange's.

7. **How wide is the private-sector proxy?** Contract values are observed from
   public procurement because that is the only attributable source available.
   Where Orange has its own won-deal distribution, substituting it would move
   these estimates off a proxy and onto evidence.

---

## Security note

`.env` is gitignored and holds the DeepSeek API key supplied for development.
That key was shared in plaintext over chat, so **rotate it before any wider
use**, and issue a separate key for CI.

Every `/api` path now requires a session (`src/radar/auth.py`), which closes the
two things that made a public deployment unsafe to show anyone: it answered every
request it received, and anyone with the URL could spend the deployed model key.
The guard is an application-level dependency rather than a decorator per route,
because the failure mode of a per-route guard is the route somebody forgot, and
`tests/test_api_auth.py` walks the router instead of naming endpoints for the
same reason.

Three things are still absent and are named rather than implied:

- **Per-role authorisation.** Sign-in answers _who_, not _may they_. Every
  signed-in account can move a stage, delete a space and spend model budget.
- **Rate limiting on the generation endpoints.** Sign-in bounds who reaches them,
  not how often.
- **An audit log** distinct from the workflow transition history.

The seeded account is `orange` / `orange`, flagged `must_change_password`, and
the interface warns on every screen until that is cleared. Accounts are created
only from the command line (`radar user add`), so a hijacked session cannot mint
itself a permanent login.

