/* Country names for the cluster memberships.
 *
 * "DACH" and "Benelux" are opaque unless you already know them, and the whole
 * point of showing a cluster is that the reader knows what is inside it. The
 * names come from the platform's own CLDR data rather than a table we maintain:
 * 186 country names is a table that goes stale, and the browser already has it.
 */

const display = (() => {
  try {
    return new Intl.DisplayNames(['en'], { type: 'region' })
  } catch {
    // Older engines, or a locale the runtime does not carry. Falling back to the
    // ISO code is worse than a name and much better than an empty line.
    return null
  }
})()

export function countryName(code: string): string {
  if (!display) return code
  try {
    return display.of(code) ?? code
  } catch {
    // User-assigned codes (XK) and anything malformed land here.
    return code
  }
}

/** Spelled-out membership, with a short form for lists and a full one for the
 *  tooltip. Eastern Europe carries twenty countries; printing all of them in a
 *  filter row would bury the cluster name it is supposed to explain. */
export function countryNames(codes: string[], max = 4): { short: string; full: string } {
  const names = codes.map(countryName)
  const full = names.join(', ')
  const short = names.length <= max
    ? full
    : `${names.slice(0, max).join(', ')} + ${names.length - max} more`
  return { short, full }
}
