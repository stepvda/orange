import {
  IconBuilding, IconClock, IconDoc, IconGlobe, IconLayers, IconPerson, IconSearch, IconVenn,
} from './Icons'
import type { FilterState, MarketCluster, Meta } from '../types'
import { countryNames } from '../geo'
import { EMPTY_FILTERS } from '../types'

/** AC-04 / FR-12: multi-select on at least vertical, geography, domain and
 * persona, plus free-text search over statements and signals (§4.9) — and, since
 * §4.3.3 and §4.3.4 gave every space a competitive intensity and a market size,
 * those too. A fact the radar computes and displays but cannot filter on is a
 * fact a strategist has to eyeball across 148 rows.
 *
 * Counts come from the SERVER, over every topic the role can see, not from the
 * capped page: a rail that showed "CISO 0" because none of the 24 visible rows
 * carried that persona — while 37 matched — trained people not to trust it.
 */

interface Props {
  meta: Meta
  /** True while the view request is in flight — "none matched" and "not here
   *  yet" are opposite messages and must not share a rendering. */
  loading?: boolean
  filters: FilterState
  onChange: (next: FilterState) => void
  geographies: string[]
  /** Only the clusters present in the current result set, in vocabulary order. */
  marketClusters: MarketCluster[]
  /** Server-computed facet counts for the current role and result set. */
  facets: Record<string, Record<string, number>>
  totalMatching: number
}

function MultiSelect({
  title, items, selected, onToggle, counts, hint, icon: Icon,
}: {
  title: string
  items: { id: string; label: string; sub?: string; title?: string }[]
  selected: string[]
  onToggle: (id: string) => void
  counts?: Record<string, number>
  hint?: string
  /** Decoration for the group heading. The heading is the accessible name —
   *  the icon is `aria-hidden` and never the only thing that says what this is. */
  icon?: (props: { className?: string }) => JSX.Element
}) {
  // A value that matches nothing is still shown, greyed, rather than hidden:
  // "there are none of these" is information, and a list that silently changes
  // length as you filter is disorienting.
  return (
    <div className="filter-group">
      <h3 title={hint}>
        {Icon && <Icon />}
        {title}{selected.length > 0 && ` · ${selected.length}`}
      </h3>
      <div className="filter-list">
        {items.map((item) => {
          // An explicit 0 rather than a blank: a missing count reads as "this
          // filter is broken", where "0" reads as "none of these right now".
          const count = counts === undefined ? undefined : (counts[item.id] ?? 0)
          const empty = count === 0 && !selected.includes(item.id)
          return (
            <label className={`filter-item${empty ? ' filter-item-zero' : ''}`} key={item.id}
                   title={item.title ?? (count === undefined ? item.label : `${item.label} — ${count} space${count === 1 ? '' : 's'}`)}>
              <input
                type="checkbox"
                checked={selected.includes(item.id)}
                onChange={() => onToggle(item.id)}
              />
              {/* An acronym that is never expanded is a name only the people who
                  chose it can read, so the cluster rows carry their membership.
                  They are the one dimension that gets two lines — every other
                  filter stays on one, which is why this is opt-in per item
                  rather than a change to the row itself. */}
              <span className={item.sub ? 'stacked' : undefined}>
                {item.label}
                {item.sub && <span className="filter-item-sub">{item.sub}</span>}
              </span>
              {count !== undefined && <span className="filter-count">{count}</span>}
            </label>
          )
        })}
      </div>
    </div>
  )
}

export default function Filters({ meta, filters, onChange, geographies, marketClusters, facets, totalMatching, loading }: Props) {
  const toggle = (key: keyof FilterState) => (id: string) => {
    const current = filters[key] as string[]
    onChange({
      ...filters,
      [key]: current.includes(id) ? current.filter((v) => v !== id) : [...current, id],
    })
  }

  /* Ticking a cluster ticks the countries in it, and unticking releases them.
   *
   * A cluster IS its countries, so the rail should say so rather than leaving
   * the reader to work out which five codes "Nordics" stands for. Two rules keep
   * it from fighting the reader:
   *
   *  - every member is ticked, not just the ones on screen. Selections within
   *    the country dimension are a union, so a member the corpus has no evidence
   *    for narrows nothing; and the country rail lists whatever is selected, so
   *    they are visible rather than active-but-hidden.
   *  - a country claimed by another still-selected cluster survives unticking,
   *    so turning Benelux off does not silently drop the Netherlands out of a
   *    selection some other cluster is still holding.
   *
   * Countries stay independently toggleable afterwards: this seeds the selection,
   * it does not own it.
   */
  const membersOf = (id: string) =>
    marketClusters.find((c) => c.id === id)?.countries ?? []

  const toggleCluster = (id: string) => {
    const removing = filters.market_cluster.includes(id)
    const market_cluster = removing
      ? filters.market_cluster.filter((c) => c !== id)
      : [...filters.market_cluster, id]
    const members = membersOf(id)
    const geography = removing
      ? filters.geography.filter(
          (g) => !members.includes(g) || market_cluster.some((c) => membersOf(c).includes(g)),
        )
      : [...new Set([...filters.geography, ...members])]
    onChange({ ...filters, market_cluster, geography })
  }

  const active =
    filters.vertical.length + filters.domain.length + filters.persona.length +
    filters.geography.length + filters.market_cluster.length + filters.horizon.length + filters.competition.length +
    (filters.has_brief ? 1 : 0) + (filters.q ? 1 : 0)

  return (
    <>
      <div className="filter-group">
        <h3><IconSearch />Search</h3>
        <input
          className="search-input"
          type="search"
          placeholder="Statements and claims…"
          value={filters.q}
          onChange={(e) => onChange({ ...filters, q: e.target.value })}
        />
      </div>

      <div className="filter-summary" aria-live="polite">
        {loading ? 'Counting…' : `${totalMatching} space${totalMatching === 1 ? '' : 's'} match this role and filter`}
      </div>

      {active > 0 && (
        <button style={{ width: '100%', marginBottom: 16 }} onClick={() => onChange({ ...EMPTY_FILTERS })}>
          Clear {active} filter{active === 1 ? '' : 's'}
        </button>
      )}

      <MultiSelect
        title="Horizon"
        icon={IconClock}
        items={meta.horizons.map((h) => ({ id: h, label: h.toUpperCase() }))}
        selected={filters.horizon}
        onToggle={toggle('horizon')}
        counts={facets.horizon}
      />
      <MultiSelect
        title="Competition"
        icon={IconVenn}
        hint="How crowded the field is (§4.3.3) — named competitors, scored"
        items={(meta.competition_levels ?? [{ id: 'none' }, { id: 'low' }, { id: 'medium' }, { id: 'high' }])
          .map((level) => ({ id: level.id, label: level.id.toUpperCase() }))}
        selected={filters.competition}
        onToggle={toggle('competition')}
        counts={facets.competition}
      />

      <div className="filter-group">
        <h3><IconDoc />Ready to sell</h3>
        <label className="filter-item">
          <input type="checkbox" checked={filters.has_brief}
                 onChange={() => onChange({ ...filters, has_brief: !filters.has_brief })} />
          <span>Has a sales brief</span>
          <span className="filter-count">{facets.with_brief?.true ?? 0}</span>
        </label>
      </div>

      <MultiSelect
        title="Vertical"
        icon={IconBuilding}
        items={meta.verticals}
        selected={filters.vertical}
        onToggle={toggle('vertical')}
        counts={facets.vertical}
      />
      <MultiSelect
        title="Domain"
        icon={IconLayers}
        items={meta.domains}
        selected={filters.domain}
        onToggle={toggle('domain')}
        counts={facets.domain}
      />
      <MultiSelect
        title="Persona"
        icon={IconPerson}
        items={meta.personas}
        selected={filters.persona}
        onToggle={toggle('persona')}
        counts={facets.persona}
      />
      {marketClusters.length > 0 && (
        <MultiSelect
          title="Market cluster"
          icon={IconGlobe}
          hint="Orange Business go-to-market grouping. EU-wide evidence counts towards every European cluster."
          items={marketClusters.map((c) => {
            const names = countryNames(c.countries)
            return {
              id: c.id,
              // Only the groupings that are still nobody's decision are marked.
              // Orange named most of them; France was settled separately. What is
              // left with an asterisk is our own reading of the corpus.
              label: c.source === 'extension' ? `${c.label} *` : c.label,
              sub: names.short,
              title: `${c.label} — ${names.full}`,
            }
          })}
          selected={filters.market_cluster}
          onToggle={toggleCluster}
          counts={facets.market_cluster}
        />
      )}
      {geographies.length > 0 && (
        <MultiSelect
          title="Country"
          icon={IconGlobe}
          items={geographies.map((g) => ({ id: g, label: g }))}
          selected={filters.geography}
          onToggle={toggle('geography')}
          counts={facets.geography}
        />
      )}
    </>
  )
}
