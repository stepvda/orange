import { useRef } from 'react'
import { useFocusTrap } from './Help'
import type { Meta } from '../types'
import {
  IconWaves, IconFunnel, IconCluster, IconSpark, IconLink, IconCube, IconGauge,
  IconMoney, IconDoc, IconShield, IconRefresh, IconRadar, IconList,
} from './Icons'

/** "How was the radar created?" — the pipeline, end to end, for the reader.
 *
 * The radar asks to be trusted with a strategic decision, and NFR-02/NFR-03
 * require that "a reviewer outside the project can reconstruct why any topic
 * holds its rank". `ScoreExplain` makes that good for ONE number on ONE topic.
 * This makes it good for the picture as a whole: where the evidence came from,
 * what was thrown away and by which test, which stages are arithmetic, which
 * are retrieval, and the two places a language model is allowed to write.
 *
 * The division of labour is the honest part and it is stated explicitly, because
 * "an AI built this" is the reading a reader will otherwise default to — and it
 * is wrong in a way that damages the product's credibility. Eleven of the
 * thirteen stages never call a model at all.
 *
 * Live figures come from `meta` rather than being written into the prose. A help
 * page that hardcodes "15 verticals" is wrong the first time somebody edits the
 * taxonomy, and a wrong explanation of the method is worse than none.
 */

/* ---------- diagram 1: the thirteen stages, in four phases ---------------- */

const PHASES: { n: string; name: string; asks: string; stages: string[][]; out: string }[] = [
  {
    n: '1', name: 'Evidence', asks: 'what is the world saying?',
    stages: [['collect'], ['classify']],
    out: 'dated, attributed, tiered signals',
  },
  {
    n: '2', name: 'Structure', asks: 'what is the theme?',
    stages: [['themes'], ['synthesise'], ['enrich']],
    out: 'curated opportunity spaces',
  },
  {
    n: '3', name: 'Orange join', asks: 'can we play?',
    stages: [['graph'], ['link']],
    out: 'portfolio distance L0–L4',
  },
  {
    n: '4', name: 'Measure & place', asks: 'how big, how contested?',
    stages: [['score', 'reference'], ['size', 'competition'], ['actions', 'describe']],
    out: 'two scores, a size, a field, an action',
  },
]

const CARD_W = 206
const CARD_GAP = 38
const CARD_Y = 10
const CARD_H = 138

function PhaseDiagram() {
  return (
    <div className="hb-scroll">
      <svg viewBox="0 0 938 200" className="hb-svg" style={{ minWidth: 700 }}
           role="img"
           aria-label="The refresh pipeline in four phases. Phase 1 Evidence — stages collect and classify — produces dated, attributed, tiered signals. Phase 2 Structure — themes, synthesise, enrich — produces curated opportunity spaces. Phase 3 Orange join — graph, link — produces portfolio distance L0 to L4. Phase 4 Measure and place — score, reference, size, competition, actions, describe — produces two scores, a market size, a competitive field and a next action.">
        <defs>
          <marker id="hb-arrow" viewBox="0 0 10 10" refX="8" refY="5"
                  markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0 1.5 8.5 5 0 8.5z" fill="var(--border-strong)" />
          </marker>
        </defs>

        {PHASES.map((phase, i) => {
          const x = i * (CARD_W + CARD_GAP)
          return (
            <g key={phase.n}>
              <rect x={x} y={CARD_Y} width={CARD_W} height={CARD_H} rx={9}
                    fill="var(--surface-2)" stroke="var(--border-strong)" />
              <circle cx={x + 25} cy={CARD_Y + 34} r={12}
                      fill="var(--accent)" opacity={0.14} />
              <circle cx={x + 25} cy={CARD_Y + 34} r={12}
                      fill="none" stroke="var(--accent)" strokeWidth={1.2} />
              <text x={x + 25} y={CARD_Y + 38.5} textAnchor="middle"
                    className="hb-d-badge">{phase.n}</text>
              <text x={x + 46} y={CARD_Y + 31} className="hb-d-title">{phase.name}</text>
              <text x={x + 46} y={CARD_Y + 46} className="hb-d-sub">{phase.asks}</text>
              <line x1={x + 14} y1={CARD_Y + 62} x2={x + CARD_W - 14} y2={CARD_Y + 62}
                    stroke="var(--border)" />
              {/* Centred in the space below the rule rather than top-aligned:
                  the four phases hold two to three lines each, and a common card
                  height with ragged content reads as a rendering accident. */}
              {phase.stages.map((row, r) => (
                <text key={r} x={x + 16} className="hb-d-stage"
                      y={CARD_Y + 104 - ((phase.stages.length - 1) * 18) / 2 + r * 18}>
                  {row.join('  ·  ')}
                </text>
              ))}
              <text x={x + CARD_W / 2} y={CARD_Y + CARD_H + 26} textAnchor="middle"
                    className="hb-d-out">
                {/* Two lines, because "dated, attributed, tiered signals" does
                    not fit a 206px card and shrinking the type to make it fit
                    would make the label the smallest text in the interface. */}
                {phase.out.split(' ').reduce<string[]>((lines, word) => {
                  const last = lines[lines.length - 1]
                  if (last && (last + ' ' + word).length <= 24) lines[lines.length - 1] = last + ' ' + word
                  else lines.push(word)
                  return lines
                }, []).map((line, li) => (
                  <tspan key={li} x={x + CARD_W / 2} dy={li === 0 ? 0 : 13}>{line}</tspan>
                ))}
              </text>
              {i < PHASES.length - 1 && (
                <line x1={x + CARD_W + 9} y1={CARD_Y + CARD_H / 2}
                      x2={x + CARD_W + CARD_GAP - 9} y2={CARD_Y + CARD_H / 2}
                      stroke="var(--border-strong)" strokeWidth={1.4}
                      markerEnd="url(#hb-arrow)" />
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

/* ---------- diagram 2: what each gate throws away ------------------------ */

const FUNNEL: { label: string; note: string; w: number; fill: string; dashed?: boolean }[] = [
  { label: 'Raw items fetched', note: 'stored verbatim, with URL, publisher and date', w: 400, fill: 'var(--ord-1)' },
  { label: 'Signal records', note: 'one row per distinct story, not per outlet', w: 322, fill: 'var(--ord-2)' },
  { label: 'Relevant signals', note: 'typed, and tiered 1–4 by publisher', w: 236, fill: 'var(--ord-3)' },
  { label: 'Theme clusters', note: 'groups of ≥ 3 semantically close signals', w: 140, fill: 'var(--ord-4)' },
  { label: 'Candidate spaces', note: 'the only stage that WIDENS — on purpose', w: 210, fill: 'var(--ord-2)', dashed: true },
  { label: 'Topics on the radar', note: 'what survived every test above', w: 104, fill: 'var(--accent)' },
]

const GATES = [
  'content hash · language · date · geography',
  'keyword pre-filter, then a small model at temperature 0',
  'agglomerative clustering · cosine 0.58 · min size 3',
  '3 candidates per cluster at temperature 0.85',
  'critic ≥ 3/5 · evidence binding · closed vocabulary · entailment',
]

const ROW_H = 56
const BAR_H = 28
// The left gutter has to hold the longest note ("stored verbatim, with URL,
// publisher and date"), not just the longest label — anything narrower clips it
// against the viewBox edge, and an SVG has no overflow to catch it.
const LABEL_X = 262
const BAR_X = 280

function FunnelDiagram() {
  return (
    <div className="hb-scroll">
      <svg viewBox={`0 0 820 ${14 + (FUNNEL.length - 1) * ROW_H + BAR_H}`} className="hb-svg"
           style={{ minWidth: 680 }} role="img"
           aria-label={FUNNEL.map((f, i) => `${f.label}: ${f.note}.${GATES[i] ? ` Next gate: ${GATES[i]}.` : ''}`).join(' ')}>
        {FUNNEL.map((row, i) => {
          const y = 8 + i * ROW_H
          return (
            <g key={row.label}>
              <text x={LABEL_X} y={y + 14} textAnchor="end" className="hb-f-label">{row.label}</text>
              <text x={LABEL_X} y={y + 26} textAnchor="end" className="hb-f-note">{row.note}</text>
              {/* The provisional bar is washed out on FILL only. `opacity` would
                  take the dashed outline with it, and on the dark surface that
                  leaves the one bar the section is about barely visible. */}
              <rect x={BAR_X} y={y} width={row.w} height={BAR_H} rx={4}
                    fill={row.fill} fillOpacity={row.dashed ? 0.3 : 1}
                    stroke={row.dashed ? row.fill : 'none'}
                    strokeWidth={row.dashed ? 1.4 : 0}
                    strokeDasharray={row.dashed ? '4 3' : undefined} />
              {GATES[i] && (
                <>
                  <line x1={BAR_X + 12} y1={y + BAR_H + 3} x2={BAR_X + 12} y2={y + ROW_H - 3}
                        stroke="var(--border-strong)" strokeDasharray="2 2.4" />
                  <text x={BAR_X + 22} y={y + BAR_H + 19} className="hb-f-gate">↓ {GATES[i]}</text>
                </>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

/** The six words the rest of the page leans on.
 *
 * A reader who does not already know what a "signal" or a "cluster" is will read
 * every step as approximately-magic, and approximately-magic is exactly the
 * impression this page exists to remove. Defining them once, up front, is
 * cheaper than hedging every sentence that uses them.
 */
const GLOSSARY: { term: string; plain: string }[] = [
  { term: 'Signal',
    plain: 'One dated document from one publisher — a tender notice, a new law, an article, a paper. The smallest unit of evidence on the radar.' },
  { term: 'Theme cluster',
    plain: 'A group of signals the software judged to be about roughly the same thing. Nobody writes the groups; they fall out of the data.' },
  { term: 'Opportunity space',
    plain: 'One dot on the radar. A specific industry, plus a specific problem, plus a specific technology — never just “AI” or “cloud”.' },
  { term: 'Portfolio distance',
    plain: 'How far an opportunity sits from something Orange could deliver, from L0 (an existing product does it today) to L4 (nothing in the portfolio is close).' },
  { term: 'Source tier',
    plain: 'How much a publisher is trusted, 1 to 4. A statistics office and a vendor’s marketing blog do not carry the same weight.' },
  { term: 'Refresh',
    plain: 'One complete run of everything below. Runs are comparable to each other, which is what lets the radar show movement rather than a new list each time.' },
]

/** Weight keys are stored identifiers; `replace(/_/g, ' ')` turns
 *  `novelty_momentum` into "novelty momentum", which is not a phrase. The two
 *  score panels elsewhere in the app spell these out, and the explainer of the
 *  method is the last place that should disagree with them. */
const WEIGHT_LABELS: Record<string, string> = {
  market_signal_strength: 'market signal strength',
  source_diversity: 'source diversity',
  evidence_quality: 'evidence quality',
  novelty_momentum: 'novelty and momentum',
  strategic_relevance: 'strategic relevance',
  offer_match: 'offer match',
  reference_density: 'reference density',
  partner_coverage: 'partner coverage',
  compliance_fit: 'compliance fit',
  capability_depth: 'capability depth',
  external_validation: 'external validation',
  technology_ownership: 'technology ownership',
}

/* ---------- the division of labour, stated rather than implied ----------- */

const LABOUR: { task: string; method: string; model: boolean; why: string }[] = [
  { task: 'Counting, diversity, recency, momentum', method: 'Arithmetic', model: false,
    why: 'a model asked to count will occasionally be wrong and always be unverifiable' },
  { task: 'Theme extraction and clustering', method: 'Embeddings', model: false,
    why: 'clustering is reproducible; generation here would invent structure' },
  { task: 'Relevance gating', method: 'Keywords, then a cheap model', model: true,
    why: 'the cheapest thing that works — most items never reach inference' },
  { task: 'Opportunity synthesis and critique', method: 'Strong model, then a critic', model: true,
    why: 'the one genuinely creative step; volume is low, so quality dominates cost' },
  { task: 'Right to win', method: 'Structured lookup on the graph', model: false,
    why: 'matching against the asset catalogue is a join, not an inference' },
  { task: 'Market size', method: 'Bottom-up computation', model: false,
    why: 'published figures are quoted without method and conflict by an order of magnitude' },
  { task: 'Competitive intensity', method: 'Curated register + query', model: false,
    why: 'a competitor is a named entity with evidence attached, never a guess' },
  { task: 'Description and next action', method: 'Templated generation', model: true,
    why: 'the named assets are handed in from the graph — the model only writes the sentence' },
]

/* ---------- the modal --------------------------------------------------- */

function Step({ icon: Icon, n, title, wide, children }: {
  icon: (p: { className?: string }) => JSX.Element
  n: number
  title: string
  /** Spans both columns. The ninth step has no partner, and a half-width card
   *  beside a gap reads as a card that failed to load. */
  wide?: boolean
  children: React.ReactNode
}) {
  return (
    <section className={wide ? 'hb-step hb-step-wide' : 'hb-step'}>
      <div className="hb-step-head">
        <span className="hb-step-n">{n}</span>
        <Icon className="hb-step-icon" />
        <h5>{title}</h5>
      </div>
      <div className="hb-step-body">{children}</div>
    </section>
  )
}

export default function HowBuilt({ open, onClose, meta }: {
  open: boolean
  onClose: () => void
  meta: Meta
}) {
  const ref = useRef<HTMLDivElement>(null)
  useFocusTrap(open, ref, onClose)
  if (!open) return null

  const refreshed = meta.last_refresh
    ? (meta.last_refresh.finished_at ?? meta.last_refresh.started_at).slice(0, 10)
    : null
  const triple = `${meta.verticals.length} × ${meta.use_cases.length} × ${meta.technologies.length}`
  const attractivenessParts = Object.entries(meta.attractiveness_weights)
  const rtwParts = Object.entries(meta.right_to_win_weights)

  return (
    <div className="help-backdrop" onClick={onClose} role="presentation">
      <div className="help-modal hb-modal" role="dialog" aria-modal="true"
           aria-labelledby="hb-title" tabIndex={-1} ref={ref}
           onClick={(e) => e.stopPropagation()}>

        <div className="help-head">
          <div>
            <h3 id="hb-title">How the radar was created</h3>
            <p className="hb-lede">
              Every mark on the plot began as a public document. Thirteen stages sit between the
              document and the dot — and only three of them are allowed to write a sentence.
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="hb-body">

          <h4 className="hb-h"><IconRadar className="hb-h-icon" />What this thing actually does</h4>
          <p>
            Once a month, software reads what the outside world has published — new laws, contracts
            that organisations are putting out to bid, research papers, technical standards, job
            adverts, news. On its own that is a pile of documents. The radar’s job is to notice what
            keeps coming up, turn each recurring theme into <em>one concrete business opportunity</em>,
            and then answer two questions about it that are kept strictly separate:
          </p>
          <div className="hb-two-qs">
            <div>
              <span className="hb-q-tag">Is the world moving on this?</span>
              Answered <b>only</b> from outside evidence — who is publishing, how credible they are,
              whether the volume is rising. Orange does not appear in this answer at all. The radar
              calls it <b>attractiveness</b>, and it decides how <b>large</b> a dot is drawn.
            </div>
            <div>
              <span className="hb-q-tag">Could Orange win the work?</span>
              Answered <b>only</b> from what Orange already has — products, customer projects
              delivered, partners, certifications, people. The market does not appear in this answer
              at all. The radar calls it <b>right to win</b>, and it decides how <b>dark</b> a dot is.
            </div>
          </div>
          <p>
            Keeping them apart is the whole design. A single blended “score” would hide the only two
            situations worth acting on: something the world clearly wants that Orange cannot yet
            deliver (a job for strategy), and something Orange is ready to sell that nobody has
            noticed is being bought (a job for sales). And nothing on the radar is somebody’s opinion
            typed in — every dot has to be able to produce the documents behind it, on demand.
          </p>

          <h4 className="hb-h"><IconList className="hb-h-icon" />Six words used below</h4>
          <dl className="hb-gloss">
            {GLOSSARY.map((g) => (
              <div key={g.term}>
                <dt>{g.term}</dt>
                <dd>{g.plain}</dd>
              </div>
            ))}
          </dl>

          <h4 className="hb-h"><IconRefresh className="hb-h-icon" />One refresh, left to right</h4>
          <p>
            A refresh is a single ordered run: thirteen stages, each with one job, each writing its
            result down before the next one starts. Because every stage stores its own output, a
            stage can be re-run on its own, and the whole run can be repeated later and compared.
          </p>
          <PhaseDiagram />
          <p className="hb-caption">
            <b>How to read it:</b> work left to right. Each box is a phase, the small monospaced words
            inside it are the actual stage names in the code, and the line under each box says what
            that phase hands to the next one.
          </p>
          <p>
            One consequence is worth calling out. The run can be told to pretend it is an earlier
            date — a <b>historical replay</b>. Every source is then cut off at that date, so the radar
            can be asked what it would have put in front of you in 2024, and the answer can be
            checked against what actually happened since. That is the difference between a system
            that sounds convincing and one that can be tested.
          </p>

          <h4 className="hb-h"><IconRadar className="hb-h-icon" />Stage by stage</h4>

          <div className="hb-steps">
            <Step icon={IconWaves} n={1} wide title="Collect">
              <p>
                Software reads 42 public sources on a schedule. The <em>mix</em> matters more than
                the number, because each kind of source answers a different question — and the ones
                that matter most are the least glamorous:
              </p>
              <ul className="hb-sources">
                <li><b>Procurement portals</b> — TED, BOAMP, UK Contracts Finder. What organisations
                    are actually putting money behind. Money is a better signal than opinion.</li>
                <li><b>Law and regulators</b> — EUR-Lex, ENISA, CERT-EU, national agencies. What is
                    about to become compulsory, and roughly when.</li>
                <li><b>Research and standards</b> — OpenAlex, arXiv, patents, IETF, ETSI, 3GPP. What
                    is becoming technically possible before anyone is buying it.</li>
                <li><b>Job adverts and code</b> — what companies are hiring for and building right
                    now, which usually moves before the press notices.</li>
                <li><b>News, in six languages</b> — the rest, and the counterweight to an
                    English-only view of Europe.</li>
              </ul>
              <p className="hb-tech">
                Nothing here is private or purchased — anyone could read the same pages. Every raw
                payload is stored word-for-word <em>before</em> anything is derived from it, so any
                figure that appears later traces back to a web address, a named publisher and a
                publication date.
              </p>
            </Step>

            <Step icon={IconFunnel} n={2} title="Normalise, de-duplicate, gate and tier">
              <p>
                Twenty news sites running the same press release is <b>one</b> piece of news, not
                twenty — and a system that miscounts that will mistake an advertising campaign for a
                market. So each document is fingerprinted, the copies collapse into a single record,
                and the date, language and country are pinned down. Two questions are then put to
                whatever is left: <em>is this even relevant to us?</em> — most items are rejected
                here — and <em>how far should we trust whoever published it?</em>
              </p>
              <p className="hb-tech">
                Relevance is decided by a plain keyword filter for the clear-cut majority; only the
                genuinely ambiguous middle is passed to a small model. Trust is a published tier per
                publisher — <b>authoritative ×1.00</b> (regulators, statistics offices, courts),
                <b> independent reporting ×0.75</b>, <b>practitioner ×0.45</b> (forums, preprints),
                <b> interested party ×0.15</b> (a vendor writing about its own product). Tier 4 is
                capped on top of that, so no topic can climb on marketing material alone.
              </p>
            </Step>

            <Step icon={IconCluster} n={3} title="Embed and cluster">
              <p>
                The software has to notice that “ransomware at a regional hospital” and “clinic
                patient records held to ransom” are about the same thing, though they share almost no
                words — and in six languages at once. It does this by converting every passage into a
                long list of numbers, arranged so that <em>similar meanings land near each other</em>,
                then grouping whatever sits close together. Nobody writes the categories; they emerge
                from the documents.
              </p>
              <p className="hb-tech">
                Technically: multilingual sentence embeddings, then agglomerative clustering at cosine
                distance 0.58, minimum group size 3. There is no <code>k</code> to pick and no random
                starting point — feed the same documents and settings in twice and the same radar
                comes out, which a randomised method could not promise. A group of two is a
                coincidence, not a theme, so it never goes forward.
              </p>
            </Step>

            <Step icon={IconSpark} n={4} title="Synthesise, then attack the result">
              <p>
                A pile of related documents is still not an opportunity. This is the one step where an
                AI language model <em>writes</em> something: it reads a cluster and proposes a
                concrete sentence — this industry, this problem, this technology — that the documents
                behind it actually support. It is deliberately asked for <b>three</b> different
                attempts rather than one, and a second pass then marks each out of five and discards
                the weak ones. Generating cheaply and rejecting hard beats coaxing one perfect answer.
              </p>
              <p className="hb-tech">
                Three candidates per cluster at temperature 0.85 (high, to force variety), critiqued
                at temperature 0.10 (low, to be consistent); under 3 out of 5 a candidate is revised
                once, then dropped. A topic’s identity <em>is</em> its industry-problem-technology
                triple, so next month’s run recognises and updates it instead of minting a fresh,
                incomparable one — the only reason movement over time can be measured at all.
              </p>
            </Step>

            <Step icon={IconLink} n={5} title="Enrich">
              <p>
                Topics do not stop existing between runs. When documents arrive that plainly belong to
                a topic created two months ago, they are filed against <em>that</em> topic rather than
                starting a near-duplicate beside it. Without this, an established topic would slowly
                look as though nobody was talking about it any more — not because attention had faded,
                but because nothing new had been filed under it.
              </p>
              <p className="hb-tech">
                Matching only, never writing: a document is attached when it is close enough in
                meaning <b>and</b> independently confirms the topic’s industry, problem or technology
                through its own text or its procurement category. The reason for every attachment is
                recorded, so an enriched topic can be audited exactly like a newly written one.
              </p>
            </Step>

            <Step icon={IconCube} n={6} title="Join to the Orange Business Graph">
              <p>
                Everything up to here is about the outside world. This step brings Orange into it. A
                hand-curated catalogue records what Orange sells, which customers it has already done
                this kind of work for, which partners and certifications it holds and which
                technologies it built itself. Matching a topic against that catalogue answers the
                practical question: <em>how far is this from something we could actually deliver?</em>
              </p>
              <p className="hb-tech">
                The answer is a distance, from <b>L0</b> — an existing product does this today —
                through bundling and partnering, to <b>L4</b>, where nothing in the portfolio is
                close. It decides which topics a salesperson is shown and which belong on a
                strategist’s agenda. No language model runs in this step: it is a lookup, every entry
                carries its source and its date, and a claimed connection nobody can explain is worse
                than none — it will eventually be said out loud to a customer.
              </p>
            </Step>

            <Step icon={IconGauge} n={7} title="Score — two numbers, kept apart">
              <p>
                The two questions from the top of this page finally become two numbers out of 100.
                Neither is a single judgement; each is a handful of separately measured ingredients
                with a published weight, so a score can always be taken apart and argued with.
              </p>
              <p>
                <b>Attractiveness</b> — is the world moving? {attractivenessParts.map(([k, v], i) => (
                  <span key={k}>{i > 0 ? ', ' : ''}{WEIGHT_LABELS[k] ?? k.replace(/_/g, ' ')}&nbsp;
                    <span className="hb-w">{Math.round(v * 100)}%</span></span>
                ))}. In everyday terms: how much is being published, by how many genuinely
                independent publishers, how credible they are, whether the volume is rising or
                fading, and whether it connects to what Orange has publicly said it wants to be.
              </p>
              <p>
                <b>Right to win</b> — could we win the work? {rtwParts.map(([k, v], i) => (
                  <span key={k}>{i > 0 ? ', ' : ''}{WEIGHT_LABELS[k] ?? k.replace(/_/g, ' ')}&nbsp;
                    <span className="hb-w">{Math.round(v * 100)}%</span></span>
                ))}. In everyday terms: do we sell something that does this, have we proved it with a
                real customer, can a partner supply the missing piece, do we hold the certifications
                this industry insists on, do we have enough people, and did we build any of the
                technology ourselves.
              </p>
              <p className="hb-tech">
                The two are never averaged into one figure. A topic can be excellent for a strategist
                and useless for a salesperson, and a single blended rank hides the one fact either of
                them needed. Every ingredient stores the inputs that produced it, which is why the
                “?” beside any number in this product can show its own arithmetic.
              </p>
            </Step>

            <Step icon={IconMoney} n={8} title="Size it, and count the field">
              <p>
                “How big is this market?” is where most trend reports quietly invent a number: a
                headline figure from a research house, quoted with no method, often disagreeing with
                the next one by a factor of ten. The radar refuses to quote. It multiplies out three
                things that can each be checked — <b>how many companies of this kind exist</b>{' '}
                (official statistics), <b>what share of them have adopted the technology</b>{' '}
                (official survey), and <b>what contracts like this actually cost</b>{' '}
                (real tender values) — and shows every factor.
              </p>
              <p className="hb-tech">
                A second, completely separate figure is then built from awarded contracts alone. Two
                methods drawn from different data landing in the same ballpark is an argument; one
                unattributable billion-euro number is not. Competitors are handled the same way: a
                named register, splitting <b>evidenced</b> presence (this corpus names them here, and
                links the document) from <b>structural</b> presence (the register says they sell this,
                which is true but is not proof).
              </p>
            </Step>

            <Step icon={IconDoc} n={9} title="Describe and recommend">
              <p>
                Last, each topic is written up the way somebody actually needs it the morning before a
                customer meeting: what this is, why it is happening now, which questions to ask, what
                Orange would put on the table, and one concrete next step — a different one for a
                strategist, a salesperson and a pre-sales engineer, because “interesting” is not an
                action. Every name and number in that write-up was verified by an earlier stage; the
                model is only allowed to arrange them into sentences.
              </p>
              <p className="hb-tech">
                The model does not draw the accompanying solution diagram either. It emits a
                <b> structure</b> — layers, boxes, flows — and the renderer draws it with the same
                geometry every time. A model asked directly for drawing code produces something that
                looks plausible and overlaps its own labels.
              </p>
            </Step>
          </div>

          <h4 className="hb-h"><IconFunnel className="hb-h-icon" />What each gate throws away</h4>
          <p>
            Most of what is collected never reaches the plot, and that is the point: a radar that
            showed everything would be a news feed. Each row below is what survives, and the dotted
            line beneath it is the test that removed the rest. There is one deliberate exception —
            the fifth row is <em>wider</em> than the one above it, because synthesis writes three
            candidates for every cluster so that the critic has something to reject. Generating
            cheaply and rejecting hard is safer than trying to repair one weak answer.
          </p>
          <FunnelDiagram />
          <p className="hb-caption">
            <b>How to read it:</b> the bars are illustrative proportions, not counts — the real numbers
            change with every run. What is fixed is the order, and the test written under each bar.
          </p>

          <h4 className="hb-h"><IconShield className="hb-h-icon" />What the model is not allowed to do</h4>
          <p>
            A language model produces a fluent, confident sentence whether or not it has any grounds
            for it — and a confident invented sentence is far more dangerous here than an obviously
            missing one, because it will be repeated in a meeting. That risk is the reason the model
            is confined to three of the thirteen stages, and why four separate defences run on
            everything it does write. They are listed in the order they actually work, not the order
            they run:
          </p>
          <ol className="hb-defences">
            <li>
              <b>Evidence binding.</b> Every claim must cite signal ids present in the cluster that
              produced it. An uncited claim is <em>stripped, not rewritten</em> — rewriting is how a
              plausible sentence survives with no evidence behind it.
            </li>
            <li>
              <b>Closed vocabulary.</b> A candidate must resolve to exactly one vertical × use case ×
              technology drawn from the shipped taxonomy — {triple} today — or it is discarded rather
              than coerced.
            </li>
            <li>
              <b>No generated numbers.</b> A hard rule appended to every generative prompt, and a
              regex over every emitted sentence. Figures come from the sizing engine, attributed and
              dated, or they are absent: a fabricated market size repeated in a customer meeting is
              the failure this project cannot afford.
            </li>
            <li>
              <b>Entailment.</b> A cheap second pass asking whether each “why now” claim actually
              follows from the evidence cited for it — the check that catches a true sentence
              attached to the wrong source.
            </li>
          </ol>

          <p>
            The wider principle is that each task is given to the cheapest method that can be checked.
            Anything countable is counted; anything that is a lookup is looked up; the model is used
            where judgement genuinely helps and nowhere else. Eleven of the thirteen stages never call
            one at all:
          </p>
          <div className="hb-scroll">
            <table className="hb-table">
              <thead>
                <tr><th>Task</th><th>Method</th><th>Model?</th><th>Why</th></tr>
              </thead>
              <tbody>
                {LABOUR.map((row) => (
                  <tr key={row.task}>
                    <td><b>{row.task}</b></td>
                    <td>{row.method}</td>
                    <td>
                      <span className="hb-flag" data-model={row.model || undefined}>
                        {row.model ? 'yes' : 'no'}
                      </span>
                    </td>
                    <td className="hb-why">{row.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h4 className="hb-h"><IconRefresh className="hb-h-icon" />…and then it runs again</h4>
          <p>
            Any pipeline can produce an impressive first output. The hard part is the second run. If
            next month’s run simply produced another plausible list, nothing could be compared and the
            radar would have no memory — you could never say “this is growing” or “that has gone
            quiet”, only “here is a new picture”.
          </p>
          <p>
            So the run is built to <b>update the same topics</b> rather than replace them: identity is
            the industry-problem-technology triple, write-ups are regenerated only where a topic
            genuinely changed, and if anyone edits how the scores are weighted, the new settings get a
            new name and the radar refuses to plot old and new scores on the same picture. Two numbers
            produced by two different rulers are not comparable, however similar they look.
          </p>
        </div>

        <div className="hb-foot">
          <span><i>Weight set</i><code>{meta.weight_set}</code></span>
          <span><i>Pipeline</i><code>v{meta.pipeline_version}</code></span>
          {refreshed && <span><i>Last refresh</i><code>{refreshed}</code></span>}
          <span className="hb-foot-note">
            Same inputs, same configuration, same radar — every stage is deterministic except
            synthesis, which records the prompt version that produced each topic.
          </span>
        </div>
      </div>
    </div>
  )
}
