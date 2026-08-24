"""Configuration and controlled-vocabulary loading.

NFR-11: taxonomies, source lists, prompts and weights are configuration, not
code. Nothing in this package hard-codes a vertical, a weight or a threshold —
it all arrives through here.

§3.3: the vocabularies are implemented with stable identifiers, not free text,
because opportunity-space identity, deduplication and filtering all depend on
them.
"""

from __future__ import annotations

import csv
import functools
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"

load_dotenv(PROJECT_ROOT / ".env")


def _load_yaml(*parts: str) -> dict[str, Any]:
    path = CONFIG_DIR.joinpath(*parts)
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _load_csv(*parts: str) -> list[dict[str, str]]:
    """Read a crosswalk CSV, skipping the `#` comment preamble (DR-12)."""
    path = CONFIG_DIR.joinpath(*parts)
    if not path.exists():
        raise FileNotFoundError(f"Missing crosswalk file: {path}")
    with path.open(encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VocabItem:
    id: str
    label: str
    definition: str = ""
    synonyms: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def get(self, key: str, default: Any = None) -> Any:
        return self.extra.get(key, default)


class Vocabulary:
    """An enumerated, closed vocabulary.

    §4.4.2: the model may only emit values from these lists; anything else
    fails validation and is retried once, then dropped.
    """

    def __init__(self, name: str, raw: dict[str, Any]):
        self.name = name
        self.version: str = raw.get("version", "unversioned")
        self.owner: str = raw.get("owner", "unowned")
        self.raw = raw
        self._items: dict[str, VocabItem] = {}
        for entry in raw.get("items", []):
            known = {"id", "label", "definition", "synonyms", "exclusions"}
            item = VocabItem(
                id=entry["id"],
                label=entry.get("label", entry["id"]),
                definition=(entry.get("definition") or "").strip(),
                synonyms=tuple(entry.get("synonyms") or ()),
                exclusions=tuple(entry.get("exclusions") or ()),
                extra={k: v for k, v in entry.items() if k not in known},
            )
            self._items[item.id] = item

    def __contains__(self, key: object) -> bool:
        return key in self._items

    def __iter__(self):
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, key: str) -> VocabItem:
        return self._items[key]

    @property
    def ids(self) -> list[str]:
        return list(self._items)

    def get(self, key: str) -> VocabItem | None:
        return self._items.get(key)

    def label(self, key: str) -> str:
        item = self._items.get(key)
        return item.label if item else key

    def resolve(self, text: str) -> str | None:
        """Map free text onto a vocabulary id via id, label or synonym.

        Used to repair near-miss model output before failing validation, and to
        tag crosswalk rows. Deliberately conservative: exact match only, so it
        cannot silently invent a mapping.
        """
        needle = (text or "").strip().lower()
        if not needle:
            return None
        for item in self._items.values():
            if needle == item.id.lower() or needle == item.label.lower():
                return item.id
            if any(needle == s.lower() for s in item.synonyms):
                return item.id
        return None

    def prompt_block(self, include_definitions: bool = True) -> str:
        """Render the vocabulary for injection into a prompt (§4.4.2)."""
        lines = []
        for item in self._items.values():
            if include_definitions and item.definition:
                line = f"- {item.id}: {item.label} — {item.definition}"
                if item.exclusions:
                    line += f" (NOT: {', '.join(item.exclusions)})"
            else:
                line = f"- {item.id}: {item.label}"
            lines.append(line)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Crosswalks (LK-02, DR-12)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CrosswalkRow:
    version: str
    source_code: str
    target: str
    confidence: float
    owner: str
    note: str = ""


class Crosswalk:
    """Versioned many-to-many mapping with a confidence weight per row.

    §4.5.2: every downstream number — market size, procurement volume,
    reference density, patent coverage — inherits this table's errors, so
    confidence is applied as a multiplier rather than discarded.

    Lookup is by longest prefix, because classification schemes are
    hierarchical: CPV 72212730 is more specific than 72.
    """

    HORIZONTAL = "HORIZONTAL"

    def __init__(self, name: str, rows: list[dict[str, str]], code_field: str, target_field: str):
        self.name = name
        self.rows: list[CrosswalkRow] = [
            CrosswalkRow(
                version=r.get("version", "unversioned"),
                source_code=r[code_field].strip(),
                target=r[target_field].strip(),
                confidence=float(r.get("confidence", 1.0)),
                owner=r.get("owner", "unowned"),
                note=r.get("note", ""),
            )
            for r in rows
            if r.get(code_field) and r.get(target_field)
        ]
        # Longest prefix first, so the first match wins.
        self._by_len = sorted(self.rows, key=lambda r: len(r.source_code), reverse=True)

    def lookup(self, code: str) -> list[CrosswalkRow]:
        """Return every row matching the longest matching prefix of `code`."""
        code = (code or "").strip()
        if not code:
            return []
        best_len = None
        matches: list[CrosswalkRow] = []
        for row in self._by_len:
            if not code.startswith(row.source_code):
                continue
            if best_len is None:
                best_len = len(row.source_code)
            if len(row.source_code) == best_len:
                matches.append(row)
            else:
                break
        return matches

    def resolve(self, codes: list[str]) -> dict[str, float]:
        """Accumulate confidence-weighted targets across several codes.

        Rows marked HORIZONTAL carry no signal for this dimension and are
        dropped — CPV 72 (IT services) is bought by every vertical and must not
        be attributed to one.
        """
        out: dict[str, float] = {}
        for code in codes or []:
            for row in self.lookup(code):
                if row.target == self.HORIZONTAL:
                    continue
                out[row.target] = max(out.get(row.target, 0.0), row.confidence)
        return out


# ---------------------------------------------------------------------------
# Market-sizing crosswalks (§4.3.4, DR-12)
#
# These two are exact-match rather than longest-prefix, because their source
# columns are already controlled-vocabulary ids rather than a hierarchical
# classification scheme. They are kept as CSV, versioned and owned, for the same
# reason as the CPV tables: §4.5.2 warns that every downstream number inherits a
# crosswalk's errors, so it has to be reviewable by someone who is not reading
# Python.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NaceRow:
    """One vertical -> NACE slice: an enterprise-count code and an adoption code."""

    version: str
    vertical: str
    sbs_nace: str
    ict_nace: str
    confidence: float
    owner: str
    note: str = ""


@dataclass(frozen=True)
class AdoptionRow:
    """One technology -> the Eurostat series used as its adoption rate."""

    version: str
    technology: str
    dataset: str
    indicator: str
    proxy: bool
    confidence: float
    owner: str
    note: str = ""


# ---------------------------------------------------------------------------
# Top-level config object
# ---------------------------------------------------------------------------


class Config:
    """Single entry point to every piece of configuration."""

    def __init__(self) -> None:
        self.settings = _load_yaml("settings.yaml")
        self.strategy = _load_yaml("strategy.yaml")
        self.source_tiers = _load_yaml("source_tiers.yaml")
        self.sources = _load_yaml("sources.yaml")
        self.role_modes_raw = _load_yaml("role_modes.yaml")

        self.verticals = Vocabulary("verticals", _load_yaml("taxonomy", "verticals.yaml"))
        self.use_cases = Vocabulary("use_cases", _load_yaml("taxonomy", "use_cases.yaml"))
        self.technologies = Vocabulary("technologies", _load_yaml("taxonomy", "technologies.yaml"))
        self.domains = Vocabulary("domains", _load_yaml("taxonomy", "domains.yaml"))
        self.personas = Vocabulary("personas", _load_yaml("taxonomy", "personas.yaml"))
        self.signal_types = Vocabulary("signal_types", _load_yaml("taxonomy", "signal_types.yaml"))

        # FR-28 / Table 36. The vocabularies above are English, and the relevance
        # gate is built from them, so without this the pipeline collects French,
        # German and Dutch text and then discards it for not containing English
        # words. Kept as its own file rather than as `synonyms_xx` keys on every
        # item so a translator can review one document (§4.5.2's reviewability
        # argument, applied to language rather than to crosswalks).
        self.lexicon = _load_yaml("taxonomy", "lexicon.yaml")

        self.offers = _load_yaml("business_graph", "offers.yaml")
        self.references = _load_yaml("business_graph", "references.yaml")
        self.assets = _load_yaml("business_graph", "assets.yaml")
        self.competitors_raw = _load_yaml("business_graph", "competitors.yaml")

        self.cpv_to_vertical = Crosswalk(
            "cpv_to_vertical", _load_csv("crosswalks", "cpv_to_vertical.csv"), "cpv_prefix", "vertical"
        )
        self.cpv_to_use_case = Crosswalk(
            "cpv_to_use_case", _load_csv("crosswalks", "cpv_to_use_case.csv"), "cpv_prefix", "use_case"
        )

        # §4.3.4 market sizing. Kept beside the other crosswalks because it is
        # the same kind of object and carries the same risk (§4.5.2).
        self.sizing = _load_yaml("sizing.yaml")
        # Planning economics (the Planner). Optional: the radar runs without it,
        # and only the Planner requires it — so a deployment that never plans is
        # not forced to carry an assumption set nobody owns.
        try:
            self.economics = _load_yaml("economics.yaml")
        except FileNotFoundError:
            self.economics = {}
        self.vertical_to_nace: dict[str, list[NaceRow]] = {}
        for row in _load_csv("crosswalks", "vertical_to_nace.csv"):
            entry = NaceRow(
                version=row.get("version", "unversioned"),
                vertical=row["vertical"].strip(),
                sbs_nace=row["sbs_nace"].strip(),
                ict_nace=row["ict_nace"].strip(),
                confidence=float(row.get("confidence", 1.0)),
                owner=row.get("owner", "unowned"),
                note=row.get("note", ""),
            )
            self.vertical_to_nace.setdefault(entry.vertical, []).append(entry)
        self.technology_to_adoption: dict[str, AdoptionRow] = {}
        for row in _load_csv("crosswalks", "technology_to_adoption.csv"):
            entry = AdoptionRow(
                version=row.get("version", "unversioned"),
                technology=row["technology"].strip(),
                dataset=row["dataset"].strip(),
                indicator=row["indicator"].strip(),
                proxy=str(row.get("proxy", "no")).strip().lower() in ("yes", "true", "1"),
                confidence=float(row.get("confidence", 1.0)),
                owner=row.get("owner", "unowned"),
                note=row.get("note", ""),
            )
            self.technology_to_adoption[entry.technology] = entry

        self._validate()

    # -- environment -------------------------------------------------------

    @property
    def db_path(self) -> Path:
        return PROJECT_ROOT / os.getenv("RADAR_DB_PATH", "data/radar.db")

    @property
    def archive_dir(self) -> Path:
        return PROJECT_ROOT / os.getenv("RADAR_ARCHIVE_DIR", "data/archive")

    @property
    def contact_email(self) -> str:
        return os.getenv("RADAR_CONTACT_EMAIL", "unknown@example.com")

    @property
    def user_agent(self) -> str:
        base = self.settings["ingestion"]["user_agent"]
        return f"{base} <{self.contact_email}>"

    # -- convenience accessors --------------------------------------------

    @property
    def weight_set(self) -> str:
        return self.settings["weight_set"]

    @property
    def competitor_version(self) -> str:
        return self.competitors_raw["version"]

    @property
    def economics_version(self) -> str:
        """SC-10's rule applied to plans: a projection records the bands that made it.

        Two plans built under different `economics.yaml` versions are not
        comparable — the margin bands alone move five-year profit by about 1.66x
        — so the version travels on every plan row and the interface refuses to
        chart across a boundary silently.
        """
        return self.economics.get("economics_version", "unversioned")

    @property
    def sizing_version(self) -> str:
        """SC-10's rule, applied to sizes: a size records the assumptions that made it.

        Two sizes computed under different `sizing.yaml` versions are no more
        comparable than two scores across a weight-set boundary, so the version
        travels on every stored row.
        """
        return self.sizing["version"]

    @property
    def pipeline_version(self) -> str:
        return self.settings["pipeline_version"]

    @property
    def attractiveness_weights(self) -> dict[str, float]:
        return self.settings["attractiveness_weights"]

    @property
    def right_to_win_weights(self) -> dict[str, float]:
        return self.settings["right_to_win_weights"]

    def role_mode(self, role: str) -> dict[str, Any]:
        for mode in self.role_modes_raw["modes"]:
            if mode["id"] == role:
                return mode
        raise KeyError(f"Unknown role mode: {role!r}. Known: {[m['id'] for m in self.role_modes_raw['modes']]}")

    @property
    def role_ids(self) -> list[str]:
        return [m["id"] for m in self.role_modes_raw["modes"]]

    def enabled_sources(self) -> list[dict[str, Any]]:
        return [s for s in self.sources["sources"] if s.get("enabled")]

    @property
    def lexicon_languages(self) -> list[str]:
        return list(self.lexicon.get("languages") or [])

    def lexicon_terms(self, languages: list[str] | None = None) -> set[str]:
        """Every non-English gate term, optionally restricted to some languages.

        Returned flat rather than per-language because the gate does not know an
        item's language when it scores it — detection runs at stage 2 and is
        itself unreliable on short titles (the first corpus recorded languages
        `ge` and `ng`). Matching against the union is the honest behaviour: a
        French term appearing in an English article is still a vocabulary hit.
        """
        wanted = set(languages) if languages else None
        terms: set[str] = set()
        for per_language in self.lexicon.get("terms", {}).values():
            for language, values in (per_language or {}).items():
                if wanted is None or language in wanted:
                    terms.update(str(v).lower() for v in values or ())
        for language, values in (self.lexicon.get("general") or {}).items():
            if wanted is None or language in wanted:
                terms.update(str(v).lower() for v in values or ())
        return terms

    def tier_weight(self, tier: int) -> float:
        return float(self.source_tiers["tiers"][tier]["weight"])

    def vertical_for_story_label(self, label: str) -> dict[str, float]:
        """Reconcile the 12 customer-story industry labels onto the 15 verticals (LK-03)."""
        recon = self.verticals.raw.get("story_label_reconciliation", {})
        if label in recon:
            return dict(recon[label].get("apportion", {}))
        for item in self.verticals:
            if label in (item.get("story_labels") or []):
                return {item.id: 1.0}
        return {}

    # -- validation --------------------------------------------------------

    def _validate(self) -> None:
        """Fail loudly at load time if a vocabulary references an unknown id.

        A crosswalk or business-graph entry pointing at a vocabulary value that
        no longer exists is exactly the silent-propagation failure §4.5.2 warns
        about, so it is a startup error rather than a runtime surprise.
        """
        problems: list[str] = []

        def check(values, vocab: Vocabulary, where: str) -> None:
            for value in values or []:
                if value not in vocab:
                    problems.append(f"{where}: unknown {vocab.name} id {value!r}")

        for uc in self.use_cases:
            check(uc.get("domains"), self.domains, f"use_cases/{uc.id}.domains")
            check(uc.exclusions, self.use_cases, f"use_cases/{uc.id}.exclusions")
        for tech in self.technologies:
            check(tech.exclusions, self.technologies, f"technologies/{tech.id}.exclusions")
        for dom in self.domains:
            vp_ids = {v["id"] for v in self.domains.raw.get("value_propositions", [])}
            for vp in dom.get("value_propositions") or []:
                if vp not in vp_ids:
                    problems.append(f"domains/{dom.id}: unknown value proposition {vp!r}")
        for persona in self.personas:
            check(persona.get("typical_domains"), self.domains, f"personas/{persona.id}")
        for vert in self.verticals:
            check(vert.exclusions, self.verticals, f"verticals/{vert.id}.exclusions")

        for offer in self.offers.get("offers", []):
            check(offer.get("domains"), self.domains, f"offers/{offer['id']}.domains")
            check(offer.get("addresses_use_cases"), self.use_cases, f"offers/{offer['id']}.use_cases")
            check(offer.get("technologies"), self.technologies, f"offers/{offer['id']}.technologies")
            check(offer.get("verticals"), self.verticals, f"offers/{offer['id']}.verticals")

        offer_ids = {o["id"] for o in self.offers.get("offers", [])}
        for ref in self.references.get("named", []):
            check(ref.get("verticals"), self.verticals, f"references/{ref['id']}.verticals")
            check(ref.get("domains"), self.domains, f"references/{ref['id']}.domains")
            check(ref.get("use_cases"), self.use_cases, f"references/{ref['id']}.use_cases")
            for demo in ref.get("demonstrates") or []:
                if demo not in offer_ids:
                    problems.append(f"references/{ref['id']}: unknown offer {demo!r}")

        for partner in self.assets.get("partners", []):
            check(partner.get("provides_technologies"), self.technologies, f"partners/{partner['id']}")
            check(partner.get("domains"), self.domains, f"partners/{partner['id']}.domains")
            tier = partner.get("tier", "unspecified")
            if tier not in self.assets.get("partner_tier_ranks", {}):
                problems.append(f"partners/{partner['id']}: unranked tier {tier!r}")
        for cert in self.assets.get("certifications", []):
            check(cert.get("required_by_verticals"), self.verticals, f"certifications/{cert['id']}")
        for pos in self.assets.get("analyst_positions", []):
            check(pos.get("technologies"), self.technologies, f"analyst_positions/{pos['id']}")
            check(pos.get("domains"), self.domains, f"analyst_positions/{pos['id']}.domains")
            check(pos.get("use_cases"), self.use_cases, f"analyst_positions/{pos['id']}.use_cases")
        for pool in self.assets.get("capability_pools", []):
            check(pool.get("staffs_domains"), self.domains, f"capability_pools/{pool['id']}")
            check(pool.get("technologies"), self.technologies, f"capability_pools/{pool['id']}.tech")
            check(pool.get("verticals"), self.verticals, f"capability_pools/{pool['id']}.verticals")

        for row in self.cpv_to_vertical.rows:
            if row.target != Crosswalk.HORIZONTAL and row.target not in self.verticals:
                problems.append(f"cpv_to_vertical[{row.source_code}]: unknown vertical {row.target!r}")
        for row in self.cpv_to_use_case.rows:
            if row.target != Crosswalk.HORIZONTAL and row.target not in self.use_cases:
                problems.append(f"cpv_to_use_case[{row.source_code}]: unknown use case {row.target!r}")

        # §4.3.4 sizing crosswalks. A dangling id here would silently drop a
        # vertical out of the denominator or point the adoption rate at a series
        # nobody fetches — both produce a number that looks fine and is wrong.
        for vert_id, rows in self.vertical_to_nace.items():
            if vert_id not in self.verticals:
                problems.append(f"vertical_to_nace: unknown vertical {vert_id!r}")
            for row in rows:
                if not row.sbs_nace or not row.ict_nace:
                    problems.append(f"vertical_to_nace[{vert_id}]: empty NACE code")
        sizing_datasets = self.sizing.get("reference_datasets", {})
        fetched = self.sizing.get("adoption_indicators", {})
        for tech_id, row in self.technology_to_adoption.items():
            if tech_id not in self.technologies:
                problems.append(f"technology_to_adoption: unknown technology {tech_id!r}")
            if row.dataset not in sizing_datasets:
                problems.append(
                    f"technology_to_adoption[{tech_id}]: unknown dataset {row.dataset!r}"
                )
            elif row.indicator not in (fetched.get(row.dataset) or []):
                # The fetcher pulls exactly `adoption_indicators`; an indicator
                # outside that list would never be in the reference store.
                problems.append(
                    f"technology_to_adoption[{tech_id}]: indicator {row.indicator!r} is not in "
                    f"sizing.yaml adoption_indicators[{row.dataset}]"
                )
        for domain_id in self.sizing["contract_value"].get("fallback_bands_eur", {}):
            if domain_id not in self.domains:
                problems.append(f"sizing/fallback_bands_eur: unknown domain {domain_id!r}")
        distance_keys = set(self.sizing["obtainable_share"]["by_portfolio_distance"])
        if distance_keys != {"L0", "L1", "L2", "L3", "L4"}:
            problems.append(
                f"sizing/obtainable_share.by_portfolio_distance must cover L0-L4, got {sorted(distance_keys)}"
            )

        # Competitor register (§4.3.3). Same treatment as the rest of the
        # business graph: a dangling technology id would silently drop a
        # competitor out of every topic it actually competes in.
        type_ids = set(self.competitors_raw.get("types", {}))
        partner_ids = {p["id"] for p in self.assets.get("partners", [])}
        for entry in self.competitors_raw.get("competitors", []):
            where = f"competitors/{entry['id']}"
            check(entry.get("technologies"), self.technologies, f"{where}.technologies")
            check(entry.get("domains"), self.domains, f"{where}.domains")
            check(entry.get("verticals"), self.verticals, f"{where}.verticals")
            if entry.get("type") not in type_ids:
                problems.append(f"{where}: unknown competitor type {entry.get('type')!r}")
            if entry.get("relationship") not in ("competitor", "partner", "both"):
                problems.append(f"{where}: relationship must be competitor|partner|both")
            if entry.get("partner_id") and entry["partner_id"] not in partner_ids:
                problems.append(f"{where}: unknown partner {entry['partner_id']!r}")
            if not entry.get("aliases"):
                problems.append(f"{where}: no aliases, so no evidence can ever match it")

        # The lexicon keys the vocabularies by id, so a renamed use case would
        # silently take its whole non-English term set out of the gate.
        known_ids = (
            set(self.use_cases.ids) | set(self.technologies.ids)
            | set(self.verticals.ids) | set(self.domains.ids)
        )
        declared_languages = set(self.lexicon.get("languages") or [])
        if not declared_languages:
            problems.append("lexicon: no languages declared")
        for vocab_id, per_language in (self.lexicon.get("terms") or {}).items():
            if vocab_id not in known_ids:
                problems.append(f"lexicon/terms: unknown vocabulary id {vocab_id!r}")
            for language in (per_language or {}):
                if language not in declared_languages:
                    problems.append(
                        f"lexicon/terms/{vocab_id}: language {language!r} is not in `languages`"
                    )
        for language in (self.lexicon.get("general") or {}):
            if language not in declared_languages:
                problems.append(f"lexicon/general: language {language!r} is not in `languages`")

        for vert_id in self.strategy.get("privileged_verticals", {}):
            if vert_id not in self.verticals:
                problems.append(f"strategy/privileged_verticals: unknown vertical {vert_id!r}")

        for mode in self.role_modes_raw["modes"]:
            for link_type in mode.get("link_types", []):
                if link_type not in {"L0", "L1", "L2", "L3", "L4"}:
                    problems.append(f"role_modes/{mode['id']}: unknown link type {link_type!r}")

        weight_sum = sum(self.attractiveness_weights.values())
        if abs(weight_sum - 1.0) > 1e-6:
            problems.append(f"attractiveness_weights sum to {weight_sum}, expected 1.0")
        rtw_sum = sum(self.right_to_win_weights.values())
        if abs(rtw_sum - 1.0) > 1e-6:
            problems.append(f"right_to_win_weights sum to {rtw_sum}, expected 1.0")

        if problems:
            raise ValueError(
                "Configuration validation failed (%d problem(s)):\n  - %s"
                % (len(problems), "\n  - ".join(problems))
            )


@functools.lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()
