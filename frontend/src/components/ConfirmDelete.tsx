import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useFocusTrap } from './Help'
import type { DeletionImpact } from '../types'

/** "Delete this opportunity space" — with the consequence spelled out first.
 *
 * A space is the hub of the schema. Thirteen tables point at it, and by the time
 * anybody wants one gone it is carrying evidence attachments, two scored
 * trajectories, curator-confirmed asset links, stage-gate history, per-role
 * assessments, a market estimate, a written description, a competitive read, a
 * PDF, and possibly a place in a portfolio plan. None of that is visible from
 * the button, so the dialog asks the server what would go and reads the answer
 * out before it asks anything of the user.
 *
 * Three things it makes a point of saying, because each one is a decision
 * somebody could reasonably disagree with:
 *
 *   * the signals STAY — evidence is shared between spaces and kept for replay,
 *     so a reader who thinks 47 sources are about to be destroyed is wrong, and
 *     would be right not to press the button if they were not told;
 *   * a plan that selected this space stops adding up, named plan by plan;
 *   * a later refresh that meets the same taxonomy triple will synthesise the
 *     space again, because identity is the triple (DR-03). Deleting is a
 *     statement about the corpus as it stands, not a permanent veto.
 *
 * The id has to be typed to enable the button. That is not friction for its own
 * sake: this control lives beside "Regenerate description", both are one click,
 * and only one of them is irreversible.
 */

export default function ConfirmDelete({ topicId, statement, onCancel, onDeleted }: {
  topicId: string
  statement: string
  onCancel: () => void
  onDeleted: (topicId: string) => void
}) {
  const [impact, setImpact] = useState<DeletionImpact | null>(null)
  const [typed, setTyped] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)
  useFocusTrap(true, ref, onCancel)

  useEffect(() => {
    let cancelled = false
    api.deletionImpact(topicId)
      .then((data) => { if (!cancelled) setImpact(data) })
      .catch((exc) => { if (!cancelled) setError(String(exc.message ?? exc)) })
    return () => { cancelled = true }
  }, [topicId])

  const confirmed = typed.trim().toUpperCase() === topicId.toUpperCase()

  const remove = () => {
    if (!confirmed || pending) return
    setPending(true)
    setError(null)
    api.deleteTopic(topicId)
      .then(() => onDeleted(topicId))
      .catch((exc) => { setError(String(exc.message ?? exc)); setPending(false) })
  }

  // A plan can select a space once, but the impact lists one row per selection
  // and two plans can name the same space — so the list is keyed by plan.
  const plans = impact ? [...new Map(impact.plans.map((p) => [p.id, p])).values()] : []

  return (
    <div className="help-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onCancel() }}>
      <div className="help-modal del-modal" role="dialog" aria-modal="true"
           aria-labelledby="del-title" tabIndex={-1} ref={ref}>
        <div className="help-head">
          <h3 id="del-title">Delete {topicId}?</h3>
          <button onClick={onCancel}>Close</button>
        </div>

        <div className="help-body">
          <p className="del-statement">{impact?.statement ?? statement}</p>
          {impact && (
            <p className="del-triple">
              {impact.triple.vertical} × {impact.triple.use_case} × {impact.triple.technology}
              {' · '}{impact.state}
            </p>
          )}

          {!impact && !error && <p>Working out what this would remove…</p>}

          {impact && (
            <>
              <h4 className="del-head">This removes</h4>
              {impact.removes.length === 0 ? (
                <p className="del-none">
                  Nothing but the space itself — no evidence, scores, links or assessments are
                  attached to it.
                </p>
              ) : (
                <ul className="del-list">
                  {impact.removes.map((entry) => (
                    <li key={`${entry.table}-${entry.label}`}>
                      <b>{entry.count}</b> {entry.label}
                    </li>
                  ))}
                </ul>
              )}

              {impact.merged_duplicates.length > 0 && (
                <p className="del-warn">
                  <b>And {impact.merged_duplicates.join(', ')}</b> — {impact.merged_duplicates.length === 1
                    ? 'a duplicate that was folded into this space'
                    : 'duplicates that were folded into this space'}. Under the identity rule they
                  are the same space, so they go with it.
                </p>
              )}

              {plans.length > 0 && (
                <div className="del-plans">
                  <h4 className="del-head">This breaks {plans.length === 1 ? 'a plan' : 'plans'}</h4>
                  <p>
                    A plan is computed once and stored whole, so its projection and its space count
                    still include this space. Deleting it will leave {plans.length === 1 ? 'this plan' : 'these plans'}
                    {' '}no longer adding up:
                  </p>
                  <ul className="del-list">
                    {plans.map((plan) => (
                      <li key={plan.id}>
                        <b>{plan.label || plan.id}</b>
                        <span className="del-muted"> · entered in year {plan.entry_year}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="del-keep">
                <b>{impact.signals_kept} signal{impact.signals_kept === 1 ? '' : 's'} stay.</b>{' '}
                Evidence is shared between spaces and kept so a past date can be replayed — only the
                attachment to this space goes.
              </p>

              <p className="del-note">
                A space is identified by its vertical × use case × technology, so a later refresh
                that finds the same combination in the evidence will create it again, with a new id
                and none of the history above. Deleting is a statement about the corpus as it
                stands, not a permanent veto.
              </p>

              <label className="login-field del-confirm">
                <span>Type <code>{topicId}</code> to confirm</span>
                <input value={typed} autoComplete="off" autoCapitalize="characters"
                       spellCheck={false} aria-label={`Type ${topicId} to confirm the deletion`}
                       onChange={(e) => setTyped(e.target.value)}
                       onKeyDown={(e) => { if (e.key === 'Enter') remove() }} />
              </label>
            </>
          )}

          <div className="login-error" role="alert" aria-live="assertive">{error ?? ''}</div>

          <div className="pw-actions">
            <button type="button" onClick={onCancel}>Keep it</button>
            <button type="button" className="del-go" disabled={!confirmed || pending}
                    onClick={remove}>
              {pending ? 'Deleting…' : `Delete ${topicId}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
