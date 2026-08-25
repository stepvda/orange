/** Help content, in one place.
 *
 * The radar is full of terms that are precise inside the requirements document
 * and opaque outside it — portfolio distance, conviction, evidence gap, source
 * tier, exploration slot. A user who does not know what "L2" means cannot act
 * on a topic, which defeats AC-03.
 *
 * Each entry explains WHAT the thing is, WHY it works that way, and WHERE it
 * comes from in the requirements, so the answer is checkable rather than just
 * assertive.
 */

export interface HelpEntry {
  title: string
  body: string[]
  /** Requirement or section this behaviour is traceable to. */
  ref?: string
}

export const HELP: Record<string, HelpEntry> = {
  radar: {
    title: 'The radar view',
    ref: '§4.9',
    body: [
      'Four dimensions at once, without a legend you have to study:',
      '**Angular sector** is the business domain. **Distance from the centre** is the time horizon — Now at the middle, Later at the rim. **Marker size** is attractiveness. **Marker colour** is right to win, on a light-to-dark scale.',
      'Position carries identity here, which is why the colours are one hue rather than six: colour encodes a *quantity*, never which topic is which.',
      'A `!` inside a marker means an evidence gap — Orange has few or no published references in that vertical.',
      'Click a marker to open the topic. Hover for a summary.',
    ],
  },

  attractiveness: {
    title: 'Attractiveness — "is the world moving?"',
    ref: 'SC-01, Table 27',
    body: [
      'A 0–100 score built from five components, each computed from the evidence attached to the topic:',
      '**Market signal strength (30%)** — how many distinct, relevance-gated signals mention it, log-compressed so one noisy topic cannot saturate the scale.',
      '**Source diversity (20%)** — Shannon entropy over the publishers, with syndicated copies collapsed and vendor sources discounted. Twenty outlets carrying one press release count as one source, not twenty.',
      '**Evidence quality (20%)** — a tier-weighted mean, with a penalty when no authoritative or independent source is present at all.',
      '**Novelty and momentum (15%)** — the slope of signal volume over the trailing periods.',
      '**Strategic relevance (15%)** — scored against the three *Trust the future* ambitions using a written rubric with anchored levels.',
      'Every component stores the inputs that produced it, so any number here can be reproduced.',
    ],
  },

  right_to_win: {
    title: 'Right to win — "can we play, can we win?"',
    ref: 'SC-12, SC-15',
    body: [
      'Computed from the Orange Business Graph as **named query results**, never asserted by a language model: matching offers, published references in the vertical, partner tiers, certifications, analyst positions, capability pools and technology ownership.',
      'It is deliberately kept **separate** from attractiveness and never combined with it. The two answer different questions and are owned by different people — a topic can be excellent for a strategist (large, early, no proof points) and useless for a salesperson (nothing to show a customer).',
    ],
  },

  conviction: {
    title: 'Conviction — "do our own people believe it?"',
    ref: 'FR-25, §4.10 model C',
    body: [
      'A **third** quantity beside attractiveness and right to win, built from what the three roles say rather than from evidence or assets.',
      'Each role rates only its own axis: strategy rates strategic fit, sales rates customer demand, presales rates deliverability. A salesperson is authoritative about whether customers are asking, and is not being asked to re-judge the evidence base.',
      'Ratings are 0–5 with written anchors and a separate confidence, because people are unreliable at rating something "73 out of 100" but reliable at picking a level with a description attached.',
      '**Conviction never changes attractiveness or right to win.** It only changes what surfaces first for each role. Internal judgement adjusts discovery; it does not replace it.',
      'A topic nobody has rated sits neutral, not last — "nobody has looked yet" is not the same as "everybody hates it".',
    ],
  },

  divergence: {
    title: 'Divergence — the review trigger',
    ref: '§4.10 model C',
    body: [
      'Where the team and the evidence disagree by more than the configured threshold, the topic is flagged for review rather than averaged away.',
      'Two comparisons are made: **customer demand vs attractiveness**, and **deliverability vs right to win** — in each case a published score against the role whose job it is to know better.',
      'This is the most interesting row in the system. If sales rates demand far below a high attractiveness score, either the radar is reading the market wrong, or the market is moving before the sales conversations are. Either way a human should look.',
      'Disagreement is information, not friction.',
    ],
  },

  portfolio_distance: {
    title: 'Portfolio distance (L0–L4)',
    ref: 'FR-30, §4.5.3',
    body: [
      'The shortest path from an opportunity space to a configuration Orange could actually deliver:',
      '**L0 Direct** — an existing offer addresses it as it stands. Sales: sell it.',
      '**L1 Bundle** — two or more existing offers combined. Presales: package it.',
      '**L2 Partner-dependent** — needs a capability a partner already holds. Presales/alliances: assemble it.',
      '**L3 Adjacent** — needs one capability built or acquired, but nearby assets exist. Strategy: study it.',
      '**L4 White space** — no plausible path from the current portfolio. Strategy: watch it, or reject it explicitly.',
      'This is what drives the role modes: sales sees L0–L1, presales L0–L2, strategy L1–L4. A high-attractiveness L4 topic is exactly the strategist\'s innovation agenda — and exactly what a salesperson should never be shown.',
      '**SUP** marks supporting evidence — a certification, a reference, an analyst position. These strengthen the case but deliver nothing on their own, so they never shorten the distance.',
    ],
  },

  evidence_gap: {
    title: 'Evidence gap',
    ref: 'SC-13, §2.7',
    body: [
      'Orange\'s published reference corpus is very unevenly distributed — manufacturing has 27 published stories, bank and insurance has 4, media and gaming 2.',
      'A radar that ignored that asymmetry would hand a salesperson a banking topic with no proof point behind it. So where reference density in a vertical falls below the threshold, the topic carries an explicit warning instead of being silently averaged.',
      'The warning is a shape (`!`) and a label, never colour alone.',
    ],
  },

  source_tier: {
    title: 'Source tiers',
    ref: '§4.3.7',
    body: [
      '**Tier 1 — authoritative**: legal instruments, regulators, official statistics, standards releases, procurement notices, peer-reviewed research.',
      '**Tier 2 — independent reporting**: established trade and general press with editorial independence.',
      '**Tier 3 — practitioner**: developer telemetry, community discussion, preprints.',
      '**Tier 4 — interested party**: vendor press releases, sponsored content, marketing blogs. Capped contribution.',
      'No topic can reach high attractiveness on tier-4 evidence alone. A corpus that is *all* tier 1 is not automatically better, though — it usually means the independent press and practitioner voices are missing.',
    ],
  },

  horizon: {
    title: 'Time horizon — Now / Next / Later',
    ref: 'FR-08, §4.8',
    body: [
      'Derived from evidence wherever possible rather than judged, because a derived classification is explainable and consistent.',
      '**Now** — a budgeted procurement inside twelve months, or an adopted instrument plus published deployment evidence.',
      '**Next** — regulation adopted or proposed but not yet applicable, or pilots published with no volume procurement.',
      '**Later** — research and standards activity only, or an open policy consultation.',
      'Each topic records which test was applied, so the classification can be argued with.',
    ],
  },

  lifecycle: {
    title: 'Lifecycle state',
    ref: 'FR-09, Table 32',
    body: [
      '**Candidate** — generated but not yet validated.',
      '**Watchlist** — real but thin: evidence exists below the promotion threshold.',
      '**Active** — meets thresholds on signal volume, source diversity and evidence quality.',
      '**Fading** — was active, momentum now negative.',
      '**Dormant** — no qualifying signal for several periods; retained for history, not shown by default.',
      'A topic whose signal flow stops does not vanish — it decays through these states. That is how "topics enter, rise and fade" actually gets implemented.',
    ],
  },

  why_hot: {
    title: 'Why it is hot now',
    ref: 'FR-14, AC-01',
    body: [
      'Every claim here is bound to the signal identifiers that support it, and each chip links to the original dated source.',
      'The model is not allowed to write an uncited claim — uncited claims are stripped rather than rewritten. It is also forbidden from generating any number: market sizes, growth rates and percentages are looked up and attributed, or they are absent.',
      'A second model pass checks that each claim is actually entailed by the span it cites.',
    ],
  },

  links: {
    title: 'Can we play, can we win',
    ref: 'FR-29, LK-08',
    body: [
      'Named, individually inspectable assets — never an aggregate assertion that "Orange has relevant capabilities".',
      'A sentence claiming relevant assets is unverifiable. A link to a named offer, a named reference and a named partner tier is inspectable, and can be wrong in a way someone can correct.',
      '**Unconfirmed** means no curator has yet adjudicated this link pattern. The first occurrence of each pattern needs human confirmation; later occurrences inherit the decision.',
    ],
  },

  role_modes: {
    title: 'Role modes',
    ref: 'FR-13, FR-31',
    body: [
      'The same data, three different ranking functions — not one score with different filters.',
      '**Strategist** — attractiveness and novelty first; low right-to-win is a flag, not a penalty. Sees L1–L4.',
      '**Sales** — right to win and proof-point density first. Only topics with a delivery path *and* a published reference in the vertical *and* no evidence gap.',
      '**Presales** — differentiation: where Orange has assets and the market has few credible providers. Sees L0–L2.',
      'The filters fall out of portfolio distance rather than being arbitrary presets.',
    ],
  },

  workflow: {
    title: 'The stage gate',
    ref: 'FR-25, §4.10 model A',
    body: [
      'A topic moves **Shortlisted → Demand-tested → Packaged → Live**, and ownership follows the stage: strategist, then sales, then presales.',
      'The known weakness of a stage gate is latency — a topic can die waiting for a stage owner. So time-in-stage is tracked and stalled cards are flagged rather than left for someone to notice.',
      'Every transition records who moved it and why.',
      'Cards are also marked when the team and the evidence disagree, which is a signal to look before advancing.',
    ],
  },

  assessment: {
    title: 'Assessing a topic',
    ref: '§4.10 model C, §4.7.4',
    body: [
      'You rate only the axis your role owns. Hover a level to see exactly what it means — the written anchors are what make a 0–5 scale mean the same thing to two different people.',
      'Confidence is separate from the rating, and weights how much your view moves the aggregate. "4, but I am guessing" should count for less than "4, certain".',
      'The free-text reason is optional and is the most useful text in the system — it is what a curator reads when the team and the evidence disagree.',
      'Changing your mind supersedes your earlier rating rather than adding a second one. The earlier view is kept, because a changed mind is itself informative.',
    ],
  },

  exploration_slot: {
    title: 'Exploration slot',
    ref: '§4.7.6',
    body: [
      'A small reserved slot showing topics the ranking did *not* put first, marked with a star.',
      'A ranking system that learns from its own users confirms itself: highly ranked topics get opened more, which reads as evidence they deserve to rank highly. Reserving a slot for less-exposed topics — and deliberately sampling watchlist topics into it — is the standard remedy.',
      'It respects your role\'s hard filters. It will not smuggle a topic with no proof point in front of a salesperson.',
    ],
  },

  heatmap: {
    title: 'Where the topics are',
    body: [
      'Vertical × domain occupancy. Darker means more topics in that cell.',
      'Outlined cells carry an evidence gap. **Empty cells are the interesting ones** — either the grid is genuinely unevidenced there, or the radar has not looked. That is the white-space map.',
      'Click a populated cell to filter the list to that vertical.',
      'The ramp is blue rather than orange on purpose: orange already encodes right-to-win elsewhere, and reusing it would imply the two charts show the same quantity.',
    ],
  },

  evidence_timeline: {
    title: 'Evidence over time',
    ref: '§4.6',
    body: [
      'Signals attached to this topic, by month of publication.',
      'Momentum is computed as the slope of exactly this series, so showing the shape lets you check the number rather than trust it.',
      'Dates are always publication dates, never ingestion dates — otherwise a backlog of old documents arriving today would look like a surge.',
    ],
  },

  weight_set: {
    title: 'Weight set',
    ref: 'SC-10, §4.6',
    body: [
      'The configuration version that produced every score on screen.',
      'Changing any weight requires a new weight-set id, because scores computed under different weights are not comparable. Trajectories are never plotted across a boundary without saying so.',
    ],
  },

  generation: {
    title: 'Generating opportunity spaces',
    ref: 'FR-06, §4.4, DR-03, §4.8',
    body: [
      'Runs the pipeline\'s **synthesis** stage on request instead of waiting for the scheduled refresh. It reasons over the theme clusters the pipeline has already built — it does not go and fetch anything. That is what makes *"the evidence does not support that many"* a real answer rather than a hang.',
      '**The count is spaces CREATED.** A candidate that lands on a vertical × use case × technology that already exists updates that space rather than making a second one (DR-03) — that is what keeps momentum measurable across refreshes — and an update does not count towards the number you asked for.',
      '**Vertical, domain and geography are enforced.** Every candidate is checked against them after the model replies, and anything outside is discarded rather than corrected. The prompt asks; the validator decides (§4.4.4).',
      '**Horizon is not, and cannot be.** §4.8 derives Now / Next / Later from the signal types attached to a space, after scoring — "derived rather than judged, because derived classifications are explainable and consistent". Selecting a horizon here picks clusters carrying that kind of evidence and tells the model what to look for. Where the new spaces actually landed is reported when the run finishes.',
      '**A cell that already exists is not a new space.** Canonical identity is the vertical × use case × technology triple (§4.4.5), so a candidate landing on an occupied cell updates that space rather than creating one — right on a refresh, and not what you asked for here. When a cluster produces only occupied cells, the run names them back to the model and asks again for something the evidence also supports. It does not count those toward your number, and it says how many there were.',
      '**A shortfall is explained, not hidden.** If you ask for eight and get three, the run says which gate the others failed — outside the requested scope, rejected by the critic, no claim that survived evidence binding, near-duplicates of one another.',
      '**Describing one** takes the same path with a different steer, and it is a conversation rather than a text box. Whatever you say is a *search brief, not evidence*: it is embedded, used to retrieve the closest corroborated signals already in the corpus, and then dropped from the factual role — every claim in the resulting space still has to cite those retrieved signals and survive the same critic and entailment checks. If nothing in the corpus is close enough, nothing is created. That is the answer, not a failure: a space built by restating your own sentence back to you with citations that do not support it is precisely what §4.4.4 exists to prevent.',
      '**The assistant reads the corpus while you talk.** Every turn re-retrieves from the whole conversation against the same signal vectors the run will read, at the same similarity floor, and what came back is shown beside the transcript with publisher, date and how close it actually was. That is what lets it ask about the geography the evidence is actually in rather than asking which geography, and what lets *"the radar carries nothing close to that"* arrive as a question now instead of as an empty run later.',
      '**It asks for the three things that ARE the space** — vertical, use case, technology (§4.4.5) — and then for the buyer\'s problem, the geography, the buyer and the shape of the deal, in that order, because that is the order in which they change what gets retrieved. It talks in your words and maps them onto the controlled vocabulary silently; anything it cannot map is dropped and named rather than carried through to fail validation at synthesis.',
      '**The Generate button is enabled by the corpus, not by the assistant.** Every brief it proposes is put back through the retrieval the job itself will perform. One that returns nothing above the floor is shown with that reason and cannot be selected — so a model that says it has enough, because that is what models say, still cannot enable a button that would produce nothing. When the two disagree the screen says so.',
      '**A conversation can produce more than one space.** If it genuinely lands on several distinct taxonomy triples, each becomes its own brief and its own synthesis pass inside a single run — one at a time, because synthesis holds the only write lock on that identity. The briefs are editable before they run, and the run re-checks whatever is actually submitted.',
      'New spaces arrive as `candidate` and go through enrichment, linking, scoring, next actions, sizing and the competitive read before the run reports done. A long-form description is not generated — open the space and ask for one.',
    ],
  },

  filters: {
    title: 'Filtering',
    ref: 'AC-04, FR-12',
    body: [
      'Multi-select on vertical, geography, domain, persona and horizon, plus free-text search across statements and claims.',
      'Selections within one dimension are a union; different dimensions combine as an intersection.',
      'A topic with no geography is treated as global rather than excluded.',
    ],
  },

  whitespace: {
    title: 'White space',
    ref: 'FR-32, §4.5.5',
    body: [
      'High attractiveness with no path from the current portfolio — the strategist\'s innovation agenda, expressed as a picture rather than a document.',
      'An empty list here is a real result, not a bug: it means the asset graph finds a plausible delivery path for everything currently on the radar.',
    ],
  },

  market_size: {
    title: 'Market size — the working, not the number',
    ref: '§4.3.4, Table 19',
    body: [
      '§4.3.4 warns that "the headline market-size figures circulating in press coverage almost always originate from paid research houses, are quoted without methodology, and frequently conflict by an order of magnitude". So nothing here is quoted. It is computed, and the computation is on screen.',
      '**Bottom-up** is the estimate the requirements ask for: enterprises in the vertical (Eurostat structural business statistics) × the share of them adopting this technology (Eurostat enterprise ICT survey) × the annual value of one engagement (median of matching EU tender notices, from TED).',
      '**Observed tenders** is a second, independent method: contracts that actually exist in the matching CPV categories, annualised. It is a floor rather than a market — it sees public buyers only — and for public-sector topics it is the better evidence, because Eurostat has no enterprise count for public administration.',
      '**TAM** is every enterprise that has adopted. **SAM** narrows to the size classes and geographies Orange serves — computed from the same data, not a fudge factor. **SOM** is the one modelled number: a planning assumption anchored on right to win and portfolio distance, labelled as such wherever it appears.',
      'Each factor is marked **observed**, **proxy** or **assumption**, and the confidence grade of the whole estimate is the worst of the three — never an average. An estimate is exactly as good as its weakest input.',
      'No figure in this section was produced by a language model. That rule (§4.4.4 defence 3) is enforced in the prompts and re-checked by a regex over everything generated.',
    ],
  },

  competition: {
    title: 'Competitive intensity',
    ref: '§4.3.3, Table 27',
    body: [
      'A **fourth** quantity, beside attractiveness, right to win and conviction — and kept as separate from them as they are from each other. A crowded field and a weak Orange position are different facts, and averaging them would hide both.',
      'The level is a band over a weighted count of named competitors: each contributes its category weight (a hyperscaler moves a market more than a regional reseller) times how specifically it matches this space, doubled where this topic\'s own sources actually name it.',
      '**evidenced** means the corpus mentions them here — the signal is dated, cited and clickable. **structural** means the curated register says they sell this technology into this vertical: true, and not proof they are in the deal.',
      'Companies that are both partner and competitor are marked as such rather than filed under one. Microsoft is a Gold partner and the default alternative in most AI deals; a salesperson needs both halves of that.',
      'The register is configuration with a named owner (`config/business_graph/competitors.yaml`), not model output. A model may write prose about this list; it may not add to it.',
    ],
  },

  description: {
    title: 'The detailed description',
    ref: 'FR-14, FR-18, §4.4.4',
    body: [
      'Written by the model from this topic\'s own evidence, its linked Orange assets and its named competitors — and from nothing else.',
      'The factual sections must cite signal ids attached to this topic. A section that cannot is **removed, not rewritten**, and what was removed is listed at the bottom rather than quietly omitted.',
      'A generated sentence containing a market size, percentage or monetary value is discarded on sight: the figures in this product come from the sizing engine, and a model sentence that contradicts them is worse than a missing one.',
      'Naming an organisation that was not supplied — a prospect, a partner, a competitor — also removes the section. Repeating an invented account name in a customer meeting is the failure mode this rule exists for.',
      'If the topic has changed since the text was written, the panel says so. A description of evidence the topic no longer rests on is worse than none.',
    ],
  },

  brief: {
    title: 'The opportunity brief',
    ref: 'FR-18',
    body: [
      'A PDF a salesperson or presales engineer can take into a meeting: the opportunity, the sized market with its working, the solution drawn as a diagram, the named Orange assets, the competitive field, qualifying questions, objections and the next action per role — with every source listed at the back.',
      'Three kinds of content meet on the page and are kept visibly distinct: **computed** (scores, sizes, intensity), **curated** (assets, references, competitors) and **written** (the narrative and the diagram). The last page records the weight set, sizing version, register version and the prompt and model that wrote the prose.',
      'The diagram is not drawn by the model. The model emits a structure — layers, boxes, who provides each one, what flows where — which the renderer draws to the same geometry every time. A box claiming to be an Orange asset that is not in the linked graph is demoted to third party, and the demotion is recorded.',
      'Regenerate after a refresh moves the topic: the brief carries the version it was built against, and says so when that is no longer current.',
    ],
  },

  presales: {
    title: 'Pre-sales collateral',
    ref: 'FR-18',
    body: [
      'The brief is one document for one conversation. This is the twelve pieces the team needs between that conversation and a proposal: a discovery and qualification pack, an outreach sequence, a first-meeting deck, a value hypothesis, a reference pack, competitor battlecards, a solution outline, a PoC scoping sheet, a partner brief, commercial model options, tender response blocks and a bid risk register.',
      'Every piece is built from **one snapshot** of this space, so nothing in the pack can quote a different figure for the same quantity. Each carries the versions that produced it — the weight set, the sizing version, the competitor register — on its last page, because six months later the only question anybody asks about a document found in a shared drive is which versions made it.',
      'The **format is your choice, per piece**. Documents can be PDF, Word or OpenDocument; decks can be PowerPoint, OpenDocument or PDF. The default is the format the artefact wants to be — a battlecard is a PDF because it is read on a phone and must not have been edited since it was approved; tender blocks are Word because they are paste-fodder for a response. Formats coexist: asking for Word after you have the PDF gives you both.',
      'In PowerPoint the diagrams are **native shapes**, not pictures — an architect can move a box rather than redraw the slide. In PDF they are exact vector geometry. Word and OpenDocument get the same diagram as a high-resolution image, because neither has a drawing model this system can target.',
      'Pieces that need a written narrative make one model call, and **look at the public record first** — the corpus is refreshed on a cadence and the document is being written today, and a regulator\'s deadline or a competitor\'s announcement lives in that gap. Anything drawn from a retrieved item must name its publisher inline, and every item the writer saw is listed at the back so a citation can be followed. Those items have not been through the radar\'s evidence validation, and the document says so.',
      'No figure in any of this is written by a model. Money comes from this space\'s own sizing; positions on the competitive map and bands on the risk matrix are ordinal judgements on a fixed scale, clamped on arrival and never printed as quantities.',
      'A piece whose inputs are missing still builds, with a banner naming the gap. An outline that says "built without the written description" is more use than an error message: it still carries the component map and the portfolio path.',
      'Staleness is tracked **per piece and per cause** — the space changed, the narrative was regenerated underneath it, or the sizing was recomputed. Those need different fixes, so the row says which happened rather than only that something did.',
    ],
  },

  coverage: {
    title: 'Coverage',
    ref: 'NFR-08',
    body: [
      'Language and geography coverage are monitored as a reported metric because anglophone and EU bias is a named risk, not an assumption to be waved away.',
      'If one source dominates the signal count, source diversity is thinner than the headline number suggests.',
    ],
  },
}
