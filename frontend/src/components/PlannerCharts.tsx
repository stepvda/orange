import type { Plan } from '../types'

/** Charts for the Planner, drawn as inline SVG.
 *
 * No chart library, for the same reason the radar has none: these encodings are
 * specific to this product, and each one is chosen by the job its data does
 * rather than by what looked good.
 *
 *   revenue and profit    magnitude over time, split by cohort -> stacked area,
 *                         sequential ramp so the reading order IS the entry order
 *   entry timeline        position in a sequence -> ordinal bars on a time axis
 *   capacity utilisation  a bounded ratio against a ceiling -> bars with a limit
 *                         line, because the ceiling is the point
 *   portfolio mix         parts of a whole against a target -> bar with a marker
 *   uncertainty band      a range, not a value -> band with the base case inside
 *   waterfall             where the market went -> descending steps
 */

const EUR = (v: number) => {
  const m = v / 1e6
  if (Math.abs(m) >= 1000) return `€${(m / 1000).toFixed(1)}bn`
  if (Math.abs(m) >= 10) return `€${Math.round(m)}m`
  return `€${m.toFixed(1)}m`
}

const COHORT = { now: 'var(--chart-seq-4)', next: 'var(--chart-seq-3)', later: 'var(--chart-seq-2)' }

function Frame({ title, note, height = 190, children }: {
  title: string; note?: string; height?: number; children: React.ReactNode
}) {
  return (
    <figure className="pl-chart">
      <figcaption>
        <span className="pl-chart-title">{title}</span>
        {note && <span className="pl-chart-note">{note}</span>}
      </figcaption>
      <div style={{ height }}>{children}</div>
    </figure>
  )
}

/** 1 · Revenue and profit by year, stacked by the horizon cohort each space came from. */
export function RevenueProfitChart({ plan }: { plan: Plan }) {
  const p = plan.projection
  const years = p.revenue_by_year.length
  const W = 460, H = 190, padL = 52, padB = 26, padT = 12
  const max = Math.max(...p.revenue_by_year, 1)
  const x = (i: number) => padL + (i * (W - padL - 10)) / Math.max(years - 1, 1)
  const y = (v: number) => padT + (1 - v / max) * (H - padB - padT)

  const area = (vals: number[]) =>
    `M ${x(0)},${y(0)} ` + vals.map((v, i) => `L ${x(i)},${y(v)}`).join(' ') +
    ` L ${x(years - 1)},${y(0)} Z`

  return (
    <Frame title="Revenue and profit by year"
           note="Profit at the margin band for each space's portfolio distance">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" role="img"
           aria-label="Revenue and profit projected over the plan window">
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={padL} x2={W - 10} y1={y(max * f)} y2={y(max * f)}
                  stroke="var(--border)" strokeWidth={0.6} />
            <text x={padL - 6} y={y(max * f) + 3} textAnchor="end"
                  fontSize={8.5} fill="var(--text-muted)">{EUR(max * f)}</text>
          </g>
        ))}
        <path d={area(p.revenue_by_year)} fill="var(--chart-seq-2)" opacity={0.5} />
        <path d={area(p.profit_by_year)} fill="var(--accent)" opacity={0.85} />
        <polyline points={p.revenue_by_year.map((v, i) => `${x(i)},${y(v)}`).join(' ')}
                  fill="none" stroke="var(--chart-seq-4)" strokeWidth={1.6} />
        {p.revenue_by_year.map((v, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(v)} r={2.4} fill="var(--chart-seq-4)" />
            <text x={x(i)} y={H - 8} textAnchor="middle" fontSize={9}
                  fill="var(--text-muted)">Y{i + 1}</text>
          </g>
        ))}
        <text x={W - 10} y={y(p.revenue_by_year[years - 1]) - 7} textAnchor="end"
              fontSize={9.5} fill="var(--chart-seq-4)" fontWeight={600}>
          revenue {EUR(p.revenue_by_year[years - 1])}
        </text>
        <text x={W - 10} y={y(p.profit_by_year[years - 1]) - 6} textAnchor="end"
              fontSize={9.5} fill="var(--accent-text)" fontWeight={600}>
          profit {EUR(p.profit_by_year[years - 1])}
        </text>
      </svg>
    </Frame>
  )
}

/** 2 · When each space enters, coloured by its horizon cohort. */
export function EntryTimelineChart({ plan }: { plan: Plan }) {
  const years = plan.plan_years
  const byYear: Record<number, typeof plan.selections> = {}
  plan.selections.forEach((s) => { (byYear[s.entry_year] ||= []).push(s) })
  const max = Math.max(...Object.values(byYear).map((v) => v.length), 1)
  const W = 460, H = 190, padL = 34, padB = 26, padT = 12
  const bw = (W - padL - 14) / years

  return (
    <Frame title="Entry schedule"
           note="Staggered by horizon and by what capacity allowed — later cohorts wait">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" role="img"
           aria-label="Number of spaces entering in each year of the plan">
        {Array.from({ length: years }, (_, i) => {
          const yr = i + 1
          const list = byYear[yr] ?? []
          const counts = { now: 0, next: 0, later: 0 } as Record<string, number>
          list.forEach((s) => { counts[s.horizon ?? 'next'] = (counts[s.horizon ?? 'next'] ?? 0) + 1 })
          let acc = 0
          return (
            <g key={yr}>
              {(['now', 'next', 'later'] as const).map((h) => {
                const n = counts[h] ?? 0
                if (!n) return null
                const hgt = (n / max) * (H - padB - padT)
                const yTop = H - padB - ((acc + n) / max) * (H - padB - padT)
                acc += n
                return <rect key={h} x={padL + i * bw + 5} y={yTop} width={bw - 10} height={hgt}
                             fill={COHORT[h]} rx={2} />
              })}
              <text x={padL + i * bw + bw / 2} y={H - 8} textAnchor="middle" fontSize={9}
                    fill="var(--text-muted)">Y{yr}</text>
              <text x={padL + i * bw + bw / 2} y={H - padB - (acc / max) * (H - padB - padT) - 5}
                    textAnchor="middle" fontSize={10} fontWeight={600} fill="var(--text-primary)">
                {acc || ''}
              </text>
            </g>
          )
        })}
        <g transform={`translate(${padL},${padT - 4})`}>
          {(['now', 'next', 'later'] as const).map((h, i) => (
            <g key={h} transform={`translate(${i * 64},0)`}>
              <rect width={8} height={8} y={-7} fill={COHORT[h]} rx={1.5} />
              <text x={11} fontSize={8.5} fill="var(--text-muted)">{h}</text>
            </g>
          ))}
        </g>
      </svg>
    </Frame>
  )
}

/** 3 · Capability pool load against the ceiling. The constraint that actually binds. */
export function CapacityChart({ plan }: { plan: Plan }) {
  const pools = Object.entries(plan.capacity_usage?.pools ?? {})
  if (!pools.length) return null
  const W = 460, rowH = 26, padL = 132
  const H = pools.length * rowH + 22

  return (
    <Frame title="Capability pool utilisation" height={Math.max(H, 120)}
           note="Peak load against the share of headcount available for new work">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" role="img"
           aria-label="Peak utilisation of each capability pool">
        {pools.map(([name, d], i) => {
          const util = Math.min(d.peak_utilisation ?? 0, 1.4)
          const bar = (W - padL - 46) * Math.min(util, 1)
          const over = util > 0.98
          return (
            <g key={name} transform={`translate(0,${i * rowH + 14})`}>
              <text x={padL - 8} y={4} textAnchor="end" fontSize={9}
                    fill="var(--text-secondary)">{name.replace(' experts', '')}</text>
              <rect x={padL} y={-7} width={W - padL - 46} height={13} rx={2}
                    fill="var(--surface-0)" stroke="var(--border)" strokeWidth={0.6} />
              <rect x={padL} y={-7} width={bar} height={13} rx={2}
                    fill={over ? 'var(--status-bad, #a82820)' : 'var(--accent)'} />
              <text x={W - 40} y={4} fontSize={9} fontWeight={over ? 700 : 400}
                    fill={over ? 'var(--status-bad, #a82820)' : 'var(--text-muted)'}>
                {Math.round(util * 100)}%
              </text>
            </g>
          )
        })}
        <line x1={W - 46} x2={W - 46} y1={4} y2={H - 6} stroke="var(--status-bad, #a82820)"
              strokeWidth={1} strokeDasharray="3 2" />
      </svg>
    </Frame>
  )
}

/** 4 · Portfolio mix against the concentration caps. */
export function MixChart({ plan, dimension = 'vertical' }: { plan: Plan; dimension?: string }) {
  const mix = plan.projection.mix?.[dimension] ?? []
  if (!mix.length) return null
  const cap = dimension === 'vertical'
    ? (plan.inputs?.max_share_per_vertical ?? plan.assumptions?.defaults_max_vertical ?? 0.4)
    : null
  const W = 460, rowH = 22, padL = 128
  const H = Math.min(mix.length, 7) * rowH + 20

  return (
    <Frame title={`Portfolio mix by ${dimension}`} height={Math.max(H, 110)}
           note={cap ? `Concentration cap shown as the dashed line` : undefined}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" role="img"
           aria-label={`Share of selected spaces by ${dimension}`}>
        {mix.slice(0, 7).map((m, i) => (
          <g key={m.key} transform={`translate(0,${i * rowH + 14})`}>
            <text x={padL - 8} y={4} textAnchor="end" fontSize={9}
                  fill="var(--text-secondary)">{m.key.replace(/_/g, ' ')}</text>
            <rect x={padL} y={-6} width={(W - padL - 40) * m.share} height={11} rx={2}
                  fill="var(--chart-seq-3)" />
            <text x={W - 34} y={4} fontSize={9} fill="var(--text-muted)">
              {Math.round(m.share * 100)}% · {m.count}
            </text>
          </g>
        ))}
        {cap && (
          <line x1={padL + (W - padL - 40) * cap} x2={padL + (W - padL - 40) * cap}
                y1={4} y2={H - 6} stroke="var(--accent)" strokeWidth={1} strokeDasharray="3 2" />
        )}
      </svg>
    </Frame>
  )
}

/** 5 · Cumulative profit with the band the sizing actually supports. */
export function UncertaintyChart({ plan }: { plan: Plan }) {
  const p = plan.projection
  const years = p.profit_by_year.length
  const cum = (arr: number[]) => arr.reduce<number[]>((a, v, i) => [...a, (a[i - 1] ?? 0) + v], [])
  const base = cum(p.profit_by_year), lo = cum(p.profit_low_by_year), hi = cum(p.profit_high_by_year)
  const W = 460, H = 190, padL = 56, padB = 26, padT = 12
  const max = Math.max(...hi, 1)
  const x = (i: number) => padL + (i * (W - padL - 10)) / Math.max(years - 1, 1)
  const y = (v: number) => padT + (1 - v / max) * (H - padB - padT)

  return (
    <Frame title="Cumulative profit, with its interval"
           note="The band is the sizing engine's own low and high estimates — not error bars">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" role="img"
           aria-label="Cumulative profit with the uncertainty band from the market sizing">
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={padL} x2={W - 10} y1={y(max * f)} y2={y(max * f)}
                  stroke="var(--border)" strokeWidth={0.6} />
            <text x={padL - 6} y={y(max * f) + 3} textAnchor="end" fontSize={8.5}
                  fill="var(--text-muted)">{EUR(max * f)}</text>
          </g>
        ))}
        <path d={`M ${hi.map((v, i) => `${x(i)},${y(v)}`).join(' L ')} L ${lo.slice().reverse()
              .map((v, i) => `${x(years - 1 - i)},${y(v)}`).join(' L ')} Z`}
              fill="var(--accent)" opacity={0.14} />
        <polyline points={base.map((v, i) => `${x(i)},${y(v)}`).join(' ')} fill="none"
                  stroke="var(--accent)" strokeWidth={2} />
        {base.map((_, i) => (
          <text key={i} x={x(i)} y={H - 8} textAnchor="middle" fontSize={9}
                fill="var(--text-muted)">Y{i + 1}</text>
        ))}
        <text x={W - 12} y={y(hi[years - 1]) + 10} textAnchor="end" fontSize={8.5}
              fill="var(--text-muted)">high {EUR(hi[years - 1])}</text>
        <text x={W - 12} y={y(base[years - 1]) - 6} textAnchor="end" fontSize={9.5}
              fontWeight={600} fill="var(--accent-text)">base {EUR(base[years - 1])}</text>
        <text x={W - 12} y={y(lo[years - 1]) - 5} textAnchor="end" fontSize={8.5}
              fill="var(--text-muted)">low {EUR(lo[years - 1])}</text>
      </svg>
    </Frame>
  )
}

/** 6 · Where the addressable market went, from every sized space to what is planned. */
export function FunnelChart({ plan }: { plan: Plan }) {
  const p = plan.projection
  const steps = [
    { label: 'Admissible candidates', value: plan.considered_count, unit: 'spaces' },
    { label: 'Selected by the optimiser', value: plan.selected_count, unit: 'spaces' },
    { label: 'Year-5 revenue', value: p.revenue_by_year[p.revenue_by_year.length - 1], unit: 'eur' },
    { label: 'Year-5 profit', value: p.profit_by_year[p.profit_by_year.length - 1], unit: 'eur' },
  ]
  const W = 460, rowH = 30, H = steps.length * rowH + 12
  const maxSpaces = Math.max(steps[0].value, 1)
  const maxEur = Math.max(steps[2].value, 1)

  return (
    <Frame title="From candidates to committed" height={H + 10}
           note="What the constraints removed, at each step">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" role="img"
           aria-label="Funnel from admissible candidates to projected profit">
        {steps.map((s, i) => {
          const frac = s.unit === 'spaces' ? s.value / maxSpaces : s.value / maxEur
          return (
            <g key={s.label} transform={`translate(0,${i * rowH + 18})`}>
              <rect x={0} y={-11} width={(W - 118) * Math.max(frac, 0.04)} height={17} rx={2.5}
                    fill={i < 2 ? 'var(--chart-seq-3)' : 'var(--accent)'}
                    opacity={i < 2 ? 0.75 : 0.9} />
              <text x={8} y={1} fontSize={9.5} fill="#fff" fontWeight={600}>
                {s.unit === 'spaces' ? s.value : EUR(s.value)}
              </text>
              <text x={W - 112} y={1} fontSize={9} fill="var(--text-secondary)">{s.label}</text>
            </g>
          )
        })}
      </svg>
    </Frame>
  )
}
