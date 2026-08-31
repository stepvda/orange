# Frontend and deployment

## Frontend

React + Vite + TypeScript, no chart library — the radar is hand-drawn SVG
because the encoding is specific to this product.

**The radar view** (§4.9): angular sector = business domain, radial distance =
time horizon (Now at the centre), marker **size** = attractiveness, marker
**colour** = right to win. Position carries identity, so no categorical hues are
needed. Colour encodes a magnitude, so it uses a single-hue sequential ramp,
validated for lightness monotonicity, adjacent step separation, single hue and
light-end contrast against its own surface in **both** light and dark mode.
Evidence-gap marks carry a `!` glyph as well as a border, so the warning never
depends on colour alone.

**The full-screen view of a space** is the same content with the panes out of the
way, in four tabs — the space, the competitors, the brief, the pre-sales pack.
That is the order the questions arrive: what is this, who else is here, what do
I send, and what comes after the meeting. The three-pane layout is right for
working _through_ the radar — filter, scan, open, compare, move on — and wrong
for the moment somebody actually reads a space, because §4.9 gives the detail
pane ten sections and reading them in a 420px column beside a chart nobody is
looking at any more is the narrowest possible view of the longest content in the
interface. The pre-sales tab is last on purpose: putting it before the brief
would suggest a team should build a tender response before they have had the
first meeting. It lists all twelve pieces whether or not anything has been
built, because what _could_ be produced is as much of the answer as what has
been, and a screen that starts empty is one nobody presses a button on.

**The Generate screen opens with a conversation, not a text box.** The box asked
for one thing and gave one piece of feedback — a character count, which is the
only failure that did not matter. An opportunity space is a vertical × use case
× technology plus a buyer's problem and a place, and somebody who knows their
market but not this taxonomy under-specified two of those every time; they found
out minutes later, from a run that created nothing. The assistant interviews
instead, with the corpus in front of it, and shows what each turn retrieved —
publisher, date and cosine — beside the conversation. The Generate button is
enabled by the corpus rather than by the assistant's opinion of itself, and
where the two disagree the screen says so in either direction. The parameters
route is still there for somebody who does know the taxonomy, and it shows the
spaces that _already_ match before spending a run on rediscovering them.

**The brief view** is the middle pane rendering the PDF inline, with Download,
Regenerate and a staleness warning when the topic has moved past the version the
brief was built against. Showing it beside the radar rather than only offering a
download is what makes anyone notice it is out of date.

**Market opportunity and competition** appear in the detail pane as the working,
not just the number: TAM/SAM/SOM with their ranges, every factor with its source,
year and basis badge, the caveats behind a disclosure, and per competitor the
signals that name them.

**Signing in** is a screen of its own, rendered instead of the radar rather than
over it: every panel behind it opens by fetching, and mounting them for a
signed-out visitor means a dozen requests that all answer `401`, painting the
error state of eight panels behind a login form. One refusal message covers both
an unknown account and a wrong password — a sign-in form that distinguishes them
is a staff directory with a slow interface.

**Deleting a space** sits at the bottom of the detail pane, behind its own rule,
because every other control there is reversible and that one is not. The dialog
asks the server what would go and reads the answer out first: thirteen tables
point at a space, and "are you sure?" over a number nobody was shown is not a
confirmation. It also says what is _not_ lost — the signals are shared evidence
and stay — and that a later refresh meeting the same taxonomy triple will
synthesise the space again, because identity is the triple (DR-03) and deleting
is a statement about the corpus as it stands, not a permanent veto.

Deep links work: `?topic=OS012&role=presales&theme=dark`, and `?tab=brief` opens
the brief for the selected space.

---

## Deployment

The radar runs as a single Azure App Service: one process serving the read API
and the built React bundle from the same origin, which is what the CORS list in
`api.py` was always scoped for.

```bash
./scripts/deploy-azure.sh          # build, package, provision if needed, push
```

|                |                                                                                       |
| -------------- | ------------------------------------------------------------------------------------- |
| Subscription   | Azure for Students (`9ca89421…`), tenant `33ac9060…`                                  |
| Resource group | `rg-railpulse-cloud`                                                                  |
| Region         | France Central                                                                        |
| Plan / app     | `plan-railpulse-cdb4ce` (F1, Linux, shared) / `web-orange-radar-1521f5`               |
| Runtime        | Python 3.13, `python3 -m uvicorn main:app` (no script, no absolute paths — see below) |

Three deployment decisions worth recording, because each is a constraint someone
will otherwise rediscover:

**Where it runs.** The subscription carries an `Allowed resource deployment
regions` policy — Italy North, France Central, Germany West Central, Poland
Central, Spain Central, all EU, which suits a product whose strategic frame is
sovereignty. The radar shares `plan-railpulse-cdb4ce` with the RailPulse app: a
Free plan hosts up to 21 sites and the two draw on the same 60 CPU-minutes a day.
Giving the radar its own plan means paying for one — B1 is about USD 13/month:

    RG=rg-orange-radar PLAN=plan-orange-radar SKU=B1 ./scripts/deploy-azure.sh

**Nothing may raise at import, and no bash wrapper.** These two are one lesson.
A container that exits is restarted, fifteen restarts exhaust the Free plan's
`WP stop requests` quota, and that quota **also disables Kudu** — so a crash loop
erases the logs that would explain it. Five deployments failed that way before
the design changed to make it impossible:

- The startup command names **no absolute path and no console script**:
  `python3 -m uvicorn main:app`. This is the one that cost five deployments, and
  the cause is not obvious. App Service does not run the deployed tree in place.
  Oryx builds it, compresses the result to `output.tar.zst`, and on _every_
  container start extracts that tarball to a fresh `/tmp/<hash>` which becomes
  the working directory. `/home/site/wwwroot` holds the tarball and nothing
  else, and the extraction path changes with each deploy — so no absolute path
  into `wwwroot` is ever valid at runtime, not for a startup script, not for
  `PYTHONPATH`, not for a module. Every such command exits **127** before
  printing anything. `python3 -m` resolves through `PYTHONPATH` (which Oryx
  points at the extracted virtualenv) rather than `PATH` (which it does not
  extend), and `main.py` puts its own sibling `src` on `sys.path`, so both
  resolve relative to wherever the tarball happened to land.
- Everything that wrapper used to do — seeding `/home/data/radar.db` from the
  package, converting its journal mode, copying the briefs — is in
  `radar/bootstrap.py`, which runs inside the app, inside the venv, and catches
  everything it can hit.
- `api.py` no longer dies when the database is unusable. It records the error
  and `/healthz` answers **503 with the reason**, so a bad deployment describes
  itself over HTTPS instead of disappearing.
  **What a redeploy replaces, and what it never touches.** The database is seeded
  onto `/home` once and then _not_ replaced, so a deployment cannot discard the
  feedback and workflow decisions production accumulated. That protection is right,
  and taken alone it is also why 62 briefs once sat on disk that nobody could open:
  the PDFs shipped, the rows that make them visible did not. So `bootstrap` brings
  `CONTENT_TABLES` forward from the package — the topics themselves plus
  `topic_descriptions`, `topic_briefs`, `topic_competition` and `market_sizes`.

Not unconditionally, and this is the part worth reading. An earlier version of
this took those tables wholesale on the strength of a comment claiming the UI
never writes them. That was false: `POST /api/topics/{id}/description|brief|
market-size|competition` all write them, and the shipped UI has a **Regenerate**
button wired to each. Taking them wholesale would have silently rolled back work
a curator paid a model call for, and charged them to do it twice. Every row is
therefore compared on its own timestamp and the newer one wins — the package is
authoritative for content it refreshed, production for anything regenerated
since. The PDFs follow the same rule from the other end: `content_hash` is the
SHA-256 of the file a row was written for, so the row decides which PDF belongs
on disk, and a brief regenerated in production is recognised and left alone.

Topics travel _with_ their content rather than being frozen, because
`opportunity_spaces.version` is what `brief_for_topic` compares against: shipping
new briefs against frozen topics flags every one of them "the topic has been
refreshed since". They are taken wholesale — the pipeline is their only writer.
`PRAGMA foreign_keys = OFF` is load-bearing here, not incidental: `INSERT OR
REPLACE` is a delete followed by an insert, and these tables are the parents of
`workflow_state` and `feedback` through `ON DELETE CASCADE`.

The sync is keyed on a SHA-256 of the packaged database and skipped when it
matches the marker in `/home/data/.content-fingerprint` — the container cold
starts far more often than it is deployed — and the marker is written only when
every table applied, so a partial sync is retried rather than recorded as done.
It is wrapped in its own `except`: stale content is worth serving, a crash loop
is not. `tests/test_bootstrap_sync.py` pins all of it, including the case that
matters most — a curator regenerates a brief, the next deploy lands, and their
work is still there.

- Briefs are resolved by **filename against the configured directory**, not by
  the absolute path recorded in `topic_briefs.path`. That column records the
  machine that _built_ the PDF — a laptop the server has never seen — so taken
  literally every brief 404s in Azure and the UI reports that none were ever
  generated. `resolve_brief()` falls back to `RADAR_BRIEF_DIR`, and both the
  file route and the metadata payload go through it so they cannot disagree.

**Reading the logs when Kudu is 403.** The deadlock above is escapable without
waiting an hour. Point the startup command at a static server over the whole
persisted tree —

    az webapp config set -g $RG -n $APP \
      --startup-file "python3 -m http.server 8000 --directory /home"

— and the container stays up (so the restart quota stops draining) while
`/LogFiles/*_docker.log` becomes readable over plain HTTPS. That is what finally
produced the `exit code 127` and the `can't open file` line above, after five
attempts spent guessing. Reach for it early, not late.

**SQLite cannot use WAL on `/home`.** This one cost a night. `/home` is the only
path that survives a restart on Linux App Service, and it is an SMB mount:
Azure Files. WAL needs shared memory that SMB does not provide, so opening a WAL
database there fails — and because `api.py` calls `init_schema()` at import, the
failure takes the worker with it. The platform restarts the worker, the worker
fails again, and after fifteen restarts the plan's hourly `WP stop requests`
quota is spent. At that point the app returns 403 `QuotaExceeded`, **and so does
Kudu**, so the logs that would explain it are unreadable until the quota resets.

The symptom is easy to misread as a Free-tier limitation — a second app on the
plan was even stopped to "free a slot", which changed nothing: the F1 plan runs
both apps side by side. It is not a resource limit — CPU sat at
0% of its daily allowance throughout. `db.py` therefore takes
`RADAR_SQLITE_JOURNAL_MODE` (default `WAL`, set to `DELETE` in App Service),
`radar.bootstrap` converts the seeded copy before its first write, and writes its own log to
`/home/LogFiles/radar-startup.log`, which survives a container that does not.

**What is not deployed.** The serving package carries no pipeline dependencies:
`radar.api` imports scikit-learn, sentence-transformers and the OpenAI client
only inside the functions that need them, so a serving instance never loads
torch. That is a 28 MB package instead of a multi-gigabyte one, and on the Free
tier it is the difference between starting and not. Discovery stays a local
batch job against the same SQLite file; deploying is the publish step.

**What persists.** `/home` is the only path that survives a restart or a
redeploy on Linux App Service, so the database and generated briefs live in
`/home/data`. `radar.bootstrap` seeds it from the package on first boot and then
leaves it alone — feedback, assessments, descriptions and briefs created in
production are not thrown away by the next push. The replay archive
(`raw_items`) is dropped from the serving copy: it exists so the pipeline can be
re-run as of a past date (DR-14, FR-35), which is not something the API does,
and it is half the file. Every citation still resolves.

**Secrets** are App Settings, read from the local `.env` at deploy time and never
written into the package. The `.env` itself is excluded.

**If the site answers 403 and the portal says `QuotaExceeded`,** it is almost
certainly a crash loop rather than a resource limit. Check which quota before
assuming it is CPU:

```bash
az rest --method get --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/\
rg-railpulse-cloud/providers/Microsoft.Web/serverfarms/plan-railpulse-cdb4ce/usages?api-version=2022-03-01"
```

During this deployment the answer was `WP stop requests: 41 / 15` while CPU sat
at 0% — a container failing to boot, restarted until the cap was reached. It
clears on the hour. Redeploying to fix it makes it worse: stop the app first,
which ends the loop, then read `/home/LogFiles/radar-startup.log` once the quota
allows Kudu to answer again.

### Before this goes anywhere real

The app now requires a sign-in (`src/radar/auth.py`). Every `/api` path is behind
a session; the built bundle and `/healthz` are not, because the login screen has
to load before anyone can sign in and a liveness probe that answers `401` makes
every deployment look unhealthy. The session is an `HttpOnly`, `SameSite=Lax`
cookie whose value is stored only as a SHA-256, and passwords are PBKDF2-HMAC-SHA256
verifiers at OWASP's current iteration count — so a copy of the database file is
neither a set of passwords nor a set of live logins, which matters when the
database _is_ a file on a share.

Two things that were true before it and are still worth acting on:

- **The shipped account is `orange` / `orange`.** It exists so a fresh database
  is usable without a shell, it is flagged `must_change_password`, and the
  interface carries a banner until it is changed. Change it on first sign-in.
- The generation endpoints (`POST /api/topics/{id}/description`, `POST
/api/topics/{id}/brief`) call the configured model with the deployed key, so
  anyone who _can_ sign in can spend it. The key in question was shared in
  plaintext over chat during development and should be rotated regardless.

Defence in depth is still worth having — a password is one factor, and the
platform can add a second in one command:

```bash
# Only your address may reach it
az webapp config access-restriction add -g rg-orange-radar -n web-orange-radar-1521f5 \
  --rule-name office --priority 100 --action Allow --ip-address "$(curl -s ifconfig.me)/32"

# Or require a Microsoft Entra sign-in from the tenant
az webapp auth update -g rg-orange-radar -n web-orange-radar-1521f5 \
  --enabled true --action RedirectToLoginPage --redirect-provider AzureActiveDirectory
```

---


