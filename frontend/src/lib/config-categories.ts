export type ConfigCategoryGroup = {
  slug: string;
  name: string;
  categories: string[];
};

export const configCategoryGroups: ConfigCategoryGroup[] = [
  {
    slug: "application",
    name: "Application",
    categories: ["logging", "web", "output", "pretty", "application"],
  },
  {
    slug: "music-sources",
    name: "Music Sources",
    categories: ["lastfm", "setlistfm", "listenbrainz", "musicbrainz", "spotify", "deezer"],
  },
  {
    slug: "event-sources",
    name: "Event Sources",
    categories: ["artist_events"],
  },
  {
    slug: "media-servers",
    name: "Media Servers",
    categories: ["plex", "jellyfin"],
  },
  {
    slug: "music-management",
    name: "Music Management",
    categories: ["lidarr"],
  },
  {
    slug: "performance",
    name: "Performance",
    categories: ["cache", "library", "commands"],
  },
  {
    slug: "scheduler",
    name: "Scheduler",
    categories: ["scheduler"],
  },
];

export function getConfigCategoryGroup(slug: string): ConfigCategoryGroup | undefined {
  return configCategoryGroups.find((g) => g.slug === slug);
}

/** Legacy tab values used by classic Config page (`group.name.toLowerCase()`). */
export const legacyConfigCategoryGroups = configCategoryGroups.map((g) => ({
  name: g.name,
  icon: legacyIconForSlug(g.slug),
  categories: g.categories,
  tabValue: g.name.toLowerCase(),
}));

function legacyIconForSlug(slug: string): string {
  const icons: Record<string, string> = {
    application: "⚙️",
    "music-sources": "🎵",
    "event-sources": "🎫",
    "media-servers": "📺",
    "music-management": "🎯",
    performance: "⚡",
    scheduler: "🕐",
  };
  return icons[slug] ?? "⚙️";
}

const MEDIA_SERVER_ORDER: Record<string, number> = {
  PLEX_CLIENT_ENABLED: 0,
  PLEX_URL: 1,
  PLEX_TOKEN: 2,
  PLEX_TIMEOUT: 3,
  PLEX_IGNORE_TLS: 4,
  PLEX_LIBRARY_NAME: 5,
  LIBRARY_CACHE_PLEX_ENABLED: 6,
  LIBRARY_CACHE_PLEX_TTL_DAYS: 7,
  LIBRARY_CACHE_PLEX_USER_DISABLED: 8,
  JELLYFIN_CLIENT_ENABLED: 10,
  JELLYFIN_URL: 11,
  JELLYFIN_TOKEN: 12,
  JELLYFIN_USER_ID: 13,
  JELLYFIN_TIMEOUT: 14,
  JELLYFIN_IGNORE_TLS: 15,
  JELLYFIN_LIBRARY_NAME: 16,
  LIBRARY_CACHE_JELLYFIN_ENABLED: 17,
  LIBRARY_CACHE_JELLYFIN_TTL_DAYS: 18,
  LIBRARY_CACHE_JELLYFIN_USER_DISABLED: 19,
};

export function filterSettingsForCategories<T extends { category: string; key: string }>(
  settings: T[],
  categories: string[]
): T[] {
  const list = settings.filter((s) => categories.includes(s.category));
  if (categories.includes("plex") && categories.includes("jellyfin")) {
    return [...list].sort((a, b) => {
      const orderA = MEDIA_SERVER_ORDER[a.key] ?? 999;
      const orderB = MEDIA_SERVER_ORDER[b.key] ?? 999;
      return orderA - orderB;
    });
  }
  return list;
}
