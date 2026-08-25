/** One line-icon set, drawn rather than imported.
 *
 * Why SVG and not emoji: an emoji is a full-colour picture the theme cannot
 * touch, it renders differently on every platform, and several of the obvious
 * candidates carry meanings this interface has already spent its colour budget
 * on — a red 🔥 beside "Why it is hot now" competes with the reserved status
 * scale, where red means an evidence gap or a crowded field and nothing else.
 * These take `currentColor`, so they inherit the muted heading colour in both
 * themes and stay decorative.
 *
 * Why not an icon library: fifteen icons at ~120 bytes each is smaller than the
 * import, and drawing them here keeps the metrics identical — one viewBox, one
 * stroke width, so a row of headings does not wobble.
 *
 * Every icon is `aria-hidden`. The label beside it is the accessible name, and
 * an icon that repeated it would make a screen reader say everything twice.
 * These decorate a heading that already says what the section is; they never
 * carry meaning on their own.
 */

type IconProps = { className?: string }

function svg(path: React.ReactNode) {
  return function Icon({ className = 'sec-icon' }: IconProps) {
    return (
      <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false"
           fill="none" stroke="currentColor" strokeWidth={1.7}
           strokeLinecap="round" strokeLinejoin="round">
        {path}
      </svg>
    )
  }
}

/* --- filter rail ------------------------------------------------------- */

export const IconSearch = svg(<><circle cx="11" cy="11" r="6" /><path d="m20 20-4.5-4.5" /></>)

/** Horizon — Now / Next / Later is time, and a clock says that without a metaphor. */
export const IconClock = svg(<><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5.2l3.2 2" /></>)

/** Competition — overlap, not a crowd of people: §4.3.3 is about how many
 *  players cover the same ground, which is what two intersecting sets show. */
export const IconVenn = svg(<><circle cx="9" cy="12" r="5.5" /><circle cx="15" cy="12" r="5.5" /></>)

/** Ready to sell — the brief is a document, and that is the whole point of it. */
export const IconDoc = svg(<>
  <path d="M14 3H7a1.6 1.6 0 0 0-1.6 1.6v14.8A1.6 1.6 0 0 0 7 21h10a1.6 1.6 0 0 0 1.6-1.6V7.6z" />
  <path d="M14 3v4.6h4.6M8.6 12.5h6.8M8.6 16.3h4.6" />
</>)

/** Vertical — a sector, drawn as the industry that defines it. */
export const IconBuilding = svg(<>
  <path d="M4 21h16M6 21V6.5l6-3 6 3V21" />
  <path d="M10 11.5h.01M14 11.5h.01M10 15.5h.01M14 15.5h.01" />
</>)

/** Domain — the layer of the portfolio a use case sits in. */
export const IconLayers = svg(<>
  <path d="m12 3 8.5 4.4L12 11.8 3.5 7.4z" /><path d="m3.5 12 8.5 4.4 8.5-4.4" />
  <path d="m3.5 16.6 8.5 4.4 8.5-4.4" />
</>)

/** Persona — the buyer, singular, because that is how the taxonomy names them. */
export const IconPerson = svg(<>
  <circle cx="12" cy="8" r="3.6" /><path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
</>)

export const IconGlobe = svg(<>
  <circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17" />
  <path d="M12 3.5c2.2 2.4 3.4 5.4 3.4 8.5S14.2 18.6 12 21c-2.2-2.4-3.4-5.4-3.4-8.5S9.8 5.9 12 3.5z" />
</>)

/* --- detail sections ---------------------------------------------------- */

/** Why it is hot now. A flame in one stroke weight, not a red emoji. */
export const IconFlame = svg(<>
  <path d="M12 3c.6 3.2-1.4 4.4-2.8 6.2A6.6 6.6 0 0 0 7.7 13a4.3 4.3 0 0 0 8.6 0c0-2.2-1-3.4-2.2-5" />
  <path d="M12 20.5a2.6 2.6 0 0 0 2.6-2.6c0-1.6-2.6-3.4-2.6-3.4s-2.6 1.8-2.6 3.4A2.6 2.6 0 0 0 12 20.5z" />
</>)

/** Market opportunity — a figure with a currency, since §4.3.4 is money. */
export const IconMoney = svg(<>
  <rect x="2.8" y="6" width="18.4" height="12" rx="2" /><circle cx="12" cy="12" r="2.6" />
  <path d="M6 12h.01M18 12h.01" />
</>)

/** Ask & answer — the qualifying questions and the objections. */
export const IconChat = svg(<>
  <path d="M20.5 12.6c0 3.9-3.8 7-8.5 7a9.8 9.8 0 0 1-2.6-.35L4 21l1.3-3.6a6.6 6.6 0 0 1-1.8-4.4c0-3.9 3.8-7 8.5-7s8.5 3.1 8.5 6.6z" />
  <path d="M12 14.4v-.5c0-1 1.7-1.3 1.7-2.7a1.7 1.7 0 0 0-3.4 0M12 16.6h.01" />
</>)

/** Where it delivers value, and for whom — buyers, plural. */
export const IconPeople = svg(<>
  <circle cx="9.5" cy="8.5" r="3.2" /><path d="M3.5 19.5a6 6 0 0 1 12 0" />
  <path d="M16 5.6a3.2 3.2 0 0 1 0 5.8M17 14a6 6 0 0 1 3.5 5.5" />
</>)

/** Can we play, can we win — named Orange assets, drawn as a component. */
export const IconCube = svg(<>
  <path d="m12 2.8 8 4.3v9.8l-8 4.3-8-4.3V7.1z" /><path d="m4 7.1 8 4.3 8-4.3M12 11.4V21" />
</>)

/** Score breakdown — a measured quantity with a needle, not a trend. */
export const IconGauge = svg(<>
  <path d="M4 17.5a8.5 8.5 0 1 1 16 0" /><path d="m12 17.5 4-5" /><circle cx="12" cy="17.5" r="1.1" />
</>)

/** Next action, by role. */
export const IconTarget = svg(<>
  <circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r="0.6" />
</>)

/** Workflow — the stage board, as its columns. */
export const IconBoard = svg(<>
  <rect x="3.2" y="4.5" width="17.6" height="15" rx="1.8" />
  <path d="M9 4.5v15M15 4.5v15" />
</>)

/** Team conviction — several voices, scored. */
export const IconVoices = svg(<>
  <path d="M12 3.6l2.5 5.1 5.6.8-4 4 .9 5.6-5-2.6-5 2.6.9-5.6-4-4 5.6-.8z" />
</>)

/** Evidence over time — momentum is a trend, so it is a line. */
export const IconTrend = svg(<>
  <path d="M3.5 19.5h17" /><path d="m5.5 16 4.2-4.6 3.4 2.8L20 7" /><path d="M16.4 7H20v3.6" />
</>)

/** Is this useful? */
export const IconThumb = svg(<>
  <path d="M7.5 10.5 11 3.5a2.2 2.2 0 0 1 2.2 2.2v3.3h4.6a2 2 0 0 1 2 2.4l-1.4 6.5a2 2 0 0 1-2 1.6H7.5z" />
  <path d="M7.5 10.5v9H5a1.5 1.5 0 0 1-1.5-1.5V12A1.5 1.5 0 0 1 5 10.5z" />
</>)

/** Sources — the cited evidence, each one a link to a dated document. */
export const IconLink = svg(<>
  <path d="M10 13.6a3.6 3.6 0 0 0 5.2.3l2.8-2.8a3.7 3.7 0 0 0-5.2-5.2l-1.6 1.6" />
  <path d="M14 10.4a3.6 3.6 0 0 0-5.2-.3L6 12.9a3.7 3.7 0 0 0 5.2 5.2l1.6-1.6" />
</>)

/** Section id -> icon, so the jump bar and the heading it lands on carry the
 *  same mark. A jump bar whose entries look nothing like their destinations is
 *  a second vocabulary to learn. */
export const SECTION_ICONS: Record<string, (props: IconProps) => JSX.Element> = {
  'why-hot': IconFlame,
  market: IconMoney,
  competition: IconVenn,
  questions: IconChat,
  description: IconDoc,
  value: IconPeople,
  assets: IconCube,
  score: IconGauge,
  horizon: IconClock,
  action: IconTarget,
  workflow: IconBoard,
  conviction: IconVoices,
  timeline: IconTrend,
  feedback: IconThumb,
  sources: IconLink,
}

/* --- the top bar -------------------------------------------------------- *
 *
 * Same viewBox and stroke weight as everything above, because these sit in a
 * row of buttons that are all one height: an icon drawn at a different scale
 * makes its button look mis-set even when the box is identical.
 *
 * Each one is `aria-hidden` like the rest — the button's own text is its name,
 * and where a button has no text (theme, sign out) the name is on the button.
 */

/** Strategist / Innovator — where to point the next quarter's effort. */
export const IconCompass = svg(<>
  <circle cx="12" cy="12" r="8.5" /><path d="m15.2 8.8-1.8 4.6-4.6 1.8 1.8-4.6z" />
</>)

/** Sales — the named-account conversation, drawn as what is being sold. */
export const IconTag = svg(<>
  <path d="M20.2 12.9 12.9 20.2a1.7 1.7 0 0 1-2.4 0l-6.3-6.3a1.7 1.7 0 0 1-.5-1.2V4.9a1.5 1.5 0 0 1 1.5-1.5h7.8c.45 0 .88.18 1.2.5l6 6a1.7 1.7 0 0 1 0 2.4z" />
  <path d="M8.2 8.2h.01" />
</>)

/** Presales / Proposal — the bid being assembled. */
export const IconClipboard = svg(<>
  <path d="M9 4.5H7.4A1.6 1.6 0 0 0 5.8 6.1v13.3A1.6 1.6 0 0 0 7.4 21h9.2a1.6 1.6 0 0 0 1.6-1.6V6.1A1.6 1.6 0 0 0 16.6 4.5H15" />
  <rect x="9" y="3" width="6" height="3.2" rx="1" />
  <path d="M9.2 11.5h5.6M9.2 15.3h3.6" />
</>)

/** Radar — the sweep, not a target: the radar tab is the two-axis plot. */
export const IconRadar = svg(<>
  <path d="M12 3.5a8.5 8.5 0 1 0 8.5 8.5" /><path d="M12 8a4 4 0 1 0 4 4" />
  <path d="M12 12 19 5" /><path d="M18.4 4.2h1.9v1.9" />
</>)

/** List — the ranked rows. */
export const IconList = svg(<>
  <path d="M9 6.5h11M9 12h11M9 17.5h11" />
  <path d="M4.6 6.5h.01M4.6 12h.01M4.6 17.5h.01" />
</>)

/** Analytics — a measured portfolio, so bars rather than a trend line. */
export const IconBars = svg(<>
  <path d="M3.6 20.4h16.8" /><path d="M7 20.4v-6.2M12 20.4V6.8M17 20.4v-9.4" />
</>)

/** White space — the cell nothing has been written into yet. */
export const IconWhitespace = svg(<>
  <rect x="3.4" y="3.4" width="7.2" height="7.2" rx="1.2" />
  <rect x="13.4" y="3.4" width="7.2" height="7.2" rx="1.2" />
  <rect x="3.4" y="13.4" width="7.2" height="7.2" rx="1.2" />
  <path d="M13.4 17h7.2M17 13.4v7.2" strokeDasharray="2 2.2" />
</>)

/** Coverage — how much of the grid has actually been assessed. */
export const IconCoverageGrid = svg(<>
  <rect x="3.4" y="3.4" width="17.2" height="17.2" rx="2" />
  <path d="M3.4 9.6h17.2M9.6 3.4v17.2" />
  <path d="m12.6 15.4 1.9 1.9 3.6-3.9" />
</>)

/** Detail — the reading pane, which is what the compact fallback opens. */
export const IconPanel = svg(<>
  <rect x="3.2" y="4.5" width="17.6" height="15" rx="1.8" /><path d="M12.4 4.5v15" />
  <path d="M15 9.4h3.2M15 13h2.2" />
</>)

/** Generate — synthesis, not creation from nothing: a spark over the corpus. */
export const IconSpark = svg(<>
  <path d="m11 3.4 1.7 4.2 4.2 1.7-4.2 1.7L11 15.2 9.3 11 5.1 9.3l4.2-1.7z" />
  <path d="m18 14.6.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
</>)

/** Planner — five years, so a calendar rather than a route. */
export const IconCalendar = svg(<>
  <rect x="3.4" y="5.2" width="17.2" height="15.4" rx="2" /><path d="M3.4 10h17.2" />
  <path d="M8.2 3.4v3.4M15.8 3.4v3.4" /><path d="M8 14h.01M12 14h.01M16 14h.01M8 17.4h.01M12 17.4h.01" />
</>)

/* Theme. Three states, three marks — a single glyph that only changes meaning
   is a control you have to click to understand. */
export const IconSun = svg(<>
  <circle cx="12" cy="12" r="4" />
  <path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7" />
</>)
export const IconMoon = svg(<>
  <path d="M20 14.2A8.4 8.4 0 0 1 9.8 4 8.5 8.5 0 1 0 20 14.2z" />
</>)
export const IconAutoTheme = svg(<>
  <circle cx="12" cy="12" r="8.5" /><path d="M12 3.5v17a8.5 8.5 0 0 0 0-17z" fill="currentColor" stroke="none" />
</>)

/** Sign out — the door, with the direction of travel. */
export const IconSignOut = svg(<>
  <path d="M14.5 4.5H6.6A1.6 1.6 0 0 0 5 6.1v11.8a1.6 1.6 0 0 0 1.6 1.6h7.9" />
  <path d="M15.4 8.4 19 12l-3.6 3.6M19 12h-8.6" />
</>)
