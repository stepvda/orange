# Project timeline and time-tracking

A retrospective project plan reconstructed from the git history, written after
delivery. Every figure below is read from the commit record rather than from
memory or a timesheet: dates, times, authors, branches, and the number of lines
each commit added or removed.

**Repository span:** 19 August 2026, 02:18 → 31 August 2026, 13:44 (CEST)
**Commits on `main`:** 47 · **Contributors in git:** 2 · **Active days:** 9

---

## How to read this document

Commit timestamps record **when work landed**, not how long it took. They are a
floor on effort, never a measure of it, and three limits matter here:

1. **Work before the first commit is invisible.** The initial commit landed
   27,079 lines of authored code across 127 files at 02:18 on day one — a
   working pipeline, API, frontend and document generators. That system was
   built before git was watching, so none of its effort appears in any table
   below.
2. **Not every contributor commits.** The README names three team members;
   two appear in the commit history. A business-analysis contribution leaves no
   git trace, and its absence here is a property of the measuring instrument,
   not of the work.
3. **Thinking time is unattributable.** A commit at 23:51 says the work was
   finished then. It does not say when it started.

The session estimate below adds a 45-minute lead-in per working session to
partially correct for point 3. It is a defensible lower bound, not a true
effort figure.

---

## At a glance

| Measure | Value |
|---|---|
| Calendar span | 13 days (19–31 August 2026) |
| Active days | 9 |
| Weekend commits | 0 |
| Commits on `main` | 47 (7 of them merges) |
| Average commits per active day | 5.2 |
| Busiest day by volume | Mon 24 Aug — 11 commits, 14h 44m window |
| Busiest day by count | Tue 25 Aug — 16 commits |
| Authored lines added / removed | +144,702 / −10,943 |
| Vendored lines excluded from that | 767,462 (`node_modules`, lockfiles, source maps) |
| Feature branches used | 7 (6 still on the remote; `database-archive` deleted after merge) |
| Pull requests merged | 5 (plus 2 direct branch merges) |
| Identified working sessions | 13 |
| Commit-window hours | 12.2 |
| Estimated engaged hours (window + lead-in) | ~22 |

The gap between 144,702 authored lines and ~22 tracked hours is the clearest
evidence for caveat 1: the repository received a largely finished system rather
than growing one commit at a time.

---

## Phases

### Phase 1 — Bootstrap (Wed 19 Aug, 4 commits)

The repository opens at 02:18 with the system already standing: `src/radar/`
with scoring, sizing, brief generation, synthesis, the API and the read model;
the React frontend; the config taxonomies; and the documentation generators.
A second commit at 14:16 adds 174 generated opportunity briefs under `data/`
along with the frontend dependency tree — 839 vendored files in one commit.

Day 1 covers a 12-hour window (02:18 → 14:16) in three disconnected bursts,
which reads as import-and-tidy rather than sustained development.

### Phase 2 — Engine iteration (Thu 20 – Fri 21 Aug, 4 commits)

Backend and frontend refinement (+3,704 lines on the 20th), then on the 21st a
large pass across the pipeline and config (+8,119) and a documentation-generation
push in the afternoon (+7,178, 31 files under `docs/generators` and
`docs/_build`). This is where the deck, diagram and Word-document build chain
takes shape.

*Weekend gap: 22–23 August, no commits.*

### Phase 3 — Feature sprint (Mon 24 Aug, 11 commits) — the peak

The single most productive day of the project, and the one that defines the
product's final shape.

- **09:07** — the Planner lands (`src/radar/planner.py`, +4,773), and `radar.db`
  stops being tracked.
- **18:52–23:51** — a five-hour evening session of 10 commits:
  - sign-in and space deletion (`src/radar/auth.py`, +2,290)
  - a guard stopping a delete reaching outside its database, plus the test
    covering it — a fix and its regression test, 5 minutes apart
  - the Generate screen's text box replaced by a scoping conversation (+3,574)
  - the twelve-piece pre-sales pack (+7,912, 32 files)
  - three corrective commits: a chart label, evidence judged by sentence rather
    than taxonomy label, and the corpus rather than the assistant gating the
    Generate button

Roughly 19,800 authored lines landed between 18:52 and 23:51.

### Phase 4 — Collaboration and hardening (Tue 25 Aug, 16 commits) — the peak by count

The only genuinely two-person day, and the day the branch workflow appears.
Sixteen commits between 09:59 and 16:33, including four merges: PR #1
(workflow stage filter), the `presales-collateral` branch, PR #2 (`updates`),
and PR #3 (`bugfixes`).

Its signature is **deletion**: 7,206 lines removed against 5,852 added — the
only day in the project that removed more than it added. One commit alone
(`302ccca`, "update doc generators") removes 5,955 lines, retiring the
superseded walkthrough deck and film.

Six of the day's commits are single-defect fixes with narrow diffs: a run that
never reached the model calling itself an evidence verdict; the corpus leaking
into contributed evidence; the interview forgetting what it had settled.

### Phase 5 — Packaging and delivery (Wed 26 – Fri 28 Aug, 9 commits)

Short, targeted sessions. The working database is committed as a split zip
archive (PR #4); in-app contextual help explaining how the radar was built lands
via PR #5 (+929); the presentation slides are updated; and repository hygiene
adds Office lock files and the docs scratch dump to `.gitignore`. The 28th also
carries a +2,634-line documentation pass.

A Dependabot branch (`torch` 2.6.0+cpu → 2.12.1+cpu) is opened on the 28th and
is **not merged** — it remains the one open piece of dependency maintenance.

*Weekend gap: 29–30 August, no commits.*

### Phase 6 — Documentation restructure and handover (Mon 31 Aug, 3 commits)

Thirteen minutes, 13:31 → 13:44, and the last work on the project. The 1,893-line
README is split into seven topic guides under `docs/` (+1,966 / −1,860), team
contributions are recorded, and the final presentation is linked. The project
ends on a documentation commit rather than a code commit.

---

## Day-by-day timetable

| Date | Day | Commits | First | Last | Window | +lines | −lines | Files | Who | Focus |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 Aug | Wed | 4 | 02:18 | 14:16 | 11h 58m | 89,510 | 53 | 320 | S | bootstrap, generated briefs |
| 20 Aug | Thu | 1 | 14:09 | 14:09 | — | 3,704 | 89 | 21 | S | frontend + backend |
| 21 Aug | Fri | 3 | 08:50 | 16:32 | 7h 42m | 15,298 | 588 | 96 | S | pipeline, doc generators |
| 22–23 Aug | Sat–Sun | 0 | — | — | — | — | — | — | — | *weekend* |
| 24 Aug | Mon | 11 | 09:07 | 23:51 | 14h 44m | 24,600 | 861 | 154 | S | Planner, auth, pre-sales pack |
| 25 Aug | Tue | 16 | 09:59 | 16:33 | 6h 34m | 5,852 | 7,206 | 119 | S + L | merges, bugfixes, cleanup |
| 26 Aug | Wed | 5 | 14:53 | 15:06 | 13m | 1,120 | 9 | 10 | S | db archive, in-app help |
| 27 Aug | Thu | 1 | 11:29 | 11:29 | — | 0 | 0 | 1 | L | presentation slides |
| 28 Aug | Fri | 3 | 10:16 | 10:30 | 14m | 2,645 | 277 | 11 | S | docs pass, gitignore |
| 29–30 Aug | Sat–Sun | 0 | — | — | — | — | — | — | — | *weekend* |
| 31 Aug | Mon | 3 | 13:31 | 13:44 | 13m | 1,973 | 1,860 | 10 | L | README restructure |

S = Stephane van der Aa · L = lienkt

---

## Session log (the timesheet)

Sessions are inferred by splitting the commit stream wherever more than 150
minutes pass between consecutive commits. "Window" is first-to-last commit;
"Est." adds a 45-minute lead-in for work preceding the first commit.

| # | Session | Window | Est. | Commits | Focus |
|---|---|---|---|---|---|
| 1 | Wed 19 Aug 02:18 | — | 0.8h | 1 | initial import |
| 2 | Wed 19 Aug 06:54 | — | 0.8h | 1 | follow-up fixes |
| 3 | Wed 19 Aug 14:14–14:16 | 2m | 0.8h | 2 | briefs + frontend deps |
| 4 | Thu 20 Aug 14:09 | — | 0.8h | 1 | frontend + backend |
| 5 | Fri 21 Aug 08:50 | — | 0.8h | 2 | pipeline + config |
| 6 | Fri 21 Aug 16:32 | — | 0.8h | 1 | doc generators |
| 7 | Mon 24 Aug 09:07 | — | 0.8h | 1 | the Planner |
| 8 | **Mon 24 Aug 18:52–23:51** | **5h 0m** | **5.7h** | **10** | **auth, scoping, pre-sales pack** |
| 9 | **Tue 25 Aug 09:59–16:33** | **6h 34m** | **7.3h** | **16** | **merges, bugfixes, cleanup** |
| 10 | Wed 26 Aug 14:53–15:06 | 13m | 1.0h | 5 | db archive, in-app help |
| 11 | Thu 27 Aug 11:29 | — | 0.8h | 1 | slides |
| 12 | Fri 28 Aug 10:16–10:30 | 14m | 1.0h | 3 | docs, gitignore |
| 13 | Mon 31 Aug 13:31–13:44 | 13m | 1.0h | 3 | README restructure |
| | **Total** | **12.2h** | **~22h** | **47** | |

Sessions 8 and 9 alone account for 13 of the 22 estimated hours and 26 of the
47 commits. The project's centre of gravity is a single evening and the
following day.

---

## Working patterns

### Hour of day

```
02:00  #                                    1
06:00  #                                    1
08:00  ##                                   2
09:00  ##                                   2
10:00  #######                              7
11:00  ####                                 4
12:00  #                                    1
13:00  ###                                  3
14:00  ########                             8
15:00  ####                                 4
16:00  ####                                 4
18:00  #                                    1
19:00  ###                                  3
20:00  ####                                 4
21:00  #                                    1
23:00  #                                    1
```

Two peaks — mid-morning (10:00–11:00, 11 commits) and mid-afternoon
(14:00–16:00, 16 commits) — with a distinct evening tail. **Ten of 47 commits
(21%) land at or after 18:00**, and two before 08:00. The 02:18 and 23:51
commits bracket a project worked substantially outside office hours.

### Day of week

| Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|
| 14 | 16 | 9 | 2 | 6 | 0 | 0 |

**Zero weekend commits across two weekends.** Monday and Tuesday carry 30 of
47 commits (64%); Thursday is the quietest weekday at 2. Both weeks front-load.

### Cadence

Nine active days in a thirteen-day span. The rhythm is not steady: four days
carry 1–3 commits each, while two days carry 27 between them. Work arrived in
concentrated bursts separated by quiet days, rather than at a constant rate.

---

## Where the effort went

File touches per area, counted across all authored commits (vendored
dependencies excluded):

| Area | File touches | Share |
|---|---|---|
| Generated artefacts (`data/`, PDFs, decks, diagrams) | 241 | 32% |
| Backend (`src/radar/`) | 139 | 19% |
| Frontend (`frontend/`) | 110 | 15% |
| Document generators (`docs/generators`, `docs/_build`) | 94 | 13% |
| Documentation (`*.md`, `docs/`) | 58 | 8% |
| Tests (`tests/`) | 41 | 5% |
| Other (root config, CI, scripts) | 31 | 4% |
| Configuration (`config/`) | 28 | 4% |

Generated artefacts and the machinery that produces them (`artefact` + `docgen`
+ `docs`) total **53% of all file touches** — more than backend and frontend
combined. For a project whose output is briefs, decks and design documents,
that ratio is the point rather than an overhead.

### Churn hotspots

Lines added plus removed over the project's life:

| Lines | File |
|---|---|
| 4,612 | `README.md` |
| 2,591 | `frontend/src/theme.css` |
| 2,398 | `docs/_build/ta_content.py` |
| 2,167 | `src/radar/api.py` |
| 2,118 | `docs/_build/fdd_content.py` |
| 2,014 | `frontend/src/types.ts` |
| 1,789 | `frontend/src/App.tsx` |
| 1,686 | `frontend/src/components/Planner.tsx` |
| 1,602 | `src/radar/pipeline/prompts.py` |
| 1,580 | `src/radar/pipeline/synthesis.py` |
| 1,376 | `src/radar/planner.py` |

`README.md` is the most-rewritten file in the repository — written at 938 lines,
grown to 1,893, then split to 128 and rebuilt. The two narrative document
sources (`ta_content.py`, `fdd_content.py`) place third and fifth, ahead of
every backend module.

---

## Collaboration timeline

| Contributor | Commits | +lines | −lines | Primary areas |
|---|---|---|---|---|
| Stephane van der Aa | 40 | 140,831 | 2,156 | artefacts, backend, frontend |
| lienkt | 7 | 3,871 | 8,787 | doc generators, documentation |
| dependabot | 1 | — | — | dependency bump (branch only, unmerged) |

The two profiles are complementary rather than overlapping: one net-additive
across the whole system, one net-subtractive and concentrated in documentation —
7 commits that removed 8,787 lines and added 3,871, which is what consolidation
looks like.

Collaboration is also sharply bounded in time. Both contributors are active on
**one day only (25 August)**; the second contributor's other commits fall on the
27th and the 31st, after the first had stopped.

### Branch and merge history

| When | Merge | Branch |
|---|---|---|
| 25 Aug 10:29 | PR #1 | `lien-add-workflow-stage-in-planner` |
| 25 Aug 11:07 | direct | `presales-collateral` |
| 25 Aug 14:18 | PR #2 | `updates` |
| 25 Aug 16:33 | PR #3 | `bugfixes` |
| 26 Aug 14:54 | PR #4 | `database-archive` |
| 26 Aug 15:05 | direct | `origin/updates` → `radar-help` |
| 26 Aug 15:06 | PR #5 | `radar-help` |

All seven merges fall inside a 29-hour span on 25–26 August. Before the 25th,
work went straight onto `main`; after the 26th, it went straight onto `main`
again. The branch-and-PR discipline coincides exactly with the period when two
people were working at once.

---

## Observations for the next project

**What the record shows working well.**

- **Fix and test committed together.** On 24 August, `315a769` guards a delete
  from reaching outside its database and `7a54172` covers that path with a test
  — five minutes apart. The pattern recurs across the bugfix commits.
- **Descriptive commit subjects.** From 24 August onward, subjects state the
  behaviour changed rather than the file touched ("Stop a run that never reached
  the model calling it an evidence verdict"). Reconstructing this timeline was
  possible because of them.
- **Branches appeared exactly when they were needed.** Direct-to-`main` while
  solo, PRs the moment a second contributor joined.

**What the record shows costing time.**

- **12 of 47 commit subjects are `--`.** All fall in the early and middle
  phases, and they are the hardest commits to account for — several are large
  (`66d1851`: 185 files; `cbbdf68`: +4,222/−427). The narrative gaps in Phases
  1, 2 and 5 above are gaps in the commit messages, not in the work.
- **Vendored dependencies were committed.** 767,462 lines of `node_modules`,
  lockfiles and source maps in the history, 839 such files in a single commit.
  This inflates every raw statistic and forced the exclusion filter used
  throughout this document.
- **The README carried too much.** At 1,893 lines it was the most-churned file
  in the project, and unloading it on the final day cost a dedicated session.
  Splitting earlier would have spread that cost.
- **Documentation clustered at the end.** Phases 5 and 6 are almost entirely
  documentation and packaging. Front-loading some of it would have reduced the
  end-of-project crunch visible in the last three sessions.

**Open at close of project.**

- The Dependabot `torch` 2.12.1+cpu branch is unmerged.
- Six merged feature branches remain undeleted on the remote; only
  `database-archive` was cleaned up after its merge.

---

## Reproducing these figures

```bash
# Commit stream with dates, authors and subjects
git log --reverse --format='%h|%ad|%an|%s' --date=format:'%Y-%m-%d %H:%M %a'

# Per-commit line counts (filter node_modules, *.map, package-lock.json)
git log --reverse --format='C|%h|%ad|%an|%s' --date=iso --numstat

# Active days, weekday and hour distributions
git log --format='%ad' --date=short | sort -u | wc -l
git log --format='%ad' --date=format:'%a'  | sort | uniq -c
git log --format='%ad' --date=format:'%H'  | sort | uniq -c

# Merges and contributors
git log --merges --reverse --format='%h|%ad|%s' --date=format:'%m-%d %H:%M'
git shortlog -sne --all
```

Sessions are derived by splitting the commit stream at gaps longer than 150
minutes. Line counts throughout exclude `node_modules/`, `dist/`,
`package-lock.json` and `*.map`; binary files count as a file touch with zero
lines.
