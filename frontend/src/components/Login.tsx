import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useFocusTrap } from './Help'
import type { User } from '../types'

/** Signing in, and changing the password that got you in.
 *
 * The radar is not a public document. Everything behind this form is competitive
 * analysis of named companies, Orange's own asset graph, market estimates with
 * the workings attached, and the stage-gate opinions of people who work here —
 * so the interesting design question is not the form, it is what the form is
 * allowed to tell somebody who is not supposed to be here. The answer is
 * nothing: one refusal, identical whether the account is unknown or the password
 * is wrong, because a sign-in form that distinguishes the two is a staff
 * directory with a slow interface.
 *
 * The rest is ordinary and deliberately so — a real `<form>`, so Enter submits
 * and a password manager recognises it; `autocomplete` hints, so it can fill it;
 * the error in a live region, so it is announced rather than merely displayed.
 */

export function LoginScreen({ onSignedIn }: { onSignedIn: (user: User) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const usernameRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => { usernameRef.current?.focus() }, [])

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (pending) return
    setPending(true)
    setError(null)
    api.login(username, password)
      .then((result) => onSignedIn(result.user))
      .catch((exc) => {
        setError(String(exc.message ?? exc))
        // The username is almost always right and the password almost never is,
        // so only one of them is cleared. Clearing both means retyping a name
        // the user got right the first time.
        setPassword('')
      })
      .finally(() => setPending(false))
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <span className="brand-mark" />
          <h1>Innovation Radar</h1>
        </div>
        <p className="login-sub">
          Orange Business · opportunity spaces. Sign in to continue.
        </p>

        <label className="login-field">
          <span>Username</span>
          <input ref={usernameRef} value={username} autoComplete="username"
                 autoCapitalize="none" spellCheck={false} name="username"
                 onChange={(e) => setUsername(e.target.value)} required />
        </label>

        <label className="login-field">
          <span>Password</span>
          <input type="password" value={password} autoComplete="current-password"
                 name="password" onChange={(e) => setPassword(e.target.value)} required />
        </label>

        {/* Announced, not just shown: a rejection nobody hears is a form that
            appears to have done nothing. */}
        <div className="login-error" role="alert" aria-live="assertive">
          {error ?? ''}
        </div>

        <button type="submit" className="login-submit" disabled={pending || !username || !password}>
          {pending ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="login-note">
          Accounts are created from the command line — <code>radar user add</code>. If you do not
          have one, ask whoever runs the radar.
        </p>
      </form>
    </div>
  )
}

/** Change the signed-in account's password.
 *
 * The current password is asked for even though the session already proves
 * identity, because the session proves the laptop is unlocked and not that the
 * person at it knows the password — and this is the one action that locks its
 * owner out.
 *
 * Every other session for the account ends. That is the point rather than a side
 * effect: the usual reason to change a password is that somebody else might know
 * the old one, and leaving their session alive would make the change cosmetic.
 */
export function PasswordDialog({ user, minLength, onClose, onChanged }: {
  user: User
  minLength: number
  onClose: () => void
  onChanged: (user: User) => void
}) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)
  useFocusTrap(true, ref, onClose)

  // Checked here as well as on the server, because a rule the user meets before
  // pressing the button beats the same rule reported after it.
  const tooShort = next.length > 0 && next.length < minLength
  const mismatch = repeat.length > 0 && next !== repeat
  const ready = current && next.length >= minLength && next === repeat && !pending

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!ready) return
    setPending(true)
    setError(null)
    api.changePassword(current, next)
      .then((result) => { onChanged(result.user); onClose() })
      .catch((exc) => setError(String(exc.message ?? exc)))
      .finally(() => setPending(false))
  }

  return (
    <div className="help-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="help-modal pw-modal" role="dialog" aria-modal="true"
           aria-labelledby="pw-title" tabIndex={-1} ref={ref}>
        <div className="help-head">
          <h3 id="pw-title">Change password</h3>
          <button onClick={onClose}>Close</button>
        </div>
        <form className="help-body" onSubmit={submit}>
          <p>
            Signed in as <b>{user.username}</b>.{' '}
            {user.must_change_password && (
              <span className="pw-warn">
                This account still holds the password the radar shipped with.
              </span>
            )}
          </p>

          <label className="login-field">
            <span>Current password</span>
            <input type="password" value={current} autoComplete="current-password"
                   onChange={(e) => setCurrent(e.target.value)} required />
          </label>

          <label className="login-field">
            <span>New password</span>
            <input type="password" value={next} autoComplete="new-password"
                   onChange={(e) => setNext(e.target.value)} required
                   aria-describedby="pw-rule" aria-invalid={tooShort || undefined} />
            <span className="login-hint" id="pw-rule">
              At least {minLength} characters.
            </span>
          </label>

          <label className="login-field">
            <span>Repeat the new password</span>
            <input type="password" value={repeat} autoComplete="new-password"
                   onChange={(e) => setRepeat(e.target.value)} required
                   aria-invalid={mismatch || undefined} />
          </label>

          <div className="login-error" role="alert" aria-live="assertive">
            {error ?? (mismatch ? 'The two entries do not match.' : '')}
          </div>

          <p className="pw-note">
            Every other session signed in as {user.username} will end. This one will not — you are
            about to prove you know the new password.
          </p>

          <div className="pw-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit" className="login-submit" disabled={!ready}>
              {pending ? 'Changing…' : 'Change password'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
