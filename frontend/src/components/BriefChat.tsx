import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import type {
  ChatMessage, GenerationOptions, HypothesisRequest, Meta, ScopingBrief, ScopingOpening,
  ScopingSignal, ScopingTurn,
} from '../types'
import { HYPOTHESIS_KINDS } from '../types'

/** The scoping conversation — the Generate screen's assistant tab (FR-06, §4.4).
 *
 * It replaces a textarea and a character counter. That pairing asked for one
 * thing and gave one piece of feedback, and the feedback was about length: the
 * only failure it could warn about was the one that did not matter. An
 * opportunity space is a vertical × use case × technology plus a buyer's problem
 * and a place, and somebody who knows their market but not this taxonomy
 * under-specifies two of those every time. They found out minutes later, from a
 * run that created nothing.
 *
 * Three things this screen does that a chat window normally does not, each
 * because the thing being composed is a retrieval and not a wish:
 *
 * 1. THE EVIDENCE SITS BESIDE THE CONVERSATION. Every turn is re-retrieved from
 *    the whole transcript against the same signal vectors the run will read, and
 *    what came back is shown with publisher, date and similarity, linked. An
 *    assistant claiming to know what the corpus holds, on a screen where that
 *    cannot be checked, is just a confident chatbot.
 *
 * 2. THE BUTTON IS ENABLED BY THE CORPUS, NOT BY THE ASSISTANT. `ready` is the
 *    server's verdict: each proposed brief goes back through the run's own
 *    retrieval, and one the corpus cannot answer is shown with the reason and
 *    cannot be selected. The model's own opinion is only surfaced when the two
 *    disagree, because that disagreement is worth seeing.
 *
 * 3. THE BRIEFS ARE EDITABLE. What is generated is what is in the box, not what
 *    the assistant said — and the job re-checks whatever is submitted, so an
 *    edit that breaks the retrieval fails honestly rather than silently.
 */

interface Props {
  meta: Meta
  options: GenerationOptions | null
  /** A run is in flight — one at a time, so the conversation may continue but
   *  nothing may be started. */
  active: boolean
  starting: boolean
  /** Generation is impossible in this deployment at all (no encoder, no clusters). */
  blocked: boolean
  onGenerate: (descriptions: string[]) => void
  /** Build a space the corpus is silent about, on contributed evidence. */
  onHypothesis: (body: HypothesisRequest) => void
  onOpenTopic: (id: string) => void
}

/** The second route, offered where the first one closes.
 *
 * The corpus cannot evidence a genuinely new idea — that is what "new" means —
 * and a screen that stops there is useless for the thing it is most wanted for.
 * What it must NOT do is invent the evidence: a space citing signals that are
 * not about it is the exact failure §4.4.4 exists to prevent, and it would make
 * every other space on the radar less believable.
 *
 * So the evidence is contributed rather than fabricated. What the person knows
 * becomes an internal signal — their name on it, dated today, tier 3 because a
 * conversation is not a published record — and the ordinary run cites that. The
 * space gets built and scores low, which is the honest reading of a hypothesis
 * rather than a shortcoming to hide.
 */
function HypothesisForm({ brief, disabled, evidenced, onSubmit }: {
  brief: ScopingBrief
  disabled: boolean
  /** The corpus does carry this brief, so Generate above will run. This route
   *  is then the fallback rather than the only way through. */
  evidenced: boolean
  onSubmit: (body: HypothesisRequest) => void
}) {
  const [open, setOpen] = useState(false)
  const [rationale, setRationale] = useState(brief.hypothesis_rationale ?? '')
  const [kind, setKind] = useState<string>(HYPOTHESIS_KINDS[0].id)
  const MIN = 80
  const short = rationale.trim().length < MIN

  if (!open) {
    return (
      <div className={`chat-hyp${evidenced ? ' is-fallback' : ''}`}>
        <p>
          {evidenced ? (
            <>
              <b>Or build it on what you know instead.</b> The corpus carries this well enough to
              run, but a run can still end with nothing: the candidate has to survive a critic that
              rejects claims citing evidence which is near the subject rather than about it. If
              that happens, or if you would rather the space rested on your own account, take this
              route.
            </>
          ) : (
            <>
              <b>The corpus is silent about this — that is not the same as the idea being
              wrong.</b>{' '}
              Nobody has published about it yet, which is what makes it new. You can still build
              the space, on what <i>you</i> know rather than on evidence that is not about it.
            </>
          )}
          {brief.hypothesis_rationale
            && ' What you have said so far is already written up below — check it and go.'}
        </p>
        <button type="button" onClick={() => setOpen(true)} disabled={disabled}>
          Build it on what I know →
        </button>
      </div>
    )
  }

  return (
    <div className="chat-hyp is-open">
      <h5>What do you know that the radar does not?</h5>
      <p>
        This is recorded as an <b>internal signal</b> — your name on it, dated today, tier 3
        because a conversation is not a published record (§4.3.7). The space then cites it the way
        it would cite anything else, and it has to survive the same critic and entailment checks.
        Nothing is invented; the evidence is contributed and attributed.
      </p>
      <label className="chat-hyp-kind">
        <span>What kind of thing is this?</span>
        <select value={kind} onChange={(e) => setKind(e.target.value)} disabled={disabled}>
          {HYPOTHESIS_KINDS.map((k) => (
            <option key={k.id} value={k.id}>{k.label} — counts as a {k.becomes}</option>
          ))}
        </select>
      </label>
      <textarea
        rows={4}
        value={rationale}
        maxLength={2000}
        disabled={disabled}
        placeholder="Who asked, what they wanted, what stopped them. Something a colleague could act on — not a restatement of the brief."
        onChange={(e) => setRationale(e.target.value)}
        aria-label="What you know that the corpus does not"
      />
      <div className="chat-hyp-foot">
        <span className="gen-quiet">
          {short
            ? `${MIN - rationale.trim().length} more characters — the space will rest on this, so it
               has to say something`
            : `${rationale.trim().length} of 2000 characters`}
        </span>
        <span className="spacer" />
        <button type="button" onClick={() => setOpen(false)} disabled={disabled}>Cancel</button>
        <button
          className="gen-go"
          disabled={disabled || short}
          onClick={() => onSubmit({
            description: brief.description,
            rationale: rationale.trim(),
            kind,
            vertical: brief.vertical,
            geographies: brief.geographies,
          })}
        >
          Record it and build the space
        </button>
      </div>
      <p className="gen-quiet">
        Expect a low score. One tier-3 signal with no independent corroboration is exactly what a
        hypothesis looks like to the scoring model — and the radar saying so is the point. It will
        rise on its own as real evidence arrives and attaches to it.
      </p>
    </div>
  )
}

/** Turn a taxonomy id into the label a person uses, falling back to the id. */
function useLabeller(meta: Meta) {
  return useMemo(() => {
    const index = new Map<string, string>()
    for (const group of [meta.verticals, meta.use_cases, meta.technologies, meta.personas]) {
      for (const item of group) index.set(item.id, item.label)
    }
    return (id: string | null | undefined) => (id ? index.get(id) ?? id : null)
  }, [meta])
}

/** One retrieved signal. Carries what makes it checkable — who published it,
 *  when, and how close it actually was — because a retrieval nobody can open is
 *  decoration. */
function EvidenceRow({ signal }: { signal: ScopingSignal }) {
  const body = (
    <>
      <span className="chat-ev-title">{signal.title}</span>
      <span className="chat-ev-meta">
        {signal.publisher} · {signal.published_at}
        {signal.signal_type && ` · ${signal.signal_type.replace(/_/g, ' ')}`}
        {` · tier ${signal.tier}`}
        {signal.geographies && signal.geographies.length > 0 && ` · ${signal.geographies.join(' ')}`}
      </span>
      {/* Only shown where corroboration was asked for — beside a proposed brief.
          "Similarity only" is the interesting half: it is how a retrieval of ten
          can support nothing. */}
      {signal.corroborates !== undefined && (
        <span className={`chat-ev-support${signal.corroborates ? ' is-real' : ''}`}>
          {signal.corroborates ?? 'reads like it, but is not evidence for what this describes'}
        </span>
      )}
    </>
  )
  return (
    <li className="chat-ev">
      <span className="chat-ev-sim" title="Cosine similarity to the conversation so far">
        {signal.similarity.toFixed(2)}
      </span>
      {signal.url
        ? <a href={signal.url} target="_blank" rel="noreferrer" className="chat-ev-body">{body}</a>
        : <span className="chat-ev-body">{body}</span>}
    </li>
  )
}

/** A proposed brief, with everything that decides whether it can be run.
 *
 * The description is editable. That is not a convenience: the assistant writes
 * for retrieval and the person knows their market, and the run re-retrieves
 * whatever is submitted — so letting them fix a word costs nothing and being
 * unable to is the difference between a proposal and a decree. */
function BriefCard({ brief, index, text, selected, onText, onToggle, onOpenTopic, min, max, label,
                    onHypothesis, busy }: {
  brief: ScopingBrief
  index: number
  text: string
  selected: boolean
  onText: (value: string) => void
  onToggle: () => void
  onOpenTopic: (id: string) => void
  min: number
  max: number
  label: (id: string | null | undefined) => string | null
  onHypothesis: (body: HypothesisRequest) => void
  busy: boolean
}) {
  const length = text.trim().length
  const tooShort = length < min
  return (
    <div className={`chat-brief${selected ? ' is-on' : ''}${brief.runnable ? '' : ' is-blocked'}`}>
      <div className="chat-brief-head">
        <label className="chat-brief-pick">
          <input
            type="checkbox"
            checked={selected}
            disabled={!brief.runnable}
            onChange={onToggle}
          />
          <span>{brief.title || `Space ${index + 1}`}</span>
        </label>
      </div>

      <p className="chat-brief-triple">
        {[label(brief.vertical), label(brief.use_case), label(brief.technology)]
          .filter(Boolean).join(' · ') || 'no taxonomy triple resolved'}
        {brief.geographies.length > 0 && ` · ${brief.geographies.join(' ')}`}
      </p>

      <textarea
        className="chat-brief-text"
        rows={3}
        value={text}
        maxLength={max}
        onChange={(e) => onText(e.target.value)}
        aria-label={`Search brief for ${brief.title || `space ${index + 1}`}`}
      />
      <div className="chat-brief-foot">
        <span className="gen-quiet">
          {tooShort
            ? `${min - length} more character${min - length === 1 ? '' : 's'}`
            : `${length} of ${max} characters`}
          {' · '}edited text is re-checked against the corpus by the run
        </span>
      </div>

      {brief.rationale && <p className="chat-brief-why">{brief.rationale}</p>}

      {brief.problems.length > 0 && (
        <ul className="chat-brief-problems">
          {brief.problems.map((problem, i) => <li key={i}>{problem}</li>)}
        </ul>
      )}

      {/* Offered whether or not the evidence-backed route is open. A runnable
          brief is not a guaranteed space: the run log's commonest ending is a
          candidate the critic threw out for citing evidence that was retrieved
          but not really about it. Someone who has just watched a finished run
          create nothing needs the second route to still be here. */}
      {brief.hypothesis && (
        <HypothesisForm brief={{ ...brief, description: text }} disabled={busy}
                        evidenced={brief.runnable} onSubmit={onHypothesis} />
      )}

      {brief.evidence.count > 0 && (
        <details className="chat-brief-ev">
          <summary>
            {brief.evidence.count} signal{brief.evidence.count === 1 ? '' : 's'} retrieved
            {' · '}
            <b className={brief.runnable ? '' : 'chat-thin'}>
              {brief.evidence.corroborated} independently about it
            </b>
            {brief.evidence.best !== null && ` · closest ${brief.evidence.best.toFixed(2)}`}
          </summary>
          <p className="gen-quiet">
            Retrieval finds text that reads like the brief; it does not find text that is{' '}
            <i>about</i> it. Support is a second, independent test — the signal's own words carry
            the use case or the technology, or its procurement codes do
            {brief.evidence.support_method === 'model'
              ? ' — and then a cheap model pass judged each one against this brief\'s own sentence '
                + 'rather than its taxonomy labels. The labels come from closed lists, so a '
                + 'proposal is routinely filed under the nearest available one; a tender that '
                + 'matches that label while being about something else is not evidence for it.'
              : '. The corpus could not be asked here.'}
          </p>
          <ul className="chat-ev-list">
            {brief.evidence.signals.map((signal) => (
              <EvidenceRow key={signal.id} signal={signal} />
            ))}
          </ul>
        </details>
      )}

      {/* Not a problem — the run is legal and useful — but it changes what the
          button does, and finding that out afterwards is the DR-03 surprise. */}
      {brief.existing && (
        <p className="chat-brief-dr03">
          This taxonomy triple is already{' '}
          <button type="button" className="chat-link" onClick={() => onOpenTopic(brief.existing!.id)}>
            {brief.existing.id}
          </button>
          . Under DR-03 a run landing here <b>refreshes</b> that space with the new evidence rather
          than creating a second one — which is what keeps momentum measurable, but it is not a new
          space.
        </p>
      )}
    </div>
  )
}

/** What has been established, and what is still open.
 *
 * The three required slots are shown apart from the rest because they ARE the
 * opportunity space (§4.4.5 — canonical identity is the taxonomy triple).
 * Everything else improves the brief; those three decide whether there is one. */
function Understood({ turn, label }: {
  turn: ScopingTurn
  label: (id: string | null | undefined) => string | null
}) {
  const u = turn.understood
  const rows: { id: string; label: string; value: string | null; required: boolean }[] = [
    { id: 'vertical', label: 'Vertical', value: label(u.vertical), required: true },
    { id: 'use_case', label: 'Use case', value: label(u.use_case), required: true },
    { id: 'technology', label: 'Technology', value: label(u.technology), required: true },
    { id: 'buyer_problem', label: 'The pain', value: u.buyer_problem, required: false },
    { id: 'geographies', label: 'Geography', value: u.geographies.join(' ') || null, required: false },
    {
      id: 'personas',
      label: 'Buyer',
      value: u.personas.map((p) => label(p)).filter(Boolean).join(', ') || null,
      required: false,
    },
    { id: 'deployment', label: 'Shape', value: u.deployment, required: false },
  ]
  return (
    <div className="chat-slots">
      <h4>What the radar has understood</h4>
      <ul>
        {rows.map((row) => (
          <li key={row.id} className={row.value ? 'is-filled' : row.required ? 'is-needed' : ''}>
            <span className="chat-slot-label">{row.label}</span>
            <span className="chat-slot-value">
              {row.value ?? (row.required ? 'still needed' : '—')}
            </span>
          </li>
        ))}
      </ul>
      {Object.keys(turn.unresolved).length > 0 && (
        <p className="gen-quiet">
          Not in the controlled vocabulary, so it was dropped rather than guessed:{' '}
          {Object.entries(turn.unresolved).map(([k, v]) => `${k} “${v}”`).join(', ')}. §3.3 keeps
          these closed — a value outside them fails validation at synthesis, so it cannot be carried
          this far.
        </p>
      )}
    </div>
  )
}

export default function BriefChat({
  meta, options, active, starting, blocked, onGenerate, onHypothesis, onOpenTopic,
}: Props) {
  const [opening, setOpening] = useState<ScopingOpening | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [turn, setTurn] = useState<ScopingTurn | null>(null)
  const [draft, setDraft] = useState('')
  const [thinking, setThinking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  /** Brief text by index, so an edit survives — but only until the next turn
   *  replaces the proposals it belonged to. */
  const [edits, setEdits] = useState<Record<number, string>>({})
  const [picked, setPicked] = useState<Record<number, boolean>>({})
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const label = useLabeller(meta)

  useEffect(() => {
    api.scopingOpening()
      .then((first) => {
        setOpening(first)
        setMessages([{ role: 'assistant', content: first.message }])
      })
      .catch((e) => setError(String(e).replace(/^Error:\s*/, '')))
  }, [])

  // Follow the tail. A transcript that has to be scrolled to see the question
  // just asked is a transcript nobody reads.
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages.length, thinking])

  const send = useCallback((text: string) => {
    const content = text.trim()
    if (!content || thinking) return
    const next: ChatMessage[] = [...messages, { role: 'user', content }]
    setMessages(next)
    setDraft('')
    setThinking(true)
    setError(null)
    api.scopingTurn(next, turn?.understood)
      .then((answer) => {
        setTurn(answer)
        setMessages([...next, { role: 'assistant', content: answer.reply }])
        // A new set of proposals invalidates edits and selections made against
        // the previous one — index 1 is a different brief now.
        setEdits({})
        setPicked(Object.fromEntries(
          answer.briefs.map((brief, index) => [index, brief.runnable]),
        ))
      })
      .catch((e) => {
        setError(String(e).replace(/^Error:\s*/, ''))
        // Put the turn back in the box rather than losing what was typed.
        setMessages(messages)
        setDraft(content)
      })
      .finally(() => {
        setThinking(false)
        inputRef.current?.focus()
      })
  }, [messages, thinking, turn])

  const briefs = turn?.briefs ?? []
  const textFor = useCallback(
    (index: number) => edits[index] ?? briefs[index]?.description ?? '',
    [edits, briefs],
  )
  const min = opening?.min_brief_chars ?? 40

  const selected = useMemo(
    () => briefs
      .map((brief, index) => ({ brief, index }))
      .filter(({ brief, index }) => brief.runnable && picked[index]
        && textFor(index).trim().length >= min),
    [briefs, picked, textFor, min],
  )

  const canGenerate = Boolean(turn?.ready) && selected.length > 0 && !active && !starting && !blocked

  const suggestions = turn?.suggestions ?? opening?.suggestions ?? []

  return (
    <div className="chat">
      <div className="chat-main">
        <div className="chat-log" ref={scrollRef} role="log" aria-live="polite"
             aria-label="Scoping conversation">
          {messages.map((message, index) => (
            <div key={index} className={`chat-msg chat-msg-${message.role}`}>
              <span className="chat-who">{message.role === 'user' ? 'You' : 'Radar'}</span>
              <div className="chat-bubble">
                {message.content.split('\n\n').map((para, i) => <p key={i}>{para}</p>)}
              </div>
            </div>
          ))}
          {thinking && (
            <div className="chat-msg chat-msg-assistant">
              <span className="chat-who">Radar</span>
              <div className="chat-bubble chat-thinking">
                <span className="spinner" /> Reading the corpus…
              </div>
            </div>
          )}
        </div>

        {error && <p className="gen-error chat-error">{error}</p>}

        {suggestions.length > 0 && !thinking && (
          <div className="chat-suggestions">
            {suggestions.map((suggestion, index) => (
              <button key={index} type="button" className="gen-chip"
                      onClick={() => send(suggestion)}>
                {suggestion}
              </button>
            ))}
          </div>
        )}

        <div className="chat-input">
          <textarea
            ref={inputRef}
            rows={2}
            value={draft}
            placeholder={messages.length <= 1
              ? 'An industry, a customer problem, a technology — start anywhere.'
              : 'Answer, or tell me I am asking the wrong question.'}
            disabled={thinking || !opening}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send(draft)
              }
            }}
            aria-label="Your answer"
          />
          <button className="gen-go" onClick={() => send(draft)}
                  disabled={thinking || !draft.trim() || !opening}>
            Send
          </button>
        </div>
        <p className="gen-quiet">
          Enter sends, Shift+Enter starts a line. The conversation lives in this browser tab only —
          nothing is stored, and the assistant reads the corpus fresh on every turn.
        </p>
      </div>

      <div className="chat-side">
        {opening && !turn && (
          <div className="chat-slots">
            <h4>What the assistant can see</h4>
            <ul>
              <li className="is-filled">
                <span className="chat-slot-label">Signals</span>
                <span className="chat-slot-value">
                  {opening.corpus.signals} classified, in {opening.corpus.clusters} theme clusters
                </span>
              </li>
              <li className="is-filled">
                <span className="chat-slot-label">Spaces</span>
                <span className="chat-slot-value">{opening.corpus.spaces} already in the radar</span>
              </li>
              {opening.corpus.date_range && (
                <li className="is-filled">
                  <span className="chat-slot-label">Dated</span>
                  <span className="chat-slot-value">
                    {opening.corpus.date_range[0]} to {opening.corpus.date_range[1]}
                  </span>
                </li>
              )}
              {opening.corpus.by_geography.length > 0 && (
                <li className="is-filled">
                  <span className="chat-slot-label">Best covered</span>
                  <span className="chat-slot-value">
                    {opening.corpus.by_geography.slice(0, 6)
                      .map(([code, n]) => `${code} ${n}`).join(' · ')}
                  </span>
                </li>
              )}
            </ul>
            {opening.corpus.clusters_sample.length > 0 && (
              <>
                <h4>What it is currently about</h4>
                <ul className="chat-clusters">
                  {opening.corpus.clusters_sample.slice(0, 8).map((cluster) => (
                    <li key={cluster.id}>
                      <span className="chat-cluster-size">{cluster.size}</span>
                      <span>{cluster.label}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
            <p className="gen-quiet">
              These are the theme clusters the pipeline built — the radar's own answer to “what is
              this corpus about”. Anything outside them is something the assistant will tell you it
              cannot evidence.
            </p>
          </div>
        )}

        {turn && <Understood turn={turn} label={label} />}

        {turn && (
          <div className="chat-evidence">
            <h4>
              What your words retrieved
              <span className="chat-count">{turn.evidence.count}</span>
            </h4>
            {turn.evidence.count === 0 ? (
              <p className="gen-quiet">
                Nothing above the similarity floor yet — either too little has been said to retrieve
                with, or the corpus carries nothing close. The assistant is told the same thing you
                are, so it will say which.
              </p>
            ) : (
              <>
                <p className="gen-quiet">
                  Re-retrieved from the whole conversation on every turn, against the same signal
                  vectors the run reads. Floor {turn.evidence.floor.toFixed(2)} cosine — below it a
                  signal is not evidence.
                </p>
                <ul className="chat-ev-list">
                  {turn.evidence.signals.map((signal) => (
                    <EvidenceRow key={signal.id} signal={signal} />
                  ))}
                </ul>
              </>
            )}
            {turn.occupied.length > 0 && (
              <details className="chat-occupied">
                <summary>{turn.occupied.length} space(s) already built on this evidence</summary>
                <ul>{turn.occupied.map((cell, i) => <li key={i}>{cell}</li>)}</ul>
              </details>
            )}
          </div>
        )}
      </div>

      {briefs.length > 0 && (
        <div className="chat-briefs">
          <div className="chat-briefs-head">
            <h3>
              {briefs.length === 1 ? 'The space this would generate'
                : `The ${briefs.length} spaces this would generate`}
            </h3>
            <span className="spacer" />
            <button className="gen-go" disabled={!canGenerate}
                    onClick={() => onGenerate(selected.map(({ index }) => textFor(index).trim()))}>
              {active ? <><span className="spinner" /> Generating…</>
                : starting ? 'Starting…'
                : `Generate ${selected.length || ''} space${selected.length === 1 ? '' : 's'}`.trim()}
            </button>
          </div>
          {/* The greyed button at the top is correct here and reads as a dead
              end anyway: the action that works is inside the card below, and
              somebody looking at a disabled Generate concludes the screen still
              refuses them. Say where to go. */}
          {briefs.some((b) => !b.runnable && b.hypothesis) && !canGenerate && (
            <p className="gen-blocked">
              <b>Generate is off because the corpus cannot evidence this — not because you cannot
              build it.</b> Nobody has published about it yet, which is what makes it new. Use{' '}
              <b>“Build it on what I know”</b> on the brief below: what you tell it is recorded as
              dated, attributable evidence under your name, and the space is built on that.
            </p>
          )}
          <p className="gen-note">
            Each brief is a separate synthesis pass over the evidence it retrieves. What runs is the
            text in the box — the run embeds it, retrieves again, and every claim in the resulting
            space has to cite what came back and survive the critic and the entailment check. A
            brief the corpus cannot answer creates nothing and says so; the others are unaffected.
          </p>
          {/* The disagreement worth surfacing. Everything else about the model's
              readiness opinion is noise; this case means the button is disabled
              for a reason the assistant's own words will not have mentioned. */}
          {turn && turn.model_ready && !turn.ready && (
            <p className="gen-blocked">
              The assistant believes this is ready, and the corpus disagrees. Every brief below was
              put back through the retrieval the run itself would perform, and none of them clears
              it — so generating would produce nothing. Keep talking: narrowing to what the evidence
              beside this conversation actually covers is what will change the answer.
            </p>
          )}
          {/* The other direction, and the one that used to leave a ticked brief
              under a dead button. The assistant hedges about the corpus and says
              "not ready"; the brief it wrote has already cleared the same check
              the run applies. Its opinion is worth showing and not worth
              obeying. */}
          {turn && !turn.model_ready && turn.ready && (
            <p className="gen-quiet">
              The assistant is hedging about the evidence, and it is right to — but the brief below
              already clears the check the run itself applies, so it can be generated. Its caution
              is about how <i>much</i> the corpus carries here, not about whether the run will find
              anything.
            </p>
          )}
          <div className="chat-brief-list">
            {briefs.map((brief, index) => (
              <BriefCard
                key={index}
                brief={brief}
                index={index}
                text={textFor(index)}
                selected={Boolean(picked[index])}
                min={min}
                max={opening?.max_brief_chars ?? 600}
                label={label}
                onText={(value) => setEdits((current) => ({ ...current, [index]: value }))}
                onToggle={() => setPicked((current) => ({ ...current, [index]: !current[index] }))}
                onOpenTopic={onOpenTopic}
                onHypothesis={onHypothesis}
                busy={active || starting || blocked}
              />
            ))}
          </div>
          {blocked && <p className="gen-blocked">{options?.reason}</p>}
          {active && (
            <p className="gen-quiet">
              A run is already in flight. One at a time — synthesis writes opportunity spaces, and
              the identity rule (DR-03) is enforced by a unique index on the taxonomy triple.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
