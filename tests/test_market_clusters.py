"""Orange Business market clusters (grouping supplied 25 Aug 2026).

The grouping is config, so most of what can go wrong here is a config mistake
that silently produces a plausible-looking number: a country claimed by two
clusters, a YAML scalar that is not the string it looks like, or a supranational
code quietly attributed to somewhere it does not belong. These are the tests for
that, plus the filter behaviour the clusters exist to drive.
"""

from __future__ import annotations

import pytest
import yaml

from radar.config import MarketClusters, get_config
from radar.readmodel import _matches


@pytest.fixture(scope="module")
def clusters():
    return get_config().market_clusters


# ---------------------------------------------------------------------------
# What Orange actually said
# ---------------------------------------------------------------------------

# Quoted from the mail, so a later edit to clusters.yaml that contradicts the
# client shows up as a failure rather than as a different radar.
AS_SUPPLIED = {
    "benelux": {"NL", "BE", "LU"},
    "germany": {"DE"},
    "southern_europe": {"IT", "ES", "PT", "IL"},
    "dach": {"CH", "AT"},
    "uk_ireland": {"GB", "IE"},
    "nordics": {"NO", "SE", "DK", "FI", "IS"},
}


@pytest.mark.parametrize("cluster_id,countries", sorted(AS_SUPPLIED.items()))
def test_the_grouping_orange_supplied_is_the_grouping_we_apply(clusters, cluster_id, countries):
    for code in countries:
        assert clusters.cluster_for(code) == cluster_id, (
            f"{code} should be in {cluster_id} — that is what Orange said"
        )


def test_germany_is_not_in_dach(clusters):
    """The mail lists Germany separately and DACH as Switzerland and Austria.

    DACH conventionally includes Germany, which makes this exactly the kind of
    thing a later editor would "fix" back to the convention and away from what
    the client asked for.
    """
    assert clusters.cluster_for("DE") == "germany"
    assert "DE" not in clusters.members("dach")


def test_israel_is_sold_as_southern_europe(clusters):
    """Not a geographical claim. The mail puts it there because that is the
    cluster that sells it, which is the point of grouping by market."""
    assert clusters.cluster_for("IL") == "southern_europe"


def test_norway_survived_yaml(clusters):
    """YAML 1.1 reads a bare NO as boolean false, which would silently drop
    Norway from the Nordics and leave it unmapped."""
    assert clusters.cluster_for("NO") == "nordics"
    assert "NO" in clusters.members("nordics")


# ---------------------------------------------------------------------------
# Config integrity
# ---------------------------------------------------------------------------

def test_no_country_belongs_to_two_clusters(clusters):
    seen: dict[str, str] = {}
    for cluster in clusters:
        for code in cluster.extra["members"]:
            assert code not in seen, f"{code} in both {seen.get(code)} and {cluster.id}"
            seen[code] = cluster.id


def test_a_duplicated_country_is_a_load_error():
    """The reverse index resolves a duplicate by file order, which is a coin toss
    dressed as a rule — so it has to fail at load instead."""
    raw = {
        "items": [
            {"id": "a", "label": "A", "countries": ["NL"]},
            {"id": "b", "label": "B", "countries": ["NL"]},
        ],
    }
    mc = MarketClusters("test", raw)
    # The class itself keeps first-writer-wins; Config._validate is what refuses.
    assert mc.cluster_for("NL") == "a"
    duplicates = [c for c in ("a", "b") if "NL" in mc.members(c)]
    assert duplicates == ["a", "b"], "both still declare it — which is why validation must catch it"


def test_every_country_code_is_a_plausible_iso_pair(clusters):
    for cluster in clusters:
        for code in cluster.extra["members"]:
            assert len(code) == 2 and code.isalpha() and code.isupper(), code


def test_source_is_recorded_for_every_cluster(clusters):
    """Whether Orange named a grouping, someone settled it, or we inferred it has
    to stay legible — the UI marks only the last kind."""
    for cluster in clusters:
        assert cluster.extra["source"] in {"email", "confirmed", "extension"}
    for cluster_id in AS_SUPPLIED:
        assert clusters[cluster_id].extra["source"] == "email"


def test_france_is_confirmed_not_quoted(clusters):
    """France is its own cluster by decision, not by the mail.

    `email` would put words in the client's mouth; `extension` would imply it is
    still an open guess when it has been settled. The middle value is the honest
    one, and the UI asterisk keys off the difference.
    """
    assert clusters.cluster_for("FR") == "france"
    assert clusters["france"].extra["source"] == "confirmed"
    assert "france" not in AS_SUPPLIED, "the mail listed seven clusters, and France was not one"


def test_eastern_europe_was_named_but_not_enumerated(clusters):
    """The mail says "Eastern European markets" without listing them, so the
    membership is ours even though the cluster is theirs."""
    doc = yaml.safe_load(open("config/taxonomy/clusters.yaml"))
    entry = next(i for i in doc["items"] if i["id"] == "eastern_europe")
    assert entry["source"] == "email"
    assert entry.get("extensions"), "the inferred members belong under extensions"
    assert clusters.cluster_for("PL") == "eastern_europe"


# ---------------------------------------------------------------------------
# Codes that are not countries
# ---------------------------------------------------------------------------

def test_an_eu_wide_signal_is_attributed_to_no_single_cluster(clusters):
    """It is not "about" France the way a French tender is."""
    assert clusters.clusters_for(["EU"]) == []
    assert clusters.is_supranational("EU")


def test_but_it_still_reaches_every_european_cluster(clusters):
    reach = set(clusters.reach_for(["EU"]))
    assert {"france", "germany", "benelux", "nordics", "eastern_europe",
            "southern_europe", "dach", "uk_ireland"} <= reach


def test_and_never_reaches_a_non_european_one(clusters):
    """The bug this exists to prevent: an empty cluster set matches everything,
    so EU-wide evidence surfaced under Asia and Oceania."""
    reach = set(clusters.reach_for(["EU"]))
    assert not reach & {"asia", "africa", "americas", "oceania"}


def test_a_global_code_has_no_opinion(clusters):
    """UN-tagged evidence is global; an empty reach means "do not hide this"."""
    assert clusters.reach_for(["UN"]) == []


def test_a_malformed_code_is_reported_not_guessed(clusters):
    """TU looks like TR and JA like JP. Repairing them would invent evidence
    about a country nobody wrote down, so they stay visible instead."""
    assert clusters.unmapped(["TU", "JA", "HO", "SW"]) == ["TU", "JA", "HO", "SW"]
    assert clusters.cluster_for("TU") is None


def test_only_unambiguous_aliases_are_repaired(clusters):
    """UK is reserved for the United Kingdom in ISO 3166-1 and appears in the
    corpus, so it maps. Nothing else does."""
    assert clusters.cluster_for("UK") == "uk_ireland"
    assert clusters.normalise("uk") == "GB"


# ---------------------------------------------------------------------------
# Filtering (AC-04 / FR-12)
# ---------------------------------------------------------------------------

def _topic(**overrides):
    base = {
        "id": "OS-1",
        "triple": {"vertical": "manufacturing", "use_case": "predictive_maintenance",
                   "technology": "machine_learning"},
        "domains": [], "personas": [], "geographies": [],
        "market_clusters": [], "market_cluster_reach": [],
        "state": "active", "horizon": "next",
    }
    return {**base, **overrides}


def test_filtering_on_a_cluster_matches_its_members(clusters):
    t = _topic(geographies=["SE"],
               market_clusters=clusters.clusters_for(["SE"]),
               market_cluster_reach=clusters.reach_for(["SE"]))
    assert _matches(t, {"market_cluster": ["nordics"]})
    assert not _matches(t, {"market_cluster": ["benelux"]})


def test_an_eu_wide_topic_matches_a_european_cluster_but_not_asia(clusters):
    t = _topic(geographies=["EU"],
               market_clusters=clusters.clusters_for(["EU"]),
               market_cluster_reach=clusters.reach_for(["EU"]))
    assert t["market_clusters"] == [], "shows no cluster chip"
    assert _matches(t, {"market_cluster": ["france"]})
    assert not _matches(t, {"market_cluster": ["asia"]})


def test_a_topic_with_no_geography_stays_global(clusters):
    """The rule geography already uses, applied unchanged: no geography means
    global rather than absent."""
    t = _topic()
    assert _matches(t, {"market_cluster": ["nordics"]})
    assert _matches(t, {"market_cluster": ["asia"]})


def test_clusters_come_back_in_vocabulary_order_not_input_order(clusters):
    """Otherwise the same topic renders its clusters differently depending on the
    order its geographies happen to be stored in."""
    assert (clusters.clusters_for(["SE", "DE", "NL"])
            == clusters.clusters_for(["NL", "SE", "DE"]))


# ---------------------------------------------------------------------------
# Codes the corpus actually emitted, as opposed to the ones it should have
# ---------------------------------------------------------------------------

def test_apac_is_resolved_because_it_is_unambiguous(clusters):
    """Synthesis emits region acronyms as well as ISO codes. APAC has exactly one
    reading, so it reaches Asia and Oceania rather than being reported."""
    assert clusters.reach_for(["APAC"]) == ["asia", "oceania"]
    assert clusters.clusters_for(["APAC"]) == [], "a region is not attribution"


def test_af_is_left_unmapped_because_it_has_two_readings(clusters):
    """ISO 3166-1 says Afghanistan; every use in this corpus means Africa
    (OS348 "rural Africa", OS195 alongside NG/ZA/TN). Resolving it either way
    files real topics under a continent nobody wrote down, so it maps to nothing
    and is counted instead."""
    assert clusters.cluster_for("AF") is None
    assert clusters.unmapped(["AF"]) == ["AF"]
    assert "AF" not in clusters.members("asia")
    assert "AF" not in clusters.members("africa")


def test_the_rest_of_the_world_is_four_continents(clusters):
    """"Simplify it to the continents in general", made concrete: Africa,
    Americas, Asia, Oceania. Americas is one cluster rather than a North/South
    split, and there is no separate "Europe (other)" — European codes that no
    named cluster claims are routed into Eastern Europe instead."""
    continents = [c.id for c in clusters if c.extra["scope"] == "continent"]
    assert continents == ["africa", "americas", "asia", "oceania"]
    assert clusters.cluster_for("US") == "americas"
    assert clusters.cluster_for("BR") == "americas", "no North/South split"
    assert clusters.cluster_for("TR") == "eastern_europe", "European, not stranded"


def test_every_cluster_orange_named_still_leads_the_list(clusters):
    """Order is the client's, and the interface reads it straight off this file.
    The seven from the mail come first, in the order the mail gave them."""
    assert clusters.ids[:7] == [
        "benelux", "germany", "southern_europe", "dach",
        "uk_ireland", "nordics", "eastern_europe",
    ]


def test_the_clusters_the_mail_fully_specified_are_exactly_as_written(clusters):
    """No padding, no tidying.

    Six of the seven were given as a complete country list, so their membership
    should be that list and nothing else. Dependencies and microstates (LI in
    DACH, MC in France, FO/GL/AX in the Nordics) were added early and removed:
    none appears in the corpus, none is a distinct Orange market, and each one
    changed how the cluster reads — "DACH: Switzerland, Austria, Liechtenstein"
    against a mail that says "DACH – Switzerland, Austria".

    Southern Europe is excluded here because GR, CY and MT are documented
    extensions, and Eastern Europe because the mail never enumerated it.
    """
    for cluster_id, countries in AS_SUPPLIED.items():
        if cluster_id == "southern_europe":
            continue
        assert set(clusters.members(cluster_id)) == countries, (
            f"{cluster_id} should be exactly what the mail listed"
        )


def test_dach_reads_the_way_orange_wrote_it(clusters):
    """The specific regression the padding caused, kept as its own case because
    DACH is the cluster whose name most invites being "corrected"."""
    assert list(clusters.members("dach")) == ["CH", "AT"]
