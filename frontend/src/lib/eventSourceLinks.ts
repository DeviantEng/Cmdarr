/**
 * Pick one display URL per provider for Artist Events.
 *
 * Ticketmaster often returns the same tour/package event id with multiple
 * marketing URLs (ticketmaster.com per-artist slugs, on.fgtix.com shortlinks).
 * We prefer a readable ticketmaster.com link that matches the Lidarr artist,
 * then primary TM domains, then resellers / tracking links.
 */

const TOKEN_RE = /[a-z0-9']+/gi;

function tokensForArtist(artistName: string): string[] {
  const m = artistName.toLowerCase().match(TOKEN_RE);
  return m ? m.filter((t) => t.length > 0) : [];
}

/** Hyphen slug as TM uses in paths, e.g. "lorna-shore", "the-fall-of-troy". */
function hyphenSlug(tokens: string[]): string {
  return tokens.join("-");
}

function artistSlugScore(pathLower: string, artistName: string): number {
  const tokens = tokensForArtist(artistName);
  if (tokens.length === 0) return 0;
  const full = hyphenSlug(tokens);
  if (full && pathLower.includes(full)) return 400;
  if (tokens[0] === "the" && tokens.length > 1) {
    const rest = hyphenSlug(tokens.slice(1));
    if (rest && pathLower.includes(rest)) return 380;
  }
  // Rare short names: require a longer token to avoid noise
  const distinctive = tokens.filter((t) => t.length >= 4);
  for (const t of distinctive) {
    if (pathLower.includes(t)) return 120;
  }
  return 0;
}

function domainScore(hostname: string): number {
  const h = hostname.toLowerCase();
  if (h.endsWith("ticketmaster.com")) return 100;
  if (h.endsWith("livenation.com")) return 88;
  if (h.endsWith("ticketweb.com")) return 72;
  if (h.endsWith("axs.com")) return 65;
  if (h.endsWith("etix.com")) return 58;
  if (h.endsWith("universe.com")) return 52;
  if (h.includes("fgtix.com")) return 6;
  if (h.endsWith("gracelandlive.com")) return 44;
  return 36;
}

function scoreSourceUrl(url: string, artistName: string): number {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return -1e9;
  }
  const path = `${parsed.pathname}${parsed.search}`.toLowerCase();
  let score = domainScore(parsed.hostname);
  score += artistSlugScore(path, artistName);
  if (path.includes("/event/")) score += 35;
  if (path.includes("/trk/")) score -= 80;
  if (path.includes("/venue/")) score += 8;
  return score;
}

/**
 * Choose the best URL from several candidates for the same provider.
 */
export function pickBestSourceUrl(urls: string[], artistName: string): string | null {
  const uniq = [...new Set(urls.filter(Boolean))];
  if (uniq.length === 0) return null;
  if (uniq.length === 1) return uniq[0]!;
  let best = uniq[0]!;
  let bestScore = scoreSourceUrl(best, artistName);
  for (let i = 1; i < uniq.length; i++) {
    const u = uniq[i]!;
    const s = scoreSourceUrl(u, artistName);
    if (s > bestScore || (s === bestScore && u.length > best.length)) {
      best = u;
      bestScore = s;
    }
  }
  return best;
}

export type SourceLinkRow = { provider: string; url: string | null };

/**
 * One row per provider: collapse duplicate URLs and pick the best URL when several exist.
 */
function dedupeUrlsByBasePath(urls: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const u of urls) {
    const key = u.split("?")[0];
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(u);
  }
  return out;
}

export function collapseSourceLinksForDisplay(
  rows: SourceLinkRow[],
  artistName: string
): SourceLinkRow[] {
  const order: string[] = [];
  const byProvider = new Map<string, string[]>();

  for (const row of rows) {
    if (!byProvider.has(row.provider)) {
      byProvider.set(row.provider, []);
      order.push(row.provider);
    }
    if (row.url) {
      byProvider.get(row.provider)!.push(row.url);
    }
  }

  return order.map((provider) => {
    const urls = dedupeUrlsByBasePath(byProvider.get(provider) || []);
    const url = urls.length === 0 ? null : pickBestSourceUrl(urls, artistName);
    return { provider, url };
  });
}
