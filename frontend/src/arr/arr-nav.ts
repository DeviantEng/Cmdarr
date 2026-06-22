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
} from "lucide-react";

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
  items: ArrNavLink[];
};

export const arrPrimaryNav: ArrNavLink[] = [
  { path: "/", label: "Commands", icon: ListMusic, end: true },
  { path: "/new-releases", label: "New Releases", icon: Disc3 },
  { path: "/events", label: "Artist Events", icon: CalendarDays },
  { path: "/import-lists", label: "Import Lists", icon: Import },
];

export const arrSettingsNav: ArrNavLink[] = [
  { path: "/settings/application", label: "Application", icon: Settings2 },
  { path: "/settings/music-sources", label: "Music Sources", icon: Disc3 },
  { path: "/settings/event-sources", label: "Event Sources", icon: CalendarDays },
  { path: "/settings/media-servers", label: "Media Servers", icon: Monitor },
  { path: "/settings/music-management", label: "Music Management", icon: Cog },
  { path: "/settings/performance", label: "Performance", icon: Zap },
  { path: "/settings/scheduler", label: "Scheduler", icon: Timer },
];

export const arrSystemNav: ArrNavLink[] = [
  { path: "/system/status", label: "Status", icon: Gauge },
];

export const arrNavSections: ArrNavSection[] = [
  { id: "settings", label: "Settings", items: arrSettingsNav },
  { id: "system", label: "System", items: arrSystemNav },
];

export const arrSettingsSections = arrSettingsNav.map((item) => ({
  slug: item.path.replace("/settings/", ""),
  label: item.label,
  description: settingsSectionDescription(item.path.replace("/settings/", "")),
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
  const all = [...arrPrimaryNav, ...arrSettingsNav, ...arrSystemNav];
  const match = all.find((item) =>
    item.end ? pathname === item.path : pathname.startsWith(item.path)
  );
  return match?.label ?? "Cmdarr";
}
