import type { LucideIcon } from "lucide-react";
import {
  CalendarDays,
  Cog,
  Disc3,
  Gauge,
  Import,
  ListMusic,
  Monitor,
  Settings2,
  Timer,
  Zap,
  BarChart3,
  Database,
} from "lucide-react";
import { configCategoryGroups } from "@/lib/config-categories";

export type ArrNavLink = {
  path: string;
  label: string;
  icon: LucideIcon;
  /** Match only exact path (for index routes). */
  end?: boolean;
};

export type ArrNavSection = {
  id: string;
  label: string;
  pathPrefix: string;
  icon: LucideIcon;
  items: ArrNavLink[];
};

export const arrPrimaryNav: ArrNavLink[] = [
  { path: "/", label: "Commands", icon: ListMusic, end: true },
  { path: "/new-releases", label: "New Releases", icon: Disc3 },
  { path: "/events", label: "Artist Events", icon: CalendarDays },
  { path: "/import-lists", label: "Import Lists", icon: Import },
];

const settingsIcons: Record<string, LucideIcon> = {
  application: Settings2,
  "music-sources": Disc3,
  "event-sources": CalendarDays,
  "media-servers": Monitor,
  "music-management": Cog,
  performance: Zap,
  scheduler: Timer,
};

export const arrSettingsNav: ArrNavLink[] = configCategoryGroups.map((group) => ({
  path: `/settings/${group.slug}`,
  label: group.name,
  icon: settingsIcons[group.slug] ?? Settings2,
}));

export const arrSystemNav: ArrNavLink[] = [
  { path: "/system/status", label: "Status", icon: Gauge },
  { path: "/system/library-cache", label: "Library Cache", icon: Database },
  { path: "/system/artist-events", label: "Artist Events", icon: CalendarDays },
  { path: "/system/new-releases", label: "New Releases", icon: BarChart3 },
];

export const arrNavSections: ArrNavSection[] = [
  {
    id: "settings",
    label: "Settings",
    pathPrefix: "/settings",
    icon: Settings2,
    items: arrSettingsNav,
  },
  {
    id: "system",
    label: "System",
    pathPrefix: "/system",
    icon: Gauge,
    items: arrSystemNav,
  },
];

export const arrSettingsSections = configCategoryGroups.map((group) => ({
  slug: group.slug,
  label: group.name,
  description: settingsSectionDescription(group.slug),
}));

function settingsSectionDescription(slug: string): string {
  const descriptions: Record<string, string> = {
    application: "Logging, web server, and general application options.",
    "music-sources": "Last.fm, Spotify, Deezer, MusicBrainz, ListenBrainz, and related API keys.",
    "event-sources": "Ticketmaster, SeatGeek, Deezer events, and artist event refresh.",
    "media-servers": "Plex and Jellyfin connection settings.",
    "music-management": "Lidarr integration and library paths.",
    performance: "Cache, library sync, and command execution tuning.",
    scheduler: "Background job scheduling intervals.",
  };
  return descriptions[slug] ?? "Configure Cmdarr settings for this section.";
}

export function arrPageTitle(pathname: string): string {
  const settingsMatch = arrSettingsNav.find((item) => pathname.startsWith(item.path));
  if (settingsMatch) return settingsMatch.label;

  const systemMatch = arrSystemNav.find((item) => pathname.startsWith(item.path));
  if (systemMatch) return systemMatch.label;

  const primaryMatch = arrPrimaryNav.find((item) =>
    item.end ? pathname === item.path : pathname.startsWith(item.path)
  );
  if (primaryMatch) return primaryMatch.label;

  if (pathname.startsWith("/settings")) return "Settings";
  if (pathname.startsWith("/system")) return "System";

  return "Cmdarr";
}
