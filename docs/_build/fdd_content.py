import sys; sys.path.insert(0, ".")
from docx_kit import *

import pathlib
HERE = pathlib.Path(__file__).resolve().parent.parent
D = str(HERE / "diagrams") + "/"
doc = Doc("Orange Business Innovation Radar — Functional Design Document", "")

doc.cover(
    "Functional Design Document",
    "Opportunity Spaces / Innovation Radar",
    "ORANGE BUSINESS  ·  INNOVATION RADAR",
    [("Document", "Functional Design Document (FDD)"),
     ("Version", "1.2"),
     ("Status", "For review"),
     ("Date", "24 August 2026"),
     ("Applies to", "Innovation Radar MVP · pipeline 0.1.0 · weight set w-2026-08-a · sizing size-2026-08-a · economics econ-2026-08-a"),
     ("Baseline", "Orange Innovation Radar — Requirements and Approach"),
     ("Companion", "Technical Architecture (TA), same date · docs/ reference set"),
     ("Audience", "Business sponsors, strategy, sales and presales leadership, product owners")],
    statement="An opportunity space is a Vertical × Use case × Technology with a human-readable statement. "
              "It carries two scores that are never combined — attractiveness and right to win — plus conviction "
              "and competitive intensity as separate quantities beside them, a market size computed bottom-up "
              "from published statistics, a description bound to its own evidence, a PDF brief a salesperson "
              "can take into a meeting and twelve further pieces of pre-sales collateral in the format each reader "
              "works in. A Planner turns the ranking into portfolio selection under a budget, and a five-year projection. Every claim is bound to a dated, attributable source, and every number "
              "decomposes into named components.")

doc.toc([
    (1, "1   Executive summary"),
    (1, "2   Purpose, scope and audience"),
    (2, "2.1  What the product is  ·  2.2  In scope  ·  2.3  Out of scope"),
    (1, "3   Business context and system context"),
    (1, "4   Functional capability map"),
    (1, "5   Core domain concepts"),
    (2, "5.1  The opportunity space  ·  5.2  The controlled vocabularies  ·  5.3  Signals and source tiers"),
    (1, "6   The four quantities"),
    (2, "6.1  Attractiveness  ·  6.2  Right to win  ·  6.3  Competitive intensity  ·  6.4  Conviction"),
    (1, "7   The portfolio join and the role modes"),
    (1, "8   Lifecycle, time horizon and refresh behaviour"),
    (1, "9   Competitor intelligence"),
    (2, "9.1  What a profile may do  ·  9.2  The differentiation angle  ·  9.3  Coverage  ·  9.4  Where it appears"),
    (1, "10  Evidence discipline and the generation controls"),
    (1, "10b Creating an opportunity space on demand"),
    (1, "11  Market sizing"),
    (1, "11b The Planner — from a ranked list to a portfolio"),
    (2, "11b.1 Two sources  ·  11b.2 What is projected  ·  11b.3 What it refuses to do"),
    (1, "12  Collaboration, ownership and team conviction"),
    (1, "12b Pre-sales collateral"),
    (1, "13  Users, journeys and screens"),
    (2, "13.5  Signing in  ·  13.6  Removing an opportunity space"),
    (1, "14  Conceptual data model"),
    (1, "15  Functional requirements catalogue"),
    (1, "16  Acceptance criteria"),
    (1, "17  Deliberate exclusions"),
    (1, "18  Open questions for Orange"),
    (1, "19  Glossary"),
])

# ============================================================ 1
doc.h1("1   Executive summary")
doc.p("Orange Business needs a repeatable way to answer two questions about any emerging commercial theme: "
      "**is the world moving**, and **can we play and win**. Trend feeds answer the first. They do not answer the "
      "second, and combining the two into a single ranked list destroys the information in both. The Innovation "
      "Radar exists to hold those two answers side by side, over a corpus of dated, attributable public evidence, "
      "and to hand each of three roles the version of that answer they can act on this week.")
doc.p("The unit of work is the **opportunity space**: one vertical, one use case, one technology, and a written "
      "statement short enough to be repeated in a meeting. Around it the system assembles evidence from 19 public "
      "sources, a join onto Orange's own offers, references, partners and certifications, a market size computed "
      "from published statistics by two independent methods, a named competitive field, and a six-page PDF brief.")
doc.p("Three design commitments run through every part of the functional specification, and every later section "
      "can be read as a consequence of one of them:")
doc.bullets([
    "**Evidence before generation.** The system never invents an opportunity space from a model's own knowledge. "
    "Every claim cites signal identifiers that are validated to exist in the evidence that produced the candidate; "
    "an uncited claim is removed, not rewritten.",
    "**Quantities are kept apart.** Attractiveness, right to win, competitive intensity and team conviction answer "
    "four different questions from four different kinds of evidence. No arithmetic crosses between them.",
    "**Every number decomposes.** A score that cannot be reconstructed by someone outside the project is not "
    "explained, only displayed. Every component is stored with the inputs that produced it, and the interface "
    "shows the working rather than hiding it behind a tooltip.",
])
doc.callout("Current state of the working system", [
    "418 opportunity spaces over a corpus of 11,354 signals from 34 enabled sources across 40 refreshes. "
    "7,267 of those signals are tier-1 — regulators, procurement portals, standards bodies and official statistics.",
    "4,832 typed links onto the Orange Business Graph over 181 catalogued assets. 314 bottom-up market-size "
    "computations, 181 competitive assessments, 174 long-form descriptions and 174 generated PDF briefs.",
    "1,745 pages read from 53 of 65 competitor websites, producing 53 structured competitor profiles and "
    "177 per-topic competitive analyses.",
    "56,385 Eurostat reference observations across five statistical series, held separately from the signal store.",
    "Seven stored portfolio plans, from both sources. The baseline parameter plan selects 51 spaces from 231 "
    "admissible ones under a stated budget; the workflow plan takes the two spaces the stage gate has moved to "
    "Demand-tested and schedules them without dropping either.",
    "Twelve pre-sales artefacts describable per space, in five output formats.",
    "Sign-in in front of every /api path, and a delete that states its impact before it is taken.",
], SH_GREEN, GREEN)

# ============================================================ 2
doc.h1("2   Purpose, scope and audience")
doc.h2("2.1  What the product is")
doc.p("The Innovation Radar is a decision-support product, not a reporting tool. It produces a ranked, filtered "
      "and explained set of opportunity spaces, refreshed on a cadence, that three roles use for three different "
      "decisions: where to invest study effort next quarter, what to open a customer conversation with, and how to "
      "differentiate a specific bid.")
doc.p("It is explicitly **not** a market-intelligence newsletter, a competitor-tracking database, or a replacement "
      "for the account team's own knowledge. Its distinguishing feature is the join between external evidence and "
      "Orange's own portfolio: without that join the product is a competent trend feed, and trend feeds already exist.")

doc.h2("2.2  In scope")
doc.table(
    ["Area", "What the MVP delivers"],
    [["Evidence acquisition", "Scheduled, parallel collection from 19 public sources across procurement, regulation, "
                              "research, news and official statistics. Licence position recorded per source; publication-date "
                              "gating so a past state can be reconstructed."],
     ["Sense-making", "Relevance gating, six-way signal-type classification, geography and language tagging, theme "
                      "clustering, multi-lens candidate synthesis, an adversarial critic pass, and continuous evidence enrichment."],
     ["Qualification", "Attractiveness and right to win as separate published scores; market size by two independent "
                       "methods; competitive intensity over a named list; time-horizon derivation; a lifecycle state machine."],
     ["Competitor intelligence", "Robots-aware crawling of competitor websites into structured profiles; a per-topic "
                                  "join between those profiles and the opportunity space; a written comparison per competitor "
                                  "including how Orange differentiates against each one; and competitor-seeded topic generation."],
     ["Portfolio join", "A curated Orange Business Graph, link generation and typing L0–L4 plus supporting evidence, "
                        "portfolio distance, curator confirmation of link patterns, white space and orphan-offer reporting."],
     ["Decision support", "Role-mode ranking and filtering, eight views including a polar radar, a score-explanation "
                          "surface on every number, long-form descriptions, PDF sales briefs, a stage-gate board and a divergence review queue."]],
    widths=[4.0, 12.6])

doc.h2("2.3  Out of scope for this release")
doc.p("The exclusions below are deliberate. Each is recorded with the reason, because an exclusion without a reason "
      "gets rediscovered as a gap.")
doc.table(
    ["Excluded", "Reason"],
    [["CRM integration", "Deferred by the requirements baseline. Public assets give a sufficient right-to-win proxy for the MVP."],
     ["Learned scoring models", "No labels exist on day one. The MVP ships the transparent baseline plus the capture-and-replay "
                                "harness that learned models will need."],
     ["Patent connector", "Requires EPO OPS registration or BigQuery credentials. Technology ownership currently uses a "
                          "portfolio-level prior from the technology vocabulary."],
     ["PowerPoint export", "The PDF brief is built instead; a slide variant is a packaging exercise, not a functional gap."],
     ["Backtest evaluation metrics", "The historical replay path exists; the forecasting-quality metrics that would consume it do not."],
     ["Authentication and authorisation", "The demonstration deployment is public and unauthenticated. This must be closed "
                                          "before any wider use — see the Technical Architecture, section 17."]],
    widths=[4.6, 12.0])

# ============================================================ 3
doc.h1("3   Business context and system context")
doc.p("Figure 1 shows what crosses the boundary of the system. Three things are worth reading off it directly.")
doc.bullets([
    "**Everything entering is dated and attributable.** A signal without a usable publication date is dated by "
    "inference or rejected outright, because every temporal computation in the product — momentum, recency, horizon, "
    "replay — depends on it.",
    "**Official statistics enter on a separate path.** Eurostat enterprise counts and adoption rates are denominators, "
    "not events. They carry no publisher diversity, no momentum and no relevance, so pushing 56,385 statistical cells "
    "through the signal store would corrupt every component that counts attached signals while adding nothing to discovery.",
    "**Human judgement flows back in, but only into ordering.** Curator link decisions, role assessments and stage moves "
    "change how a list is sorted and what a curator has confirmed. They never change a published score.",
])
doc.figure(D + "fdd-01-context.png", "Figure 1 — System context",
           "Sources, capabilities, users and outputs. The dashed return path is the only route by which internal judgement "
           "re-enters the system, and it terminates in the ranking function.")

# ============================================================ 4
doc.h1("4   Functional capability map")
doc.p("The product decomposes into six capability groups. The grouping is not organisational — it follows the "
      "dependency order of the data, and each group's output is the next group's only input. Read left to right, "
      "Figure 2 is also the order in which a single opportunity space comes into existence.")
doc.bullets([
    "**Evidence acquisition** turns a source catalogue into dated, deduplicated, tiered signals. Its hardest "
    "requirement is not collection but discipline: a licence position per source, gating on the publication date "
    "rather than the fetch date, and a retained raw archive so a past state can be rebuilt without re-fetching.",
    "**Sense-making** turns signals into candidate opportunity spaces. It is the only group in which a language "
    "model writes anything, and it is correspondingly the most heavily guarded — see section 9.",
    "**Qualification** attaches the numbers: two published scores, a market size by two methods, a competitive "
    "intensity band, a derived time horizon and a lifecycle state. Everything it produces is stored with the inputs "
    "that produced it.",
    "**Portfolio join** is where the product stops being a trend feed. It links each space onto Orange's own offers, "
    "references, partners and certifications, types each link by how far the space is from something deliverable, and "
    "records who confirmed it.",
    "**Competitor intelligence** reads what each competitor publishes about itself and turns it into a per-topic "
    "answer to the question a level cannot answer: what is this competitor doing here, and what do we say when "
    "the customer names them.",
    "**Decision support** turns all of the above into something a named role can act on this week: a ranked view they "
    "are allowed to see, a decomposition of every number in it, and a document they can take into a meeting.",
    "**Portfolio planning** answers the question a ranked list cannot: not which topic, but which SET — under a "
    "budget and a capacity, or over a set the stage gate has already committed to. See section 11b.",
    "**Collateral production** takes a qualified space through to the material a bid needs: twelve artefacts built "
    "from one snapshot of the space, each in the format its reader actually works in. See section 12b.",
])
doc.p("No capability group may reach past its neighbour. Qualification cannot re-open the evidence base; decision "
      "support cannot change what a number means. This is what makes each group independently testable, and it is why "
      "a stage of the pipeline can be re-run alone without invalidating the rest.")
doc.figure(D + "fdd-02-capability.png", "Figure 2 — Functional capability map",
           "All five groups are delivered in the MVP. The exclusions listed at the foot are the ones recorded in section 2.3.")

# ============================================================ 5
doc.h1("5   Core domain concepts")
doc.h2("5.1  The opportunity space")
doc.p("An opportunity space is the canonical unit of the product. It is defined by exactly three taxonomy values "
      "and carries one human-readable statement:")
doc.code("OS021   Manufacturing  ×  Industrial asset management  ×  Private 5G\n"
         "\n"
         "\"European discrete manufacturers are procuring private 5G to run asset tracking\n"
         " and condition monitoring on their own sites rather than over public networks.\"")
doc.p("Two rules govern that definition, and both matter more than they first appear.")
doc.bullets([
    "**A candidate must resolve to exactly one value in each of the three dimensions.** A candidate that resolves to "
    "two verticals is two candidates, or it is not specific enough to act on. Generic statements — \"AI\", \"cloud\", "
    "\"cybersecurity\", \"digital transformation\" — fail specificity validation on their own.",
    "**The triple is the identity.** Two candidates with the same vertical, use case and technology are the same topic. "
    "On refresh the existing topic is updated rather than recreated: new signals attach, the score is recomputed, and "
    "the previous score is retained. This is what makes momentum measurable, and it is the requirement most often "
    "missed in a first build.",
])
doc.p("The statement is bounded between 40 and 180 characters. Below the floor it is a slogan; above the ceiling it is "
      "a paragraph, and neither can be repeated back accurately in a meeting.")

doc.h2("5.2  The controlled vocabularies")
doc.p("Nothing in the system hard-codes a vertical, a weight or a threshold. All of it lives in configuration and is "
      "validated when the application starts, so a dangling identifier is a startup error rather than a runtime surprise "
      "— crosswalk errors otherwise propagate silently into every downstream number.")
doc.table(
    ["Vocabulary", "Size", "Role"],
    [["Verticals", "15", "The industry axis of the triple. Reconciled against the 12 customer-story industry labels."],
     ["Use cases", "59", "The business-problem axis. Each carries its domains and its exclusions."],
     ["Technologies", "38", "The enabling-technology axis, with a portfolio-level ownership prior per entry."],
     ["Business domains", "6", "The angular sector of the radar view, plus two cross-cutting domains."],
     ["Personas", "9", "Who inside the customer owns the problem; drives the sales filter."],
     ["Signal types", "6", "Trend · Regulation · Buying signal · Market move · Technology maturity · Proof signal."]],
    widths=[3.6, 1.6, 11.4])
doc.callout("These vocabularies are a Sprint 0 deliverable, not a finding",
            ["The 59 use cases and 38 technologies were drafted for the MVP. If an internal Orange catalogue exists it "
             "should replace them — the system is built to swap the vocabulary, not to defend this one."], SH_GOLD, RGBColor(0x8A,0x6D,0x1F))

doc.h2("5.3  Signals and source tiers")
doc.p("A signal is one dated, attributable item from one source: a tender notice, a legal instrument, a research "
      "output, a news item. Signals are stored by reference — the URL plus a short extract — never as a mirror of the "
      "publication. Each carries a **tier** that expresses how much weight its origin deserves.")
doc.table(
    ["Tier", "Label", "Weight", "What it covers"],
    [["1", "Authoritative", "1.00", "Legal instruments, regulator publications, official statistics, standards releases, "
                                    "procurement notices, peer-reviewed research"],
     ["2", "Independent reporting", "0.75", "Established trade and general press with editorial independence"],
     ["3", "Practitioner", "0.45", "Developer telemetry, community discussion, conference programmes, preprints"],
     ["4", "Interested party", "0.15", "Vendor press releases, sponsored content, marketing blogs"]],
    widths=[1.2, 3.6, 1.6, 10.2])
doc.p("Two rules make tiering do real work rather than decorate the interface. Tier-4 evidence is **capped** at 0.25 of "
      "the evidence-quality contribution rather than merely discounted, and the diversity measure discounts tier-4 "
      "publishers on the effective publisher count. That second detail is load-bearing: publisher entropy is "
      "scale-invariant, so a uniform tier-4 discount cancels out entirely and six vendor blogs score identically to "
      "six independent outlets. **No topic reaches high attractiveness on tier-4 evidence alone.**")

doc.h2("5.4  The evidence base in practice")
doc.p("Nineteen of twenty-five catalogued sources are wired. The remaining six are catalogued with the reason they "
      "are not, because the catalogue is the requirements record and not only runtime configuration. A representative "
      "single refresh returns:")
doc.table(
    ["Source", "Category", "Signals", "Note"],
    [["TED", "Procurement", "827", "Above-threshold EU tenders with CPV, country, buyer and value"],
     ["EC \"Have your say\"", "Regulation", "167", "Consultations with their feedback deadline — feeds horizon derivation"],
     ["OpenAlex", "Research", "142", "Carries an Orange-affiliation flag"],
     ["Google News (FR)", "News", "117", "French-language coverage"],
     ["BOAMP", "Procurement", "117", "French below-threshold tenders"],
     ["Google News (EN)", "News", "111", ""],
     ["EUR-Lex", "Regulation", "58", "Dated legal instruments, legislative stage inferred"],
     ["CORDIS", "Research", "48", "EU-funded projects — what Europe decided to fund"],
     ["ANSSI / CERT-FR", "Regulation", "36", "National regulator; also French-language"],
     ["GDELT", "News", "29", "Rate-limited to one request per 6 seconds"],
     ["Hacker News", "Practice", "22", "Practitioner attention, tier 3"],
     ["arXiv", "Research", "12", ""],
     ["NIST", "Regulation", "10", "Standards timelines, post-quantum"],
     ["**Total**", "", "**1,696**", "1,406 tier-1  ·  234 French-language"]],
    widths=[3.4, 2.6, 1.8, 8.8])
doc.p("Coverage is reported rather than assumed. A dedicated view shows language, geography and tier coverage across "
      "the corpus, so a thin area is visible as a gap in the evidence rather than appearing as an absence of opportunity.")

# ============================================================ 6
doc.h1("6   The four quantities")
doc.p("This is the single most consequential functional decision in the product. Four different questions are asked of "
      "every opportunity space, they are answered from four different kinds of evidence, and they are never combined.")
doc.figure(D + "fdd-03-quantities.png", "Figure 3 — Four quantities, never combined",
           "Each answers a different question with a different owner. In the interface the two published scores occupy "
           "two different visual channels — marker size and marker colour — and are never shown as one number.")

doc.h2("6.1  Attractiveness — is the world moving?")
doc.p("Computed from external evidence only. Five weighted components, all of them reproducible from stored inputs:")
doc.table(
    ["Component", "Weight", "What it measures", "How"],
    [["Market signal strength", "30%", "How visible this space is relative to everything else on the radar",
      "Count of relevance-gated signals in a trailing 90-day window, log-compressed, normalised against the distribution across all live topics"],
     ["Source diversity", "20%", "Whether many independent parties are talking, or one party repeatedly",
      "Shannon entropy over publishers, with tier-4 publishers discounted on the effective count"],
     ["Evidence quality", "20%", "How much the origins of the evidence deserve to be believed",
      "Tier-weighted mean, tier-4 contribution capped, with a floor penalty when no tier-1 or tier-2 evidence exists"],
     ["Novelty & momentum", "15%", "Whether attention is rising or fading",
      "Slope of signal volume over six trailing periods, fitted on publication dates"],
     ["Strategic relevance", "15%", "Whether this serves a stated Orange ambition",
      "A 0–5 rubric with written anchors per level, mapped onto 0–100"]],
    widths=[3.0, 1.3, 4.6, 7.7])
doc.p("Four of the five are arithmetic and never involve a model. Only strategic relevance is model-scored, and it is "
      "scored against a discrete rubric with worked anchors rather than a free 0–100 request — a free numeric ask "
      "compresses every answer into the middle of the scale.")

doc.h2("6.2  Right to win — can we play, can we win?")
doc.p("Computed as a structured lookup against the Orange Business Graph. **No language model touches this path**: "
      "matching a space against the asset catalogue is a join, not an inference.")
doc.table(
    ["Component", "Weight", "Evidence it reads"],
    [["Offer match", "25%", "Commercial offers that address the use case and technology"],
     ["Reference density", "20%", "Published customer references in the vertical"],
     ["Partner coverage", "15%", "Partners providing the technology, at a usable tier"],
     ["Compliance fit", "12%", "Certifications the vertical requires and Orange holds"],
     ["Capability depth", "12%", "Capability pools staffing the domain"],
     ["External validation", "8%", "Analyst positions in the relevant market"],
     ["Technology ownership", "8%", "Portfolio-level ownership prior for the technology"]],
    widths=[3.6, 1.6, 11.4])

doc.h2("6.3  Competitive intensity — how crowded is the field?")
doc.p("A band of NONE / LOW / MEDIUM / HIGH over a **named list** of competitors. The level and the names are never "
      "conflated: a level with no names is an opinion, and the names with their evidence are what a salesperson can "
      "use and a colleague can correct. Two kinds of presence are distinguished, because they are worth different "
      "things in a meeting:")
doc.bullets([
    "**evidenced** — this space's own sources name the competitor. The signal identifier, publisher and date travel "
    "with the claim and are clickable.",
    "**structural** — the curated register says they sell this technology into this vertical. True, useful, and not "
    "proof they are in the deal.",
])
doc.p("The level is a band over a weighted count: a category weight (a hyperscaler moves a market more than a regional "
      "reseller) multiplied by how specifically the competitor matches this space, doubled where the corpus actually "
      "names them. It is scored over the **listed** competitors — at most eight — rather than the whole 65-entry "
      "register, because summing a long tail of weak domain matches would rate every cybersecurity space identically.")
doc.callout("`relationship: both` is what makes the register honest",
            ["Microsoft is an Orange partner and the default alternative in most enterprise AI deals. Cisco is a Global "
             "Gold partner and sells managed SD-WAN directly. Recording both halves is more useful than pretending "
             "either one is not true — and typically five of the eight competitors listed against a security space are "
             "also Orange partners."], SH_BLUE, BLUE)

doc.p("The level and the named list are what the register can establish. What a competitor is **actually doing** "
      "in this space, and what Orange says when the customer names them, needs more than a register — see section 9.")

doc.h2("6.4  Conviction — do our own people believe it?")
doc.p("An aggregate of role assessments, described in full in section 11. It is a **third quantity**, and it enters the "
      "per-role ranking function only. It never appears as a published score, because internal data adjusts but does "
      "not replace external discovery, and because every published number must stay reproducible from evidence alone.")

# ============================================================ 7
doc.h1("7   The portfolio join and the role modes")
doc.p("Every opportunity space is linked to the Orange assets that bear on it, and each link is **typed** by how far "
      "the space sits from something Orange could actually deliver. The ordinal position of that type is the "
      "**portfolio distance** — the most decision-relevant number in the product, because it is the one that says "
      "what to do next rather than how interesting something is.")
doc.p("The requirements baseline asks two questions of every topic — can we play, and can we win — but leaves the "
      "mechanism open. This join is the mechanism, and it is the part of the product that cannot be bought. The "
      "external evidence in section 5 is public: any competitor could assemble it. What is not public is which of "
      "Orange's own offers already addresses a given use case, which partner supplies the missing piece at a usable "
      "tier, and which published reference in that vertical a salesperson can actually name in a meeting.")
doc.figure(D + "fdd-04-portfolio.png", "Figure 4 — Portfolio distance and the role modes",
           "The role modes are not interface presets. Each falls out of which link types that role can act on.")
doc.p("Link generation is a retrieval and rules problem, not a generation problem: the model may propose, but rules "
      "and humans dispose. Every link records the evidence that justified it, a confidence, and — for the first "
      "occurrence of each link pattern — the curator who confirmed or rejected it. Later occurrences of the same "
      "pattern inherit that decision, and both confirmations and rejections are retained as training data.")
doc.h2("7.1  Supporting evidence, and why it is typed separately")
doc.p("Every L0–L4 definition in the requirements baseline describes a **delivery** capability. A certification, an "
      "analyst position, a published reference and a capability pool are none of those — they are right-to-win "
      "evidence. Typing them L0 would mean any topic in a regulated vertical scored as a direct sell purely because "
      "Orange holds ISO 27001, which makes portfolio distance meaningless.")
doc.p("They are therefore typed **SUP**: linked, displayed and scored, but excluded from the distance computation and "
      "from the role-mode filter. This is a deliberate extension beyond the baseline and is worth confirming with the client.")
doc.h2("7.2  What each role sees, and why")
doc.table(
    ["Role", "Link types", "Ranking function", "Additional filter"],
    [["Strategist / Innovator", "L1–L4", "attractiveness 0.60 · momentum 0.30 · portfolio distance +0.10 "
      "(further from the portfolio ranks higher)", "none — this is the only role that may see white space"],
     ["Sales", "L0–L1", "right to win 0.45 · proof-point density 0.30 · attractiveness 0.25 · portfolio distance −0.30 "
      "(closer ranks higher)", "requires a published reference in the vertical and no evidence gap"],
     ["Presales / Proposal", "L0–L2", "differentiation 0.35 · right to win 0.35 · attractiveness 0.30 · portfolio "
      "distance −0.10", "none"]],
    widths=[3.2, 1.8, 7.2, 4.4])
doc.p("The sales filter is the interesting one. The requirement says sales should see \"only topics with enough "
      "internal content to credibly back up\", which sounds subjective. It has a computable definition: a delivery "
      "link at L0 or L1, **and** a published reference in the vertical, **and** no evidence gap. That definition is "
      "enforced in the read model and cannot be bypassed by re-sorting a list.")

# ============================================================ 8
doc.h1("8   Lifecycle, time horizon and refresh behaviour")
doc.p("A topic is not a document that is written once. It is a record that accretes evidence across refreshes, and "
      "its state is recomputed on every one of them from the evidence currently attached to it.")
doc.figure(D + "fdd-05-lifecycle.png", "Figure 5 — Opportunity space lifecycle",
           "Every transition records its reason. Faded states are retained rather than deleted, because a topic that goes "
           "quiet for two quarters and returns is itself a signal.")
doc.h2("8.1  Time horizon")
doc.p("Each space is placed in one of three horizons, and the horizon is **derived** rather than asserted. The "
      "derivation records which test produced it and which date anchored it, so a horizon can be argued with.")
doc.table(
    ["Horizon", "Window", "Typical anchor"],
    [["Now", "within 12 months", "A regulatory deadline, a consultation close date, a standards freeze already published"],
     ["Next", "12 to 36 months", "A phased application date, a funded programme's delivery window"],
     ["Later", "beyond 36 months", "Published Orange commitment dates — 2028 revenue commitments, 2030 Cyberdefense and "
                                   "emissions targets, 2040 Net Zero Carbon"]],
    widths=[2.4, 3.0, 11.2])
doc.h2("8.2  The promotion gate")
doc.p("A candidate becomes an active topic only when all four conditions hold simultaneously: at least four attached "
      "signals, at least three distinct publishers, evidence quality of at least 45, and at least one non-tier-4 "
      "source. A refresh period is 14 days. A topic with no qualifying signal for one period fades; after three it "
      "goes dormant, keeping its evidence, its links and its score history.")


# ============================================================ 9
doc.h1("9   Competitor intelligence")
doc.p("Competitive intensity says how crowded a space is. It does not say what those competitors are **doing** "
      "there, and it does not say what Orange replies when the customer names one of them. Those are the two "
      "questions a salesperson actually has, and neither is answerable from a curated register alone.")
doc.p("The register has a second weakness worth naming: it is a human's summary, written once, going stale from "
      "the day it is written. This capability adds the other half — what each competitor **says** it sells, taken "
      "from its own published pages, with the page that said it attached to every claim.")
doc.figure(D + "fdd-11-competitor.png", "Figure 11 — Competitor intelligence",
           "Four stages. The first three cost nothing per topic; only the fourth spends a model call.")

doc.h2("9.1  What a competitor profile is allowed to do")
doc.p("This is the constraint everything else follows from. A competitor's own website is **tier 4 — interested "
      "party** — exactly like a vendor press release: weight 0.15, contribution to evidence quality capped, and "
      "an acceptance criterion (SC-09) asserting that vendor-only evidence scores low.")
doc.p("So a profile may do exactly two things, and no more:")
doc.bullets([
    "**Explain** a competitor the register has already matched to a topic — what they publish about this vertical, "
    "this use case and this technology, cited to the page that said it.",
    "**Seed** generation. Where two or more profiled competitors sell into a taxonomy cell the radar has no topic "
    "for, that cell is promoted to the front of the synthesis target list and reasoned over through a "
    "competitor-movement lens.",
])
doc.p("It may not lift attractiveness, right to win, or any other published score. A candidate the competitor lens "
      "produces still has to bind to independent, non-vendor evidence to be accepted — so an unsupported one dies, "
      "which is the correct outcome and is what makes seeding here safe.")
doc.callout("Why not simply treat competitor pages as evidence?",
            ["Because it is vendor marketing, and the product's credibility rests on saying so. A subsystem that "
             "quietly exempted 1,745 vendor pages from the tier-4 rule would have hollowed out SC-09 while leaving "
             "its test passing — the most expensive kind of inconsistency, because nothing fails until a customer "
             "asks where a number came from."], SH_RED, RED)

doc.h2("9.2  The differentiation angle, per competitor")
doc.p("Each competitor on a space carries its own paragraph on how Orange differentiates **against that company, "
      "for that opportunity** — not a general Orange pitch. It is the part of the analysis a salesperson repeats "
      "verbatim, so it carries a guard beyond the four defences: it may only name Orange assets that are **linked "
      "to this topic** in the business graph.")
doc.p("Where nothing is linked, the honest paragraph says Orange would be competing on price and delivery rather "
      "than on a structural advantage. An invented advantage is not caught in review — it is caught in the meeting.")
doc.table(
    ["What makes one usable", "What gets it rejected"],
    [["Names the asymmetry — sovereignty and EU data residency against a hyperscaler; an owned network and field "
      "operations against a systems integrator; integration breadth against a point specialist",
      "Superlatives. \u201cBetter\u201d, \u201cleading\u201d and \u201cbest-in-class\u201d are not differentiators"],
     ["Anchored on a named offer, certification, partner tier or published reference — and the interface prints which",
      "Naming an Orange asset that is not linked to this topic"],
     ["Concedes what the competitor genuinely does better", "Any generated figure — market share, growth, headcount"],
     ["Says what to lead with and what to avoid arguing about", "Naming a customer beyond the supplied references"]],
    widths=[8.3, 8.3])

doc.h2("9.3  Coverage is reported, not assumed")
doc.p("Of 65 registered competitors, **53 are profiled** from 1,745 of their own pages. The other 12 are each "
      "recorded with a reason and named individually in the Coverage view, because a competitive field built from "
      "seven of eight competitors should say so rather than reading as complete.")
doc.table(
    ["Status", "Count", "Meaning"],
    [["blocked", "6", "The site refuses automated clients, or robots.txt disallows crawling"],
     ["unreadable", "3", "Fetched successfully but renders its content client-side, so nothing readable returned"],
     ["unreachable", "3", "TLS failure, timeout, or rate-limited past the circuit breaker"]],
    widths=[2.6, 1.4, 12.6])
doc.callout("A refusal is recorded, not worked around",
            ["Six competitor sites answer 403 to a declared automated client. A browser user agent gets through all "
             "of them; it is not used. The project already handles refusals this way — the source catalogue records "
             "Ofcom as unwired for exactly this reason — and applying a different standard to competitors because "
             "the data is more interesting would be the kind of quiet inconsistency the rest of the design exists "
             "to prevent.",
             "This is a decision with an owner rather than a technical limit. If Orange decides the trade is worth "
             "making it is a one-line change, but it should be a decision."], SH_GOLD, RGBColor(0x8A, 0x6D, 0x1F))

doc.h2("9.4  Where it appears")
doc.table(
    ["Surface", "What it shows"],
    [["Full-screen space \u2014 Competitors tab", "The structural join always; the written comparison once generated. "
      "The two are visually distinct throughout, on the same computed-versus-written principle the rest of the "
      "interface follows."],
     ["PDF brief", "A section per competitor: what they are doing here, how Orange differentiates against them, and "
      "what they do better. Briefs built before the section existed are flagged **incomplete** \u2014 distinct from "
      "stale \u2014 with a control to rebuild."],
     ["Coverage view", "Three progress bars \u2014 register read, spaces assessed, comparisons written \u2014 plus "
      "the unread competitors named individually."]],
    widths=[4.4, 12.2])

# ============================================================ 10
doc.h1("10   Evidence discipline and the generation controls")
doc.p("The requirements baseline is unusually direct about this: the failure mode that destroys trust in a product of "
      "this kind is a plausible, well-written, wrong statement in front of a customer. The functional answer is to "
      "over-produce deliberately and then filter hard, with a named reason for every gate and a record of what each "
      "gate removed.")
doc.figure(D + "fdd-07-funnel.png", "Figure 7 — From evidence to accepted opportunity space",
           "Measured on a live run. The four defences are listed in the order of effectiveness given in the requirements baseline.")
doc.h2("10.1  Prolonged brainstorming, made systematic")
doc.p("Three mechanisms turn open-ended ideation into something that terminates and can be measured:")
doc.bullets([
    "**Coverage-driven prompting.** The system computes which taxonomy cells have evidence but no candidate yet, and "
    "targets generation at exactly those. This converts brainstorming from \"produce more ideas\" into \"cover the "
    "evidenced grid\", which terminates and is measurable.",
    "**Diversity by construction.** Each evidence cluster is passed over three times at high temperature, and each "
    "pass is given a different **evidence lens** — regulatory, procurement, technology-maturity, cross-vertical. An "
    "open-ended loop elaborates around whatever it produced first, so the passes need different starting points to "
    "explore rather than paraphrase.",
    "**Adversarial critique.** A separate critic prompt scores 1–5 as the *minimum* across five tests, so one failure "
    "caps the whole score. On a live run it rejected 119 of 254 candidates, each with a specific written reason.",
])
doc.h2("10.2  Evidence enrichment")
doc.p("Synthesis only attaches a signal to a topic when the model happens to cite it. That leaves a gap: a topic "
      "created six weeks ago stays frozen at the evidence it was born with, even when a later refresh ingests signals "
      "that plainly belong to it. Thin evidence is not cosmetic — it suppresses a topic through the whole chain, "
      "because signal volume, publisher diversity, momentum and the promotion thresholds all count attached signals.")
doc.p("Enrichment closes that gap as **retrieval plus rules rather than generation**: embedding similarity **and** an "
      "independent taxonomy corroboration — a vocabulary term present in the signal text, or a procurement-code "
      "crosswalk hit. Similarity alone is refused, because embeddings happily rate two unrelated security items as "
      "close, and unchecked attachment would inflate exactly the components that depend on the count. Enrichment never "
      "writes a claim; only synthesis may do that, and only with citations.")


# ============================================================ 10b
doc.h1("10b   Creating an opportunity space on demand")
doc.p("Everything described so far arrives from a scheduled refresh. Two further routes exist for the case a refresh "
      "cannot serve — somebody has a specific question now, about a cell of the grid the corpus has not yet been asked "
      "about. Both end in the same synthesis run under the same four defences; they differ only in what the person "
      "asking has to already know.")
doc.figure(D + "fdd-14-generation-routes.png", "Figure 14 — Two routes into a new opportunity space, and the gate they share",
           "The corpus decides whether a run may happen. The model proposes what to run.")
doc.h2("10b.1  The parameters route")
doc.p("A strategist who knows the taxonomy picks a vertical, a use case, a technology and a horizon. Before anything "
      "is spent, the screen shows the opportunity spaces that **already** satisfy those criteria — because the most "
      "common outcome of an on-demand run is rediscovering something the last refresh produced, and finding that out "
      "afterwards costs four model calls and several minutes.")
doc.h2("10b.2  The scoping conversation")
doc.p("The route that replaced a text box. An opportunity space is a vertical × use case × technology plus a buyer's "
      "problem and a place, and somebody who knows their market but not this taxonomy under-specified at least two of "
      "those every time. The only feedback the box gave was a character count — which is the one failure that did not "
      "matter. The real failure arrived minutes later, from a run that created nothing.")
doc.p("So the assistant **interviews instead, with the corpus in front of it**. Every turn re-embeds the whole "
      "transcript against the same stored signal vectors the run itself will read, at the same floor, and shows what "
      "came back — publisher, date and cosine — beside the conversation. An answer that sharpens the idea therefore "
      "sharpens the evidence the next question is asked from, and the assistant can say \"the tenders here are "
      "German\" rather than \"which country?\". It is stateless: the transcript lives in the browser and arrives with "
      "every request, so a reload loses a conversation rather than leaking one.")
doc.h2("10b.3  Similarity is not support")
doc.p("Retrieval clearing the floor only means the corpus contains text that reads like the brief. A brief for "
      "municipal digital signage retrieves French public-sector IT tenders at the same 0.64 cosine a well-evidenced "
      "brief about turbine gearboxes scores, because they are about the same sector in the same country — and "
      "synthesis then produces candidates whose every claim the critic correctly rejects, because none of those "
      "tenders mentions signage.")
doc.p("A brief must therefore also be **corroborated**: a second, independent reason, on its use case or its "
      "technology. The vertical is excluded, because it corroborates every brief ever written about a well-covered "
      "sector. This is the rule the configuration already prescribes for evidence enrichment (section 10.2), reused "
      "rather than reinvented.")
doc.callout("The failure that made the gate judge sentences rather than labels", [
    "The taxonomy is a set of closed lists — 15 verticals, 59 use cases, 32 technologies — so a proposal is regularly "
    "filed under the nearest available cell rather than an exact one. A brief for advertising-funded municipal "
    "screens was filed under citizen service automation × private 5G, because nothing closer exists.",
    "Tenders for private-5G video surveillance corroborate the LABEL private 5G perfectly, and are no evidence "
    "whatsoever for advertising screens. The gate reported four supporting signals, the button enabled, the run spent "
    "four model calls, and the critic threw out every candidate with precisely that reason.",
    "So the cheap model is now asked, on every proposed brief, about the brief's OWN SENTENCE, with the labels shown "
    "as the approximation they are — and its answer overrules a label match. The vocabulary test stays for display, "
    "because \"the term 'private 5g' appears in the signal text\" is a more checkable thing to show a reader than a "
    "model's say-so, where the two agree.",
], SH_ORANGE, ORANGE_DARK)
doc.h2("10b.4  The corpus enables the button, not the assistant's mood")
doc.p("The assistant is told to put a brief forward even while hedging about the evidence, because otherwise a "
      "genuinely new idea has nothing to press Generate on. It duly writes \"the evidence is thin, marking this as "
      "not ready\" — a fair remark about the corpus and a poor reason to disable a button whose brief has already "
      "passed the same corroboration check the run applies.")
doc.p("So **`ready` is simply whether anything here can be run**, and the model's own opinion travels beside it as "
      "`model_ready`. The screen explains either disagreement rather than silently obeying one of them. Where a brief "
      "cannot be run, the refusal names the reason before the model calls are spent, and the contributed-evidence "
      "route (section 2.5 of the baseline — internal signals, moderated) opens instead, because that is the path that "
      "can actually build it.")

# ============================================================ 11
doc.h1("11   Market sizing")
doc.p("The requirements baseline issues a warning before it states a requirement: headline market-size figures in "
      "press coverage almost always originate from paid research houses, are quoted without methodology, and "
      "frequently conflict by an order of magnitude. Every size in this product is therefore **computed, never "
      "quoted**, by two independent methods published side by side.")
doc.figure(D + "fdd-08-sizing.png", "Figure 8 — Market size: computed, never quoted",
           "Two figures built from different data that land in the same order of magnitude are an argument. A figure "
           "with no method is not.")
doc.h2("11.1  Four decisions worth naming")
doc.bullets([
    "**The denominator and the adoption rate must share a size base.** Eurostat publishes enterprise ICT adoption for "
    "firms of 10 or more employees only. Multiplied by an all-sizes enterprise count — roughly 90% micro-firms — every "
    "estimate would have been out by an order of magnitude.",
    "**The contract value has to come from the right kind of contract.** A procurement-code crosswalk says what a "
    "notice is *about*; it does not say whether it is the kind of contract Orange would bid for. A €188m hydroelectric "
    "turbine retrofit, correctly crosswalked to industrial asset management, was setting the price of a zero-trust "
    "deployment until eligibility was tested on the notice's **main object** rather than any of its lots.",
    "**A public tender is a large-organisation contract.** Applied flat it prices a twelve-person manufacturer's "
    "project at a ministry's budget, so engagement value is scaled per size class, anchored on the class the observed "
    "contracts came from. The weights are an assumption with a named owner, and they are printed in the brief.",
    "**Proxies widen the range; they never move the base.** Where one series stands in for another the substitution is "
    "declared, the uncertainty band widens from ±15% to ±40%, and the confidence grade drops.",
])
doc.p("The confidence grade — `observed`, `partial`, `modelled` — is the **worst** basis among the factors, never an "
      "average, because an estimate is exactly as good as its weakest input. Where nothing attributable exists, no "
      "number is published: public administration has no enterprise count in Eurostat at all, so those spaces are "
      "sized from observed procurement only.")
doc.h2("11.2  What TAM, SAM and SOM mean here")
doc.table(
    ["Figure", "Definition used", "Status"],
    [["TAM", "Every adopter in the scoped geographies and industries", "Computed"],
     ["SAM", "The same estimate restricted to the size classes and geographies Orange serves — computed, not "
             "discounted by a fudge factor", "Computed"],
     ["SOM", "A share assumption anchored on right to win and portfolio distance", "The one genuinely modelled "
             "number, and labelled as such everywhere it appears"]],
    widths=[2.0, 10.0, 4.6])
doc.p("Reference data lives in its own tables. Five Eurostat series feed the bottom-up path — structural business "
      "statistics for enterprise counts, and enterprise surveys for cloud, AI, IoT and security practice — across 30 "
      "geographies and the last three published periods each. The AI series carries its own trajectory, which the "
      "interface shows as an adoption trend: machine learning in EU vehicle manufacturing went 3.2% (2023) → 4.8% "
      "(2024) → 7.8% (2025), which is a dated, attributable growth statement rather than a generated one.")


# ============================================================ 11b
doc.h1("11b   The Planner — from a ranked list to a portfolio")
doc.p("The radar ranks. A plan is a different object: given a budget, a capacity and a few preferences, which **set** "
      "of opportunity spaces should Orange enter, in what **order**, and what does that set earn. Three things make "
      "set selection different in kind from ranking, and all three are places where a ranked list gives the wrong "
      "answer:")
doc.bullets([
    "**Shared build.** Spaces needing the same capability pay for it once. Ranked independently each carries the full "
    "build and all of them look marginal; selected together the second is nearly free.",
    "**The flywheel.** Winning the first deal in a vertical raises right to win for every other space in it, so "
    "**sequence** is a decision variable rather than a presentation choice.",
    "**Concentration.** Ranking by market size alone puts 18 of the top 20 spaces in manufacturing. Diversification is "
    "a property of the set and is invisible per topic.",
])
doc.figure(D + "fdd-12-planner.png", "Figure 12 — The Planner: ranking answers which topic, a plan answers which set",
           "Two sources ask two different questions. Everything downstream of the set is the same arithmetic, and none of it is a model.")
doc.h2("11b.1  Two sources, and they are different questions")
doc.table(
    ["Source", "The question", "What the Planner is allowed to do"],
    [["**Parameters**", "What *should* we do, given a budget and a capacity? Nothing has been decided yet.",
      "Everything. The caller states constraints — budget in person-years, entry slots per year, a confidence floor, a "
      "portfolio-distance cap, concentration caps, a horizon mix — and the optimiser chooses the set that maximises "
      "the stated objective."],
     ["**Workflow selected**", "What does the business we have *already committed to* actually earn, and when?",
      "Almost nothing. Every space the stage gate has moved to Demand-tested or beyond is in. There is no evidence "
      "floor, no distance cap, no concentration limit and no objective, because there is nothing left to optimise. "
      "`selected_count` equals `considered_count`, and a test asserts it."]],
    widths=[2.6, 5.6, 8.4])
doc.p("That second mode is not a filtered version of the first. A space at Demand-tested has a salesperson's "
      "judgement behind it; dropping it for resting on a modelled size, or for sitting one level too far out on "
      "portfolio distance, answers a human decision with an assumption band. What is left to do is **scheduling** — "
      "horizon says when the market arrives, entry slots say how many spaces can start together — and arithmetic.")
doc.bullets([
    "**Horizon spreads the set across time.** A `now` space may start in year one, a `later` space not before year "
    "three, and a cohort larger than a year's entry slots cascades into the next year rather than pretending the "
    "capacity exists. Within a cohort the earlier slots go to the largest commitments, so an over-subscribed year "
    "defers the smallest rather than an arbitrary set.",
    "**A Live space starts in year one whatever its horizon says.** Horizon describes when the market arrives, which "
    "is a question already answered for something that is already selling. The stage pulls entry forward; it never "
    "pushes it back.",
    "**Over-commitment is the finding, not a reason to edit the portfolio.** Under the optimiser a capability pool "
    "cannot be over-committed — it would not have selected past one. Here the business already has, so nothing is "
    "dropped to make the numbers work: the pool that peaks above its available share is flagged with the size of the "
    "gap, and the plan names what closes it — hiring, partnering, raising the share available for new work, or moving "
    "a space back down the gate.",
    "**A committed space with no market size is declared rather than dropped.** It is in the plan as far as the "
    "business is concerned and absent from every figure on the page. Left silent it understates a portfolio the "
    "reader believes is complete, so it is listed by id, flagged, and the totals are described as a floor.",
])
doc.h2("11b.2  What is projected, and on whose assumptions")
doc.p("`config/economics.yaml` holds every assumption, versioned and owner-named on exactly the discipline "
      "`config/sizing.yaml` established, and printed on the last page of every plan it produces. Two figures are "
      "quoted from Orange's own filed accounts and marked as such; everything else is a planning band. **A plan built "
      "under one version of that file is not comparable with a plan built under another**, and the interface will not "
      "chart two such plans together silently.")
doc.table(
    ["Assumption", "What it does", "Why it is the one to argue about"],
    [["**Margin by portfolio distance**", "L0 14% · L1 11% · L2 7.9% · L3 3% · L4 0%",
      "The single most consequential number in the file. The filed 7.9% segment margin is FULLY LOADED — applying it "
      "flat to incremental revenue asserts that new business carries the same overhead as existing business, which is "
      "wrong in both directions. Varying it by distance moves five-year profit by about 1.66×, and revenue "
      "concentrates at L0, so the L0 band dominates the answer. One table from Orange finance is worth more here than "
      "any other single input."],
     ["**Ramp by horizon**", "Share of obtainable market reached in each year after a space's OWN entry year",
      "It is what makes staggered entry cost something. A space entering in year three is in the first year of its "
      "own ramp, not the third year of the plan's."],
     ["**Overlap discount**", "A second space in a vertical is discounted; a third sharing its use case more so",
      "SOM is not additive. Obtainable share is computed per topic against the same customers' same budgets, and the "
      "naive sum across all 418 spaces reaches 90% of Orange Business's entire segment revenue — which is not "
      "arguable for incremental business in a segment declining 5.8% a year."],
     ["**Discount rate**", "7.3% post-tax, from the filed accounts", "Quoted, not assumed. It is the Enterprise "
      "cash-generating unit's own rate, and the segment took a €332m goodwill impairment in the same year."]],
    widths=[3.0, 5.0, 8.6])
doc.h2("11b.3  What it refuses to do")
doc.p("**It is not a forecast, and it says so before the first figure.** Every projection carries its interval, the "
      "versions of every assumption behind it, and a plausibility check against Orange's own filed segment revenue. "
      "Where a plan's year-five revenue is an implausible share of that segment, the flag appears on the plan rather "
      "than in a footnote, and describes the number as a scenario ceiling.")
doc.p("**What is not in the plan says whose decision that was.** Under the parameter source the exclusion list names "
      "the constraint that bound — the confidence floor, the distance cap, a concentration limit. Under the workflow "
      "source it names a stage instead: still at Shortlisted, stopped on the board, or unsized. Nothing there was "
      "excluded by the Planner, and the document says so.")
doc.p("**The prose knows which question it is answering.** A narrative written for a committed set may not describe "
      "alternatives being weighed, because none were. The narrative is a model writing about the projection under the "
      "numeric guard — it may not introduce a figure that is not already in the plan — and the prompt splits on the "
      "source so that it cannot describe a selection that did not happen.")
doc.callout("Why an optimiser rather than a learned model", [
    "Selection under constraints is a multi-dimensional knapsack. It solves exactly, in under a second at this size, "
    "and it explains itself: which constraint bound, and what one more euro or one more engineer would buy. A learned "
    "recommender could do none of that, and NFR-01/NFR-03 require every number to decompose.",
    "There are also no labels. 418 spaces and zero historical outcomes is a spreadsheet, not a training set. The "
    "model's job in this subsystem is to WRITE the plan, not to choose it.",
    "Where the solver is unavailable or the program is infeasible, a greedy fill runs instead and NAMES each soft "
    "constraint it had to relax, rather than returning a set that quietly ignores one.",
], SH_BLUE, BLUE)

# ============================================================ 12
doc.h1("12   Collaboration, ownership and team conviction")
doc.p("Two collaboration models are implemented, chosen because they are the two that touch scoring.")
doc.figure(D + "fdd-06-workflow.png", "Figure 6 — Collaboration: the stage gate and team conviction",
           "Model A produces accountability. Model C produces judgement. Neither is allowed to enter a published score.")
doc.h2("12.1  Model A — the stage gate")
doc.p("A topic moves Shortlisted → Demand-tested → Packaged → Live, with ownership following the stage. The named "
      "weakness of a stage gate is latency — a topic can die waiting for a stage owner — so age-in-stage is computed "
      "and a card stalled for 30 days or more is flagged rather than left for someone to notice. Every transition "
      "records who moved it and why.")
doc.h2("12.2  Model C — distributed assessment")
doc.p("Each role rates **only its own axis**. That is the whole point: a salesperson is authoritative about whether "
      "customers are asking, and is not being asked to second-guess the evidence base.")
doc.table(
    ["Role", "Axis", "Why that role owns it"],
    [["Strategist", "Strategic fit", "Owns where investment goes"],
     ["Sales", "Customer demand", "Authoritative on whether customers are asking"],
     ["Presales", "Deliverability", "Knows what it would actually take to build"]],
    widths=[3.0, 3.6, 9.8])
doc.p("Ratings are 0–5 against **written anchors** per level, with a separate confidence, rather than a slider — people "
      "are unreliable at rating a topic 73 out of 100. Ratings are confidence-weighted, and a changed mind supersedes "
      "rather than duplicates: the earlier opinion is kept, because a changed mind is itself a label.")
doc.h2("12.3  Divergence is the product, not the noise")
doc.p("Where team conviction and the evidence-derived score disagree by more than 30 points, the topic enters a review "
      "queue with a written reading of what the gap might mean — either the radar is missing signal, or enthusiasm is "
      "running ahead of it. It is flagged, never averaged away. Disagreement becomes information rather than friction.")
doc.callout("The line conviction is not allowed to cross",
            ["Conviction enters the per-role **ranking** function at weight 0.25 and nothing else. It never touches "
             "attractiveness or right to win, so every published number stays reproducible from evidence alone.",
             "An unrated topic sits **neutral**, not last. Treating \"nobody has looked yet\" as \"everybody hates it\" "
             "would be a popularity bias, not a judgement."], SH_GREEN, GREEN)


# ============================================================ 12b
doc.h1("12b   Pre-sales collateral")
doc.p("The brief is one document for one conversation. This is the twelve pieces a team needs **between** that "
      "conversation and a proposal: a discovery and qualification pack, an outreach sequence, a first-meeting deck, a "
      "value hypothesis, a reference pack, competitor battlecards, a solution outline, a PoC scoping sheet, a partner "
      "brief, commercial model options, tender response blocks and a bid risk register.")
doc.figure(D + "fdd-13-presales.png", "Figure 13 — Pre-sales collateral: twelve pieces from one snapshot",
           "The catalogue is shown in full whether or not anything has been built: what COULD be produced is as much "
           "of the answer as what has been, and a screen that starts empty is one nobody presses a button on.")
doc.h2("12b.1  One snapshot, twelve documents")
doc.p("The space is read **once** and every renderer works from that reading. Two documents in the same pack quoting "
      "different SAM figures — one built before a sizing run and one after — is the failure this makes impossible "
      "rather than merely unlikely.")
doc.h2("12b.2  The format is the reader's choice, per piece")
doc.p("Documents emit as PDF, Word or OpenDocument; decks as PowerPoint, OpenDocument or PDF. The default is the "
      "format the artefact wants to be, and that default is an argument about the artefact rather than a preference:")
doc.table(
    ["Piece", "Default", "Because"],
    [["Competitor battlecards", "PDF", "It is read on a phone in a car park, and must not have been edited since it "
      "was approved."],
     ["Solution outline (HLD)", "PowerPoint", "The first thing a solution architect does with it is paste two slides "
      "into their own deck. Handing them a PDF makes them rebuild it."],
     ["Tender response blocks", "Word", "It is paste-fodder for a Word response. A PDF of paste-fodder is actively "
      "obstructive."],
     ["Outreach sequence", "Markdown", "Nobody has ever wanted a PDF of six emails."]],
    widths=[3.6, 2.4, 10.6])
doc.p("Formats **coexist**: asking for Word after you have the PDF gives you both, because that is obviously what was "
      "meant. A deck is never offered as Word — one idea per page is the only property that made it a deck. An "
      "unsupported format is refused with the alternatives named, never satisfied silently under the wrong extension.")
doc.h2("12b.3  Charts are vector where it matters")
doc.p("Eleven chart types are drawn with exact geometry: a TAM/SAM/SOM funnel, a value waterfall, a payback curve, a "
      "competitive field map, a risk matrix, a buying-centre map, a component ownership map, a portfolio path, a "
      "phase timeline, a scope boundary and coverage bars. In PowerPoint they are **native shapes**, so an architect "
      "moves a box rather than redrawing the slide; in PDF they are drawn geometry. Word and OpenDocument get the same "
      "picture rasterised at high resolution, because neither has a drawing model this code can target — and the trade "
      "is the right way round, since the format people send and the format people edit both get true vector output.")
doc.p("The palette was validated rather than chosen: each colour does exactly one job — identity, order, magnitude, "
      "polarity or state — and the ordinal and categorical sets were run through a contrast and colour-vision check. "
      "The brand rule holds: orange means Orange, or it means emphasis. It is never slot four of a competitor "
      "palette, which is why the field map names competitors instead of colouring them.")
doc.h2("12b.4  It looks at the public record before writing")
doc.p("The corpus is refreshed on a cadence; a battlecard is written the morning of a meeting. A regulator's deadline "
      "or a competitor's announcement lives in that gap. So a short, targeted research pass runs through the "
      "connectors the pipeline already trusts — same session, same throttling, same robots discipline, content held "
      "by reference only. Anything drawn from a retrieved item names its publisher inline, and every item the writer "
      "saw is listed at the back so a citation can be followed. Those items have **not** been through the radar's "
      "evidence validation, and each document says so.")
doc.callout("A piece whose inputs are missing still builds", [
    "The expensive inputs are prepared once for whichever pieces need them. Where an input is cheap and deterministic "
    "— a market size, a competitive assessment — it is generated; where it is not, the gap is reported.",
    "But nothing here refuses to produce a document. A pre-sales engineer who asked for a solution outline and got an "
    "error has nothing. One who got the outline with \"built without the written description\" across the top has the "
    "component map, the portfolio path, and a clear instruction about what to do next.",
    "Staleness is reported PER INPUT rather than per space. A pack whose battlecard was built against last month's "
    "competitor register and whose value case was built this morning is exactly the failure that tracking exists to "
    "make visible.",
], SH_ORANGE, ORANGE_DARK)

# ============================================================ 13
doc.h1("13   Users, journeys and screens")
doc.p("Eight views sit over one read model. The role changes what may be seen and how it is ordered; it never changes "
      "what a number means.")
doc.figure(D + "fdd-09-journeys.png", "Figure 9 — Screens and the three role journeys",
           "Deep links carry the whole view, so a prepared view can be sent to a colleague.")
doc.h2("13.1  What the radar view encodes")
doc.p("The polar radar uses four channels at once: **angular sector** is the business domain, **radial distance** is "
      "the time horizon with Now at the centre, **marker size** is attractiveness, and **marker colour** is right to "
      "win. Position carries identity, so no categorical hues are needed; colour encodes a magnitude, so it uses a "
      "single-hue sequential ramp validated for lightness monotonicity and contrast in both light and dark themes. "
      "Evidence-gap marks carry a glyph as well as a border, so the warning never depends on colour alone.")
doc.h2("13.2  Explaining a number, everywhere a number appears")
doc.p("Every topic carries a **How was this calculated?** surface showing the stored inputs and the arithmetic: the "
      "weight table, the weighted total, and per component the actual evidence — publisher entropy and the publishers "
      "counted, the tier distribution, the per-period buckets the momentum slope was fitted to, the rubric level and "
      "its rationale, the named offers and references behind right to win. It is reachable from the topic detail, from "
      "every list row and from the workflow board, and it deep-links. The same surface carries the reproducibility "
      "stamps — weight set, pipeline, prompt and model version — because a number you cannot re-derive is not "
      "explained, only displayed.")
doc.h2("13.3  Contextual help")
doc.p("Every dense concept in the interface has an explanation of what it is, why it works that way, and which "
      "requirement it comes from: portfolio distance, conviction, divergence, evidence gap, source tiers, horizons, "
      "the lifecycle, the exploration slot, weight sets. Content lives in one registry rather than scattered through "
      "components, so the explanation and the behaviour cannot drift apart.")
doc.h2("13.4  Accessibility")
doc.p("The interface was reviewed adversarially by seven independent reviewers working the three role tasks end to "
      "end, plus keyboard and contrast, information architecture, failure states, and copy. Eighty-two findings were "
      "raised and each was handed to a separate reviewer whose job was to refute it against the code. The confirmed "
      "findings are fixed. Contrast is measured rather than eyeballed: 10,056 rendered text elements across seven "
      "tabs and two themes clear WCAG AA. Topic rows are real buttons, so the detail pane is reachable from the "
      "primary browsing surface with a keyboard; generation waits are announced through a single polite live region "
      "with elapsed time; and below 1080px — which is what 200% browser zoom looks like to the layout — the detail "
      "pane is taken over by the middle pane rather than hidden.")

doc.h2("13.5  Signing in")
doc.p("Everything the product serves is internal: competitive analysis of named companies, Orange's own asset graph, "
      "market estimates with the workings attached, and the stage-gate opinions of people who work here. None of it "
      "should be readable by whoever finds the URL. Every path except the sign-in endpoints themselves now requires a "
      "session, and the interface shows who is signed in and offers a password change from every screen.")
doc.p("An empty database seeds one account, `orange` / `orange`, flagged **must change password**. That flag is not "
      "decoration: a warning appears on every screen while it is set, because a default credential nobody is reminded "
      "about is a permanent one. Accounts are managed from the command line rather than from the running application, "
      "so a hijacked session cannot mint itself a permanent login.")
doc.h2("13.6  Removing an opportunity space")
doc.p("A synthesis result that is wrong could previously only be retracted by editing the database by hand. A space "
      "can now be deleted from its detail pane — but the interesting part is not the delete, which the foreign keys "
      "already cascaded. It is what the person is told **first**: the dialog asks the server for the impact and reads "
      "it out before showing the button, and the result names again what went.")
doc.bullets([
    "**The evidence survives.** Only the attachment rows go. A signal is evidence about the world that several spaces "
    "may cite; deleting a synthesis result must not delete the reading it was synthesised from.",
    "**Duplicates folded into this space go with it.** A merged record is a tombstone saying \"this triple is the same "
    "topic as that one\". If the survivor is removed, clearing the pointer instead would resurrect duplicates against "
    "the identity rule in section 5.1.",
    "**Plans are named, not blocked.** A plan that selected this space keeps its stored projection, which was "
    "computed once and is immutable by design. Refusing the delete would make any space that ever appeared in a plan "
    "permanent; silently breaking the plan would be worse. So the impact names the plans, and so does the result.",
])
doc.callout("Deletion is not suppression", [
    "Identity is the vertical × use case × technology triple. A later refresh that meets the same triple in the "
    "evidence will synthesise the space again — with a new id, and with none of the history removed here.",
    "Removing a space is a statement about the corpus as it stands, not a permanent veto. Anything that needs to be "
    "permanent belongs in the taxonomy or the source catalogue, not in a delete.",
], SH_ORANGE, ORANGE_DARK)

# ============================================================ 14
doc.h1("14   Conceptual data model")
doc.p("Figure 10 is the business-level view of what the system stores and how the objects relate. The physical schema, "
      "with columns, keys, indexes and constraints, is in the Technical Architecture, sections 11.2 to 11.5.")
doc.figure(D + "fdd-10-domain.png", "Figure 10 — Conceptual data model",
           "Read the two identity rules first: they explain most of the behaviour described in sections 5 and 8. "
           "The competitor objects added in section 9 are shown in the Technical Architecture, Figure 12.")
doc.h2("14.1  The objects, in one line each")
doc.table(
    ["Object", "What it is", "Identified by"],
    [["Signal", "One dated, attributable item from one source, stored by reference with a short extract", "Its URL"],
     ["Theme cluster", "A grouping of signals recomputed each refresh; the seed for synthesis", "A refresh-scoped id"],
     ["Opportunity space", "The canonical unit: vertical × use case × technology plus a written statement",
      "The taxonomy triple"],
     ["Score", "One published score of one kind, with its components and the inputs that produced them",
      "Topic + kind + computation time"],
     ["Market size", "TAM/SAM/SOM with low, base and high, by one of two methods, with every factor and its source",
      "Topic + method + computation time"],
     ["Competition", "A level over a named list of competitors, each with its basis and its evidence", "Topic"],
     ["Business asset", "An offer, reference, partner, certification, analyst position, capability pool or research asset",
      "Its catalogue id"],
     ["Link", "A typed, dated, evidenced join from a space to a business asset", "Topic + asset"],
     ["Description", "Long-form narrative, each section carrying the signal ids it was written from", "Topic"],
     ["Brief", "The rendered PDF, stamped with the versions of everything it printed", "Topic"],
     ["Assessment", "One role's rating of its own axis, with confidence and rationale", "Topic + role + author"],
     ["Workflow state", "The topic's current stage and owner, plus its full transition history", "Topic"],
     ["Reference series", "Eurostat observations by indicator, industry, geography, size class and period",
      "Series + full coordinate"],
     ["Competitor page", "One page published by a competitor, stored by reference plus a bounded extract",
      "Competitor + URL"],
     ["Competitor profile", "What a competitor says it sells, each claim carrying the page that said it — or a "
      "recorded reason why there is no profile", "Competitor"],
     ["Competitor analysis", "Per topic: the join onto competitor profiles, plus the written comparison and the "
      "differentiation angle per competitor", "Topic"],
     ["Plan", "One portfolio plan: the stated inputs, the selected set with entry years, the projection, the flags "
      "and the narrative", "A fingerprint of the inputs and the assumption versions — so a plan is immutable"],
     ["Plan selection", "One selected space within one plan: its entry year, margin band, overlap discount and "
      "capability pool", "Plan + topic"],
     ["Collateral", "One built pre-sales piece, recorded with the versions of everything it printed",
      "Topic + kind + format"],
     ["User", "Who may sign in. A username and a verifier — never a password", "Username"],
     ["Session", "One live sign-in, stored only as the hash of its cookie value", "The hash"]],
    widths=[3.0, 9.4, 4.2])

# ============================================================ 14
doc.h1("15   Functional requirements catalogue")
doc.p("The table below maps the requirements baseline onto what is delivered. Identifiers follow the baseline document.")
doc.table(
    ["ID", "Requirement", "Status", "Where it lives"],
    [["FR-03", "Classify every signal into one of six signal types", "Delivered", "Classification stage; shown in topic detail"],
     ["FR-06", "Specificity validation on candidate statements", "Delivered", "Closed-vocabulary and statement-length gates"],
     ["FR-08", "Derive a time horizon per topic", "Delivered", "Horizon derivation with a recorded basis and anchor"],
     ["FR-09", "Lifecycle states with defined transitions", "Delivered", "Lifecycle state machine, section 8"],
     ["FR-13", "Role-ranked topic list", "Delivered", "Role modes, section 7.2"],
     ["FR-14", "Long-form description with cited claims", "Delivered", "Description generation under all four defences"],
     ["FR-17", "A next action per role, per topic", "Delivered", "Actions stage; shown in the detail pane"],
     ["FR-18", "Exportable sales/presales brief", "Delivered", "Six-page PDF brief with solution diagram"],
     ["FR-19", "Show last refresh date per topic and globally", "Delivered", "Refresh log, surfaced in the interface"],
     ["FR-21", "Serve a bounded, ranked view", "Delivered", "Capped at 24 topics per view with an order control"],
     ["FR-23", "Capture feedback with its exposure context", "Delivered", "Feedback capture including rank and filters"],
     ["FR-24", "Internal signal injection", "Delivered", "Moderated internal signals become first-class signals"],
     ["FR-25", "Collaboration workflow", "Delivered", "Stage gate and distributed assessment, section 11"],
     ["FR-30", "Portfolio distance from typed links", "Delivered", "Link typing L0–L4 plus SUP, section 7"],
     ["FR-31", "Role modes derived from portfolio distance", "Delivered", "Section 7.2"],
     ["FR-32", "White space register", "Delivered", "High attractiveness with no portfolio path"],
     ["FR-33", "Orphan offers — portfolio decay", "Delivered", "Offers with no live topic"],
     ["FR-34", "Engagement weighting by exposure", "Delivered", "Exposure context stored with every feedback event"],
     ["FR-35", "Historical replay with leakage control", "Delivered", "Publication-date gating plus a retained raw archive"],
     ["§4.3.3+", "Competitor profiling from published material", "Delivered", "Robots-aware crawl, 53 of 65 profiled, gaps named"],
     ["§4.3.3+", "Per-topic competitor analysis", "Delivered", "Structural join always; written comparison on demand"],
     ["§4.3.3+", "Differentiation angle per competitor", "Delivered", "Anchored on linked Orange assets only"],
     ["§4.4.3+", "Competitor-seeded candidate generation", "Delivered", "Fifth evidence lens plus cell targeting"]],
    widths=[1.4, 6.0, 2.0, 7.2], size=8.5)

# ============================================================ 15
doc.h1("16   Acceptance criteria")
doc.table(
    ["ID", "Criterion", "How it is verified"],
    [["SC-01", "Attractiveness is computed from five named components with published weights",
      "Automated test on component decomposition and weighted total"],
     ["SC-03", "Syndication collapses and tier-4 evidence is discounted, not merely labelled",
      "Automated test: six vendor blogs must not score as six independent outlets"],
     ["SC-09", "Vendor-only evidence scores low", "Automated test on an all-tier-4 corpus"],
     ["SC-10", "Every published score records the weight set that produced it",
      "Schema constraint plus an interface guard against plotting across a weight-set boundary"],
     ["SC-11", "Scores are reproducible from stored inputs", "Automated reproducibility test; deterministic clustering "
                                                             "and deterministic JSON serialisation"],
     ["SC-12", "The two scores are never collapsed into one number",
      "Two separate fields end to end, and two separate visual channels in the interface"],
     ["SC-13", "A topic with an evidence gap is marked as such", "Automated test; the mark carries a glyph as well as colour"],
     ["SC-14", "Internal data adjusts but does not replace external discovery",
      "Conviction enters ranking only; automated test asserts published scores are unchanged by assessments"],
     ["SC-15", "Right to win is a structured lookup, never asserted by a model", "No model call exists on that path"],
     ["AC-05", "A view is bounded", "Capped at 24 topics, with an order control that re-orders within what the role may see"],
     ["NFR-01", "Every displayed number decomposes into named components", "The score-explanation surface, on every number"],
     ["NFR-02", "The business graph is auditable to the same standard as the evidence", "Source and as-of date on every node and edge"],
     ["NFR-03", "A reviewer outside the project can reconstruct any rank", "Stored inputs per component, plus the reproducibility stamps"],
     ["NFR-05", "A sovereign deployment option is kept open", "Provider abstraction with a local model implementation; "
                                                              "no browser dependency in PDF rendering"],
     ["NFR-08", "Coverage is reported", "Language, geography and tier coverage view"],
     ["NFR-11", "Weights and thresholds are configuration, not code", "All of them in configuration, validated at startup"]],
    widths=[1.6, 6.8, 8.2], size=8.5)

# ============================================================ 16
doc.h1("17   Deliberate exclusions")
doc.p("Repeated from section 2.3 with the additional exclusions this build did not reach, so that the two lists are "
      "not maintained separately: CRM integration, learned scoring models, learned per-role ranking, a patent "
      "connector, PowerPoint export, and the backtest evaluation metrics. In every case the reason is recorded, and "
      "in most the enabling work is already present — the replay harness, the feedback-capture schema and the "
      "provider abstraction all exist and are unused by the excluded feature rather than absent.")
doc.p("One exclusion is new with the competitor capability. **Headless-browser rendering is not built**, so three "
      "competitor sites that render their content client-side return nothing readable. Adding it would put a browser "
      "into a pipeline that deliberately has none — the same dependency the PDF renderer was chosen to avoid — for "
      "three profiles out of sixty-five. It is recorded as a gap rather than closed.")

# ============================================================ 17
doc.h1("18   Open questions for Orange")
doc.p("The requirements baseline lists thirteen. Six affect the functional specification as written, and each has a "
      "consequence that is worth stating rather than leaving to discovery.")
doc.table(
    ["Question", "Why it matters now"],
    [["What is the refresh cadence?", "Drives connector design and cost more than any other decision. Currently a "
                                      "14-day period, which is also the unit the lifecycle counts in."],
     ["May an external model API be used during the MVP?", "The provider abstraction supports a local model today. "
                                                           "The question is whether the sovereign path must be exercised now."],
     ["Do internal taxonomies exist?", "The 59 use cases and 38 technologies are a drafted Sprint 0 deliverable. An "
                                       "internal catalogue should replace them."],
     ["Who is the curator?", "173 links are currently unconfirmed. The first occurrence of each link pattern requires "
                             "a named human, and without one, quality drifts. The same question now applies twice over: "
                             "the sizing assumptions and the 65-entry competitor register both carry a placeholder owner, "
                             "and both appear in front of customers."],
     ["Is the four-year contract assumption right?", "Tender notices publish a contract's whole value, and annualising "
                                                     "it needs a duration. Four years is the figure used and printed; every "
                                                     "size in the radar moves inversely with it."],
     ["How wide is the private-sector proxy?", "Contract values are observed from public procurement because that is the "
                                               "only attributable source available. Where Orange has its own won-deal "
                                               "distribution, substituting it would move these estimates off a proxy and "
                                               "onto evidence."],
     ["Is the SUP link type accepted?", "Typing supporting evidence separately from delivery links is an extension beyond "
                                        "the baseline. It is the difference between portfolio distance meaning something "
                                        "and meaning nothing in regulated verticals."],
     ["May a browser user agent be used for competitor profiling?", "Six competitor sites — including Cisco and "
      "Fortinet — refuse a declared automated client. A browser agent gets through all of them. Not doing so is a "
      "deliberate consistency with how the source catalogue treats Ofcom, and it costs twelve profiles that thin the "
      "competitive picture on security spaces. This should be Orange's decision, not the build's."]],
    widths=[5.4, 11.2])

# ============================================================ 18
doc.h1("19   Glossary")
doc.table(
    ["Term", "Meaning"],
    [["Attractiveness", "Published 0–100 score answering \"is the world moving\", from external evidence only"],
     ["Conviction", "Confidence-weighted aggregate of role assessments. Enters ranking only; never published as a score"],
     ["Competitive intensity", "A NONE/LOW/MEDIUM/HIGH band over a named list of competitors, each with its basis"],
     ["Evidence gap", "A topic whose evidence is too thin, too concentrated or too low-tier to support the number shown"],
     ["Evidence lens", "The angle a synthesis pass is asked to take — regulatory, procurement, technology-maturity, cross-vertical"],
     ["Exploration slot", "A small randomised allocation in a ranked view, so the feedback loop cannot only ever see what it already ranks highly"],
     ["Opportunity space", "Vertical × Use case × Technology plus a written statement. The canonical unit of the product"],
     ["Orange Business Graph", "The curated graph of offers, references, partners, certifications, analyst positions and capability pools"],
     ["Portfolio distance", "The ordinal position of the shortest delivery link from a space to the portfolio; 0 for a direct offer, 4 for white space"],
     ["Right to win", "Published 0–100 score answering \"can we play, can we win\", from the business graph only"],
     ["Signal", "One dated, attributable item from one source, stored by reference plus a short extract"],
     ["Source tier", "1 to 4, expressing how much an item's origin deserves to be believed"],
     ["SUP", "A supporting-evidence link — scored and displayed, but excluded from portfolio distance"],
     ["Weight set", "The identifier of the calibration a score was computed under. Scores across a boundary are not comparable"],
     ["White space", "High attractiveness with no plausible delivery path from the current portfolio"]],
    widths=[3.6, 13.0], size=9)

doc.save(str(HERE / "Orange_Innovation_Radar_Functional_Design_Document.docx"))
