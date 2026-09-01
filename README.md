# Orange Business — Opportunity Spaces / Innovation Radar

An evidence-first innovation radar that discovers specific business
opportunities, explains why they matter, connects them to Orange Business
capabilities, and turns them into actionable sales and portfolio material.

MVP implementation of the requirements baseline in
[`Orange_Innovation_Radar_Requirements_and_Approach.docx`](docs/Orange_Innovation_Radar_Requirements_and_Approach.docx).

## What an opportunity space is

An opportunity space is **Vertical × Use Case × Technology** with a
human-readable statement. Each one carries two scores that are never combined:

- **Attractiveness** — is the external market moving?
- **Right to Win** — can Orange play and win?

Beside them, and never folded into either, sit two further quantities:

- **Conviction** — do internal teams believe in it?
- **Competitive intensity** — how crowded is the field?

The system keeps these questions separate, stores the evidence and inputs behind
every result, and exposes the calculation rather than asking users to trust an
opaque score.

Each space also carries a **market size** computed bottom-up from published
statistics, a written description bound to its own evidence, a **competitor
analysis** saying what each named competitor is doing there and how Orange
differentiates against each of them, and a **PDF brief** a salesperson can take
into a meeting. Every claim is bound to a dated, attributable source, and every
number decomposes into named components.

## What it does

1. Collects dated, attributable evidence from regulation, procurement, research,
   standards, news, and other configured sources.
2. Uses multilingual embeddings to cluster related evidence.
3. Uses guarded AI generation to propose evidence-backed opportunity spaces.
4. Calculates explainable Attractiveness and Right-to-Win scores.
5. Connects opportunities to Orange offers, references, partners,
   certifications, and capabilities.
6. Produces market sizing, competitor analysis, briefs, pre-sales collateral,
   workflow views, and constrained portfolio plans.

## The pre-sales pack

Beyond the brief, each space carries **twelve pieces of pre-sales collateral**
for the work between the first meeting and a proposal — qualification, a
solution outline, battlecards, a business case, a PoC scope, tender blocks, a
risk register and more — each with its own diagrams, and each available as PDF,
Word or OpenDocument (decks as PowerPoint, OpenDocument or PDF). All twelve are
built from one snapshot of the space, so nothing in the pack can disagree with
anything else in it.

## Why it is different

- Generated claims must cite evidence the pipeline actually retrieved.
- Unsupported claims are removed rather than rewritten to sound plausible.
- Scores retain their components, raw inputs, weight set, and model/pipeline
  versions.
- Market sizing shows its factors, sources, assumptions, confidence, and range.
- The same evidence can be followed from discovery to a customer-facing
  deliverable.

## Quick start

```bash
# Install Python dependencies
pip install -r requirements.txt

# Configure the model provider
cp .env.example .env

# Validate configuration
PYTHONPATH=src python3 -m radar.cli check

# Run the pipeline
PYTHONPATH=src python3 -m radar.cli refresh --since-days 60

# Start the API
PYTHONPATH=src python3 -m radar.cli serve

# In another terminal, start the frontend
npm --prefix frontend install
npm --prefix frontend run dev
```

The application is available at <http://127.0.0.1:5173>. On a new empty
database, the initial development account is `orange` / `orange`; change this
password immediately.

Running the pipeline stage by stage, managing accounts from the command line,
and the full CLI command reference are in the
[getting started and architecture guide](docs/GETTING_STARTED_AND_ARCHITECTURE.md).

## Documentation

Start with the [documentation index](docs/DOCUMENTATION.md), or open the topic
you need directly:

| Document | Use it for |
|---|---|
| [Interview guide](docs/INTERVIEW_GUIDE.md) | Six presentation questions covering uniqueness, limitations, AI, trust, scoring, and tools |
| [Getting started and architecture](docs/GETTING_STARTED_AND_ARCHITECTURE.md) | Setup, CLI workflow, pipeline stages, repository layout, and configuration |
| [Implementation guide](docs/IMPLEMENTATION_GUIDE.md) | Evidence controls, role modes, workflow, outputs, Planner, UI, and performance |
| [Build status and data sources](docs/DATA_SOURCES_AND_STATUS.md) | Current implementation status, source coverage, and sampling lessons |
| [Frontend and deployment](docs/FRONTEND_AND_DEPLOYMENT.md) | Frontend design, Azure deployment, access control, and production readiness |
| [Quality, limitations, and security](docs/QUALITY_LIMITATIONS_AND_SECURITY.md) | Tests, deliberately unbuilt features, open decisions, and security notes |
| [Scoring formulas](docs/SCORING_FORMULAS.md) | Exact hand-calculation formulas for Attractiveness, Right to Win, Conviction, and role ranking |
| [Market sizing](docs/MARKET_SIZING.md) | TAM/SAM/SOM methods, factors, confidence, assumptions, and examples |
| [Competitor intelligence](docs/COMPETITOR_INTELLIGENCE.md) | Competitor profiles, evidence binding, and differentiation rules |
| [API reference](docs/API.md) | Available HTTP endpoints |
| [Data model](docs/DATA_MODEL.md) | Tables, relationships, and stored provenance |
| [Operations guide](docs/OPERATIONS.md) | Running, refreshing, troubleshooting, and rebuilding documentation |
| [Architecture decisions](docs/DECISIONS.md) | Important technical and product trade-offs |
| [Changelog](docs/CHANGELOG.md) | Features, fixes, and instructive defects |
| [Project timeline](docs/TIMELINES.md) | Retrospective project plan, session log, and working patterns from the commit history |
| [Final presentation](<docs/Orange_Innovation_Radar (final slides with speaker notes).pptx>) | Final project slides with speaker notes |

The full Functional Design Document, Technical Architecture, requirements
baseline, presentations, and demonstrations are listed in the documentation
index.

Section references used throughout that documentation (§4.5.3, SC-13, FR-30 …)
point at the requirements document. They are also carried in the code as
comments, so any given behaviour can be traced back to the requirement that
asked for it.

## Team and contributions

- **Stephane — Team Leader / Technical Architect** ([LinkedIn](https://www.linkedin.com/in/stepvda/))
- **Uzair — Business Analyst** ([LinkedIn](https://www.linkedin.com/in/uzairsaeedkhan/))
- **Lien — Documentation Specialist** ([LinkedIn](https://www.linkedin.com/in/lienkt0110/))

## Repository layout

```text
config/          taxonomies, sources, weights, thresholds, business graph
src/radar/       ingestion, synthesis, scoring, graph, sizing, API, planning
frontend/        React + TypeScript application
tests/           automated unit and integration tests
docs/            detailed documentation and generated deliverables
```

## Tests

```bash
python3 -m pytest tests/ -q
npm --prefix frontend run build
```

The tests cover evidence binding, scoring reproducibility, source-quality rules,
market sizing, graph linking, workflow, authentication, deletion, generated
documents, and API behaviour.

## Important limitation

The current formulas and weights are transparent, deterministic where possible,
and reproducible, but they are a baseline rather than a scientifically proven
model. They still require Orange Business expert validation and calibration
against historical outcomes. See [limitations and next
steps](docs/INTERVIEW_GUIDE.md#2-the-top-three-limitations-and-next-steps).
