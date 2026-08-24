"""Command-line interface.

    radar init                  create the database schema
    radar check                 validate config and report vocabulary sizes
    radar refresh               run the pipeline (FR-19)
    radar replay --date ...     historical replay with leakage controls (FR-35)
    radar graph                 rebuild the Orange Business Graph (LK-01)
    radar topics                list topics for a role (FR-13)
    radar show OS001            topic detail with full decomposition (NFR-01)
    radar coverage              language / geography / tier coverage (NFR-08)
    radar whitespace            high attractiveness, no portfolio path (FR-32)
    radar orphan-offers         offers with no live topic (FR-33)
    radar confirm-link          curator confirmation of a link pattern (LK-06)
    radar reference-data        fetch Eurostat sizing denominators (§4.3.4)
    radar size                  compute market size per opportunity space (§4.3.4)
    radar competition           assess competitive intensity per space (§4.3.3)
    radar describe              generate long-form descriptions (FR-14, FR-18)
    radar brief OS001           render the sales/presales PDF brief (FR-18)
    radar serve                 run the read API for the React frontend
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys

from .config import get_config
from .db import Database
from .embeddings import Embedder
from .graph import build_graph
from . import internal as internal_intake
from .internal import KINDS as INTERNAL_KINDS
from .llm import LLMClient
from .pipeline import STAGES, RefreshRunner
from .readmodel import ReadModel


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)-28s %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "urllib3", "openai", "sentence_transformers", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar", description="Orange Business Innovation Radar")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create the database schema")
    sub.add_parser("check", help="Validate configuration and controlled vocabularies")
    sub.add_parser("graph", help="Rebuild the Orange Business Graph from config")
    sub.add_parser("coverage", help="Report language, geography and tier coverage (NFR-08)")
    sub.add_parser("orphan-offers", help="Offers with no live opportunity space (FR-33)")

    refresh = sub.add_parser("refresh", help="Run the pipeline")
    refresh.add_argument("--since-days", type=int, default=30)
    refresh.add_argument("--stages", default=",".join(STAGES),
                         help=f"Comma-separated subset of: {','.join(STAGES)}")
    refresh.add_argument("--sources", default=None, help="Comma-separated source ids")
    refresh.add_argument("--max-clusters", type=int, default=None)
    refresh.add_argument("--target-topics", type=int, default=None,
                         help="Loop synthesis until this many live topics exist (or the evidence runs out)")
    refresh.add_argument("--no-llm", action="store_true", help="Deterministic stages only")
    refresh.add_argument("--no-critic", action="store_true", help="Skip the adversarial critic pass")
    refresh.add_argument("--no-entailment", action="store_true", help="Skip the entailment check")
    refresh.add_argument("--provider", default=None, help="Override RADAR_LLM_PROVIDER (deepseek|openai|ollama|mock)")

    replay = sub.add_parser("replay", help="Historical replay as of a past date (FR-35)")
    replay.add_argument("--date", required=True, help="Reference date, YYYY-MM-DD")
    replay.add_argument("--since-days", type=int, default=90)
    replay.add_argument("--max-clusters", type=int, default=None)
    replay.add_argument("--provider", default=None)

    topics = sub.add_parser("topics", help="List topics ranked for a role")
    topics.add_argument("--role", default="strategist")
    topics.add_argument("--vertical", default=None)
    topics.add_argument("--domain", default=None)
    topics.add_argument("--horizon", default=None)
    topics.add_argument("--competition", default=None,
                        help="Comma-separated levels: none,low,medium,high (§4.3.3)")
    topics.add_argument("--sort", default="rank",
                        help="rank (the role's own ranking) | market_size | attractiveness | "
                             "right_to_win | competition | signals | recent")
    topics.add_argument("--limit", type=int, default=None)
    topics.add_argument("--json", action="store_true")

    show = sub.add_parser("show", help="Topic detail")
    show.add_argument("topic_id")
    show.add_argument("--json", action="store_true")

    white = sub.add_parser("whitespace", help="High attractiveness, no portfolio path (FR-32)")
    white.add_argument("--min-attractiveness", type=float, default=55.0)

    internal = sub.add_parser("internal", help="Internal signal intake — conversations, RFP themes, lost deals (§2.5)")
    internal_sub = internal.add_subparsers(dest="internal_command", required=True)
    add_int = internal_sub.add_parser("add", help="Record an internal signal (inert until moderated)")
    add_int.add_argument("--author", required=True)
    add_int.add_argument("--kind", required=True, choices=sorted(INTERNAL_KINDS))
    add_int.add_argument("--title", required=True)
    add_int.add_argument("--body", default="")
    add_int.add_argument("--vertical", default=None)
    add_int.add_argument("--geographies", default="", help="Comma-separated ISO codes")
    add_int.add_argument("--account-hint", default=None, help="Segment or industry — never a named contact (DR-09)")
    mod_int = internal_sub.add_parser("moderate", help="Approve a pending record so it can be promoted")
    mod_int.add_argument("internal_id")
    mod_int.add_argument("--reject", action="store_true")
    internal_sub.add_parser("pending", help="List records awaiting moderation")
    internal_sub.add_parser("promote", help="Move moderated records into the signal store")

    confirm = sub.add_parser("confirm-link", help="Curator decision on a link pattern (LK-06)")
    confirm.add_argument("pattern")
    confirm.add_argument("--decision", choices=["confirmed", "rejected"], required=True)
    confirm.add_argument("--curator", required=True)
    confirm.add_argument("--reason", default="")

    reference = sub.add_parser("reference-data", help="Fetch Eurostat reference data for sizing (§4.3.4)")
    reference.add_argument("--force", action="store_true", help="Refetch even if recently fetched")
    reference.add_argument("--series", default=None, help="Comma-separated series ids")

    size = sub.add_parser("size", help="Compute market size per opportunity space (§4.3.4)")
    size.add_argument("--topics", default=None, help="Comma-separated topic ids")

    competition = sub.add_parser("competition", help="Assess competitive intensity (§4.3.3)")
    competition.add_argument("--topics", default=None, help="Comma-separated topic ids")

    plan = sub.add_parser("plan", help="Build a five-year portfolio plan (the Planner)")
    plan.add_argument("--label", default="Untitled plan")
    plan.add_argument("--objective", default="profit",
                      choices=["profit", "revenue", "npv", "strategic_coverage"])
    plan.add_argument("--years", type=int, default=5)
    plan.add_argument("--budget", type=float, default=None, help="Total entry effort, person-years")
    plan.add_argument("--slots", type=int, default=None, help="New spaces started per year")
    plan.add_argument("--availability", type=float, default=None,
                      help="Share of capability-pool headcount free for new work (0-1)")
    plan.add_argument("--min-confidence", default="partial",
                      choices=["observed", "partial", "modelled"])
    plan.add_argument("--max-distance", type=int, default=3)
    plan.add_argument("--prefer-verticals", default=None, help="Comma-separated")
    plan.add_argument("--exclude-verticals", default=None, help="Comma-separated")
    plan.add_argument("--geographies", default=None, help="Comma-separated ISO codes")
    plan.add_argument("--narrate", action="store_true", help="Also write the business plan")
    plan.add_argument("--pdf", action="store_true",
                      help="Also export the whole plan as a PDF (inputs, projection, spaces, "
                           "business plan, assumptions)")
    plan.add_argument("--json", action="store_true")
    plan.add_argument("--provider", default=None)

    plans = sub.add_parser("plans", help="List stored plans")
    plans.add_argument("--limit", type=int, default=20)

    cscrape = sub.add_parser("competitor-scrape",
                             help="Crawl competitor sites into the profiling corpus (robots-aware)")
    cscrape.add_argument("--competitors", default=None, help="Comma-separated register ids")
    cscrape.add_argument("--max-pages", type=int, default=None, help="Override pages per competitor")

    cprofile = sub.add_parser("competitor-profile",
                              help="Build a structured profile per competitor from the crawled corpus")
    cprofile.add_argument("--competitors", default=None, help="Comma-separated register ids")
    cprofile.add_argument("--force", action="store_true", help="Rebuild even when the corpus has not moved")
    cprofile.add_argument("--provider", default=None)

    canalyse = sub.add_parser("competitor-analysis",
                              help="Per-topic competitor analysis, with the differentiation angle per competitor")
    canalyse.add_argument("--topics", default=None, help="Comma-separated topic ids")
    canalyse.add_argument("--limit", type=int, default=None)
    canalyse.add_argument("--force", action="store_true", help="Regenerate even when current")
    canalyse.add_argument("--no-llm", action="store_true",
                          help="Structural join only — no written comparison")
    canalyse.add_argument("--provider", default=None)

    describe = sub.add_parser("describe", help="Generate long-form descriptions (FR-14, FR-18)")
    describe.add_argument("--topics", default=None, help="Comma-separated topic ids")
    describe.add_argument("--limit", type=int, default=None, help="Stop after this many topics")
    describe.add_argument("--force", action="store_true", help="Regenerate even if current")
    describe.add_argument("--provider", default=None)

    brief = sub.add_parser("brief", help="Render the sales/presales PDF brief (FR-18)")
    brief.add_argument("topic_id", nargs="?", default=None)
    brief.add_argument("--all", action="store_true", help="Every topic that has a description")
    brief.add_argument("--open", action="store_true", help="Open the PDF when it is written")

    serve = sub.add_parser("serve", help="Run the read API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    cfg = get_config()
    db = Database(cfg.db_path)

    if args.command == "init":
        db.init_schema()
        print(f"Schema created at {cfg.db_path}")
        return 0

    if args.command == "check":
        print(f"Config OK — weight set {cfg.weight_set}, pipeline {cfg.pipeline_version}")
        print(f"  verticals        {len(cfg.verticals):>3}")
        print(f"  use cases        {len(cfg.use_cases):>3}  (§3.3 target 40-60)")
        print(f"  technologies     {len(cfg.technologies):>3}  (§3.3 target 25-40)")
        print(f"  domains          {len(cfg.domains):>3}")
        print(f"  personas         {len(cfg.personas):>3}")
        print(f"  signal types     {len(cfg.signal_types):>3}")
        lex = cfg.lexicon_terms()
        print(f"  lexicon terms    {len(lex):>3}  across {', '.join(cfg.lexicon_languages)} "
              f"(FR-28 relevance gate)")
        print(f"  offers           {len(cfg.offers['offers']):>3}")
        print(f"  named references {len(cfg.references['named']):>3}")
        print(f"  partners         {len(cfg.assets['partners']):>3}")
        print(f"  crosswalk rows   {len(cfg.cpv_to_vertical.rows) + len(cfg.cpv_to_use_case.rows):>3}")
        nace_rows = sum(len(v) for v in cfg.vertical_to_nace.values())
        print(f"  sizing crosswalk {nace_rows:>3} NACE rows over {len(cfg.vertical_to_nace)} verticals, "
              f"{len(cfg.technology_to_adoption)} technology adoption rows  (sizing {cfg.sizing_version})")
        print(f"  competitors      {len(cfg.competitors_raw['competitors']):>3}  ({cfg.competitor_version})")
        enabled = [s["id"] for s in cfg.enabled_sources()]
        catalogued = len(cfg.sources["sources"])
        print(f"  sources          {len(enabled):>3} enabled of {catalogued} catalogued: {', '.join(enabled)}")
        pending = [s["id"] for s in cfg.enabled_sources() if s.get("terms_checked") == "pending"]
        if pending:
            print(f"\n  NFR-07 WARNING: terms of use unconfirmed for: {', '.join(pending)}")
            print("  These must be cleared in Sprint 0 before non-prototype use.")

        # §4.12 names silent coverage loss as a real risk, and `ncsc_uk` proved
        # it: enabled for the whole build, never returned a single item, and
        # said nothing — because graceful degradation makes a dead source cost
        # nothing, and a source that returns zero looks exactly like a source
        # with no news. A catalogue entry that has never produced evidence is a
        # configuration error until someone says otherwise.
        if db.path.exists():
            db.init_schema()
            counted = {r["source_id"]: r["n"] for r in db.query(
                "SELECT source_id, COUNT(*) AS n FROM signals GROUP BY source_id")}
            silent = [s["id"] for s in cfg.enabled_sources() if not counted.get(s["id"])]
            if silent:
                print(f"\n  ZERO-YIELD WARNING: enabled but no signal has ever been stored for: "
                      f"{', '.join(silent)}")
                print("  Either the source has not run yet, or it is failing silently — check "
                      "`collect.errors` in the last refresh before assuming the former.")
        return 0

    if args.command == "internal":
        db.init_schema()
        if args.internal_command == "add":
            geographies = [g.strip() for g in (args.geographies or "").split(",") if g.strip()]
            internal_id = internal_intake.record(
                db, author=args.author, kind=args.kind, title=args.title, body=args.body,
                vertical=args.vertical, geographies=geographies, account_hint=args.account_hint,
            )
            print(f"Recorded {internal_id} — pending moderation. "
                  f"Approve with: radar internal moderate {internal_id}")
            return 0
        if args.internal_command == "moderate":
            found = internal_intake.moderate(db, args.internal_id, approved=not args.reject)
            if not found:
                print(f"No internal signal with id {args.internal_id!r}", file=sys.stderr)
                return 2
            print(f"{args.internal_id} {'rejected' if args.reject else 'approved'}")
            return 0
        if args.internal_command == "pending":
            rows = internal_intake.pending(db)
            if not rows:
                print("Nothing awaiting moderation.")
                return 0
            for row in rows:
                print(f"{row['id']}  {row['created_at'][:10]}  {row['kind']:<22}  "
                      f"{row['author']:<18}  {row['title'][:60]}")
            return 0
        if args.internal_command == "promote":
            print(json.dumps(internal_intake.promote(cfg, db), indent=2))
            return 0

    if args.command == "graph":
        db.init_schema()
        print(json.dumps(build_graph(cfg, db), indent=2))
        return 0

    if args.command in ("refresh", "replay"):
        if getattr(args, "provider", None):
            import os
            os.environ["RADAR_LLM_PROVIDER"] = args.provider
        use_llm = not getattr(args, "no_llm", False)
        llm = LLMClient(max_retries=cfg.settings["llm"]["max_retries"]) if use_llm else None
        runner = RefreshRunner(cfg, db, llm, Embedder())
        if args.command == "replay":
            reference_date = dt.date.fromisoformat(args.date)
            if reference_date >= dt.date.today():
                print("Replay requires a past date.", file=sys.stderr)
                return 2
            stats = runner.run(reference_date, args.since_days, max_clusters=args.max_clusters)
        else:
            stages = tuple(s.strip() for s in args.stages.split(",") if s.strip())
            unknown = [s for s in stages if s not in STAGES]
            if unknown:
                print(f"Unknown stage(s): {unknown}. Known: {list(STAGES)}", file=sys.stderr)
                return 2
            stats = runner.run(
                since_days=args.since_days,
                stages=stages,
                source_ids=[s.strip() for s in args.sources.split(",")] if args.sources else None,
                max_clusters=args.max_clusters,
                target_topics=args.target_topics,
                use_llm=use_llm,
                run_critic=not args.no_critic,
                run_entailment=not args.no_entailment,
            )
        print(json.dumps(stats, indent=2, default=str))
        return 0

    if args.command == "reference-data":
        from .reference import ReferenceDataFetcher, reference_status
        stats = ReferenceDataFetcher(cfg, db).run(
            series_ids=[s.strip() for s in args.series.split(",")] if args.series else None,
            force=args.force,
        )
        print(json.dumps(stats, indent=2))
        print(json.dumps(reference_status(db), indent=2, default=str))
        return 0

    if args.command == "size":
        from .sizing import MarketSizer
        stats = MarketSizer(cfg, db).run(
            topic_ids=[t.strip() for t in args.topics.split(",")] if args.topics else None
        )
        print(json.dumps(stats, indent=2))
        if stats.get("no_estimate"):
            print(f"\n{len(stats['no_estimate'])} topic(s) could not be sized. §4.3.4 prefers a "
                  f"missing number to a manufactured one; run `radar reference-data` if the "
                  f"reference store is empty.")
        return 0

    if args.command == "competition":
        from .competition import CompetitionAnalyser
        stats = CompetitionAnalyser(cfg, db).run(
            topic_ids=[t.strip() for t in args.topics.split(",")] if args.topics else None
        )
        print(json.dumps(stats, indent=2))
        return 0

    if args.command == "plans":
        from .planner import list_plans
        for row in list_plans(db, args.limit):
            pr = row["projection"] or {}
            print(f"{row['id']}  {row['created_at'][:16]}  {row['selected_count']:>3} spaces  "
                  f"profit EUR{(pr.get('profit_total') or 0)/1e6:>8,.0f}m  {row['label']}")
        return 0

    if args.command == "plan":
        if getattr(args, "provider", None):
            import os
            os.environ["RADAR_LLM_PROVIDER"] = args.provider
        from .planner import Planner, PlanInputs

        def split(v):
            return tuple(x.strip() for x in v.split(",")) if v else ()

        inputs = PlanInputs(
            label=args.label, objective=args.objective, plan_years=args.years,
            budget_person_years=args.budget, entry_slots_per_year=args.slots,
            pool_availability=args.availability, min_confidence=args.min_confidence,
            max_portfolio_distance=args.max_distance,
            prefer_verticals=split(args.prefer_verticals),
            exclude_verticals=split(args.exclude_verticals),
            geographies=split(args.geographies),
        )
        planner = Planner(cfg, db)
        result = planner.plan(inputs)
        if args.narrate:
            result = planner.narrate(result["id"])
        report = None
        if args.pdf:
            from .plan_report import PlanReportBuilder
            # After the narrative, never before: the document is a snapshot, and
            # one taken first would be missing the business plan.
            report = PlanReportBuilder(cfg, db).build(planner.get(result["id"]))
            result["report"] = report
        if args.json:
            print(json.dumps(result, indent=2, default=str))
            return 0
        pr = result["projection"]
        print(f"\n{result['id']}  —  {result['label']}")
        print(f"{result['selected_count']} spaces selected from {result['considered_count']} candidates\n")
        print(f"{'year':>6}{'revenue':>14}{'profit':>12}")
        for i, (rev, prof) in enumerate(zip(pr["revenue_by_year"], pr["profit_by_year"]), 1):
            print(f"{i:>6}{rev/1e6:>13,.1f}m{prof/1e6:>11,.1f}m")
        print(f"{'total':>6}{pr['revenue_total']/1e6:>13,.1f}m{pr['profit_total']/1e6:>11,.1f}m")
        print(f"\nprofit band  EUR{pr['profit_total_low']/1e6:,.0f}m - EUR{pr['profit_total_high']/1e6:,.0f}m")
        print(f"NPV @ {pr['discount_rate']:.1%}  EUR{pr['npv_profit']/1e6:,.0f}m")
        print(f"year-{pr['years']} revenue is {pr['year5_share_of_segment']:.1%} of the filed segment")
        binding = (result.get("capacity_usage") or {}).get("binding") or []
        if binding:
            print("\nwhat bound this plan:")
            for b in binding:
                print(f"  - {b}")
        for f in result.get("flags") or []:
            print(f"\n[{f['severity'].upper()}] {f['message']}")
        if result.get("narrative"):
            print(f"\n{result['narrative'].get('headline','')}")
        if report:
            print(f"\nPDF  {report['path']}  ({report['bytes']:,} bytes)")
        return 0

    if args.command == "competitor-scrape":
        from .competitor_intel import CompetitorCrawler
        crawler = CompetitorCrawler(cfg, db)
        if args.max_pages:
            crawler.max_pages = args.max_pages
        stats = crawler.run(
            only=[c.strip() for c in args.competitors.split(",")] if args.competitors else None
        )
        print(json.dumps(stats, indent=2))
        return 0

    if args.command == "competitor-profile":
        if getattr(args, "provider", None):
            import os
            os.environ["RADAR_LLM_PROVIDER"] = args.provider
        from .competitor_intel import ProfileBuilder
        stats = ProfileBuilder(cfg, db).run(
            only=[c.strip() for c in args.competitors.split(",")] if args.competitors else None,
            force=args.force,
        )
        print(json.dumps(stats, indent=2))
        return 0

    if args.command == "competitor-analysis":
        if getattr(args, "provider", None):
            import os
            os.environ["RADAR_LLM_PROVIDER"] = args.provider
        from .competitor_analysis import CompetitorAnalyst
        stats = CompetitorAnalyst(cfg, db).run(
            topic_ids=[t.strip() for t in args.topics.split(",")] if args.topics else None,
            limit=args.limit, force=args.force, use_llm=not args.no_llm,
        )
        print(json.dumps(stats, indent=2))
        return 0

    if args.command == "describe":
        if getattr(args, "provider", None):
            import os
            os.environ["RADAR_LLM_PROVIDER"] = args.provider
        from .pipeline.describe import DescriptionGenerator
        generator = DescriptionGenerator(cfg, db, LLMClient(max_retries=cfg.settings["llm"]["max_retries"]))
        stats = generator.run(
            topic_ids=[t.strip() for t in args.topics.split(",")] if args.topics else None,
            limit=args.limit, force=args.force,
        )
        print(json.dumps(stats, indent=2))
        return 0

    if args.command == "brief":
        from .brief import BriefBuilder
        builder = BriefBuilder(cfg, db)
        if args.all:
            rows = db.query(
                "SELECT opportunity_id FROM topic_descriptions ORDER BY opportunity_id"
            )
            targets = [r["opportunity_id"] for r in rows]
            if not targets:
                print("No descriptions generated yet — run `radar describe` first.", file=sys.stderr)
                return 1
        elif args.topic_id:
            targets = [args.topic_id]
        else:
            print("Give a topic id or --all.", file=sys.stderr)
            return 2
        for topic_id in targets:
            try:
                meta = builder.build(topic_id)
            except KeyError as exc:
                print(exc, file=sys.stderr)
                return 1
            print(f"{topic_id}  {meta['bytes']:>7} bytes  {meta['filename']}")
        if args.open and len(targets) == 1:
            import subprocess
            from .brief import brief_path
            path = brief_path(db, targets[0])
            if path:
                subprocess.run(["open", str(path)], check=False)
        return 0

    read = ReadModel(cfg, db)

    if args.command == "topics":
        from .readmodel import SORTS
        if args.sort not in SORTS:
            print(f"Unknown sort {args.sort!r}. Known: {list(SORTS)}", file=sys.stderr)
            return 2
        filters = {}
        for key, value in (("vertical", args.vertical), ("domain", args.domain),
                           ("horizon", args.horizon), ("competition", args.competition)):
            if value:
                filters[key] = [v.strip() for v in value.split(",")]
        view = read.view(args.role, filters, args.limit, sort=args.sort)
        if args.json:
            print(json.dumps(view, indent=2, default=str))
            return 0
        from .readmodel import SORTS as _SORTS
        print(f"\n{view['role_label']} — {view['total_matching']} matching, showing {len(view['topics'])} "
              f"(cap {view['cap']}, weight set {view['weight_set']}, "
              f"order: {_SORTS[view.get('sort', 'rank')].lower()})")
        if view["last_refresh"]:
            print(f"Last refresh: {view['last_refresh'].get('finished_at') or view['last_refresh']['started_at']}")
        print()
        for i, topic in enumerate(view["topics"], 1):
            att = (topic.get("attractiveness") or {}).get("score", 0)
            rtw = (topic.get("right_to_win") or {}).get("score", 0)
            gap = "  [EVIDENCE GAP]" if topic["evidence_gap_warning"] else ""
            from .sizing import format_eur
            size = (topic.get("market_size_summary") or {}).get("sam_base")
            level = (topic.get("competition") or {}).get("level") or "-"
            print(f"{i:2}. {topic['id']}  A={att:5.1f}  RtW={rtw:5.1f}  "
                  f"L{topic['portfolio_distance']}  {topic['horizon'] or '?':5}  {topic['state']:9}"
                  f"  SAM {format_eur(size):>8}  competition {level:6}{gap}")
            print(f"    {topic['statement']}")
            print(f"    {topic['labels']['vertical']} x {topic['labels']['use_case']} x "
                  f"{topic['labels']['technology']}  ({topic['signal_count']} signals)")
            action = topic["next_actions"].get(args.role)
            if action:
                print(f"    -> {action}")
            print()
        for topic in view["exploration"]:
            print(f" *  {topic['id']}  [exploration slot — countering exposure bias, §4.7.6]")
            print(f"    {topic['statement']}\n")
        return 0

    if args.command == "show":
        topic = read.topic(args.topic_id)
        if topic is None:
            print(f"No such topic: {args.topic_id}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(topic, indent=2, default=str))
            return 0
        _print_topic(topic)
        return 0

    if args.command == "whitespace":
        rows = read.white_space(args.min_attractiveness)
        print(f"\nWhite space — high attractiveness, no path from the portfolio ({len(rows)} topics)\n")
        for topic in rows:
            att = (topic.get("attractiveness") or {}).get("score", 0)
            print(f"  {topic['id']}  A={att:5.1f}  L{topic['portfolio_distance']}  {topic['statement']}")
        return 0

    if args.command == "orphan-offers":
        from .graph import Linker
        rows = Linker(cfg, db).offers_without_topics()
        print(f"\nOffers with no live opportunity space attached ({len(rows)}) — portfolio-decay signal (§4.5.5)\n")
        for row in rows:
            print(f"  {row['id']:45} {row['label']}")
        return 0

    if args.command == "coverage":
        print(json.dumps(read.coverage(), indent=2))
        return 0

    if args.command == "confirm-link":
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with db.cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO link_pattern_decisions (pattern, decision, curator, reason, decided_at) "
                "VALUES (?,?,?,?,?)",
                (args.pattern, args.decision, args.curator, args.reason, now),
            )
        print(f"Recorded: {args.pattern} -> {args.decision} by {args.curator}")
        print("Re-run `radar refresh --stages link` to apply it to existing topics.")
        return 0

    if args.command == "serve":
        import uvicorn
        uvicorn.run("radar.api:app", host=args.host, port=args.port, reload=args.reload)
        return 0

    return 1


def _print_topic(topic: dict) -> None:
    print(f"\n{'=' * 78}\n{topic['id']}  v{topic['version']}   {topic['statement']}\n{'=' * 78}")
    print(f"Triple      : {topic['triple']['vertical']} x {topic['triple']['use_case']} x "
          f"{topic['triple']['technology']}")
    print(f"State       : {topic['state']} — {topic['state_reason']}")
    print(f"Horizon     : {topic['horizon']} (basis: {topic['horizon_basis']})")
    print(f"Distance    : L{topic['portfolio_distance']}  link types {topic['link_types']}")
    print(f"Refreshed   : {topic['last_refresh']}  (first seen {topic['first_seen']})")

    for kind in ("attractiveness", "right_to_win"):
        score = topic.get(kind)
        if not score:
            continue
        print(f"\n{kind.upper()}: {score['score']}   [weight set {score['weight_set']}]")
        for name, value in sorted(score["components"].items(), key=lambda kv: -kv[1]):
            bar = "#" * int(value / 4)
            print(f"    {name:26} {value:6.2f}  {bar}")

    if topic["evidence_gap_warning"]:
        density = topic.get("reference_density", {})
        print(f"\n!! EVIDENCE GAP (SC-13): {density.get('published_story_count')} published references in "
              f"{density.get('vertical')}, threshold {density.get('threshold')}")

    print("\nWHY HOT (every claim evidence-bound, FR-14):")
    for claim in topic["why_hot"]:
        print(f"  - {claim['claim']}")
        print(f"    signals: {', '.join(claim['signals'])}")

    print("\nCAN WE PLAY / CAN WE WIN (named, individually inspectable — LK-08):")
    for link in sorted(topic["links"], key=lambda l: l["link_type"]):
        curator = f" confirmed by {link['confirmed_by']}" if link["confirmed_by"] else " UNCONFIRMED"
        print(f"  [{link['link_type']}] {link['label']:42} conf={link['confidence']:.2f}{curator}")
        print(f"        {link['evidence'].get('rule', '')}")

    print("\nNEXT ACTIONS (FR-17):")
    for role, action in topic["next_actions"].items():
        print(f"  {role:11}: {action}")

    if topic.get("signals"):
        print(f"\nSOURCES ({len(topic['signals'])}) — NFR-02 lineage:")
        for signal in topic["signals"][:12]:
            print(f"  [{signal['id']}] t{signal['tier']} {signal['published_at']} "
                  f"{signal['publisher'][:28]:28} {signal['title'][:52]}")
            print(f"        {signal['url']}")

    print(f"\nPROVENANCE (DR-10): {topic['provenance']}")


if __name__ == "__main__":
    sys.exit(main())
