# Cmdarr Frontend

React SPA for Cmdarr — TypeScript, Vite, Tailwind CSS, and shadcn/ui — with a Sonarr-style (\*arr) shell.

## Tech Stack

- **React 19** — UI library
- **TypeScript** — Type safety
- **Vite** — Build tool and dev server
- **Tailwind CSS 4** — Utility-first CSS
- **shadcn/ui** — Accessible component primitives
- **React Router** — Client-side routing
- **Sonner** — Toast notifications

## Development

### Prerequisites

- Node.js 24+ and npm (see repo `.nvmrc`)
- FastAPI backend on http://localhost:8080

### Setup

```bash
cd frontend
npm install
```

### Development Server

```bash
npm run dev
```

Dev server on http://localhost:5173 with HMR and a proxy to the FastAPI backend.

### Build / Preview

```bash
npm run build
npm run preview
```

Production assets go to `dist/`, served by FastAPI.

## App structure

The UI is a single \*arr shell (sidebar + header). Shared page logic lives under `pages/`; shell wrappers and navigation live under `arr/`.

| Route                             | Purpose                                              |
| --------------------------------- | ---------------------------------------------------- |
| `/commands`                       | Command list, enable/run                             |
| `/commands/add`                   | Add command                                          |
| `/commands/history`               | Execution history                                    |
| `/new-releases`                   | New Release Discovery                                |
| `/events`                         | Artist events                                        |
| `/discovery`, `/discovery/lastfm` | Discovery hub + Last.fm                              |
| `/import-lists`                   | Lidarr import list URLs                              |
| `/settings/:section`              | Configuration                                        |
| `/system/*`                       | Status KPIs, library cache, Lidarr maintenance, etc. |

Bookmark redirects: `/` → `/commands`, `/config` → settings, `/status` → `/system/status`.

```
frontend/
├── src/
│   ├── arr/                 # Shell layout, nav, route wrappers
│   ├── components/          # Shared UI (dialogs, command edit, shadcn)
│   ├── pages/               # Shared page implementations
│   ├── hooks/
│   ├── lib/                 # API client, theme, helpers
│   ├── App.tsx
│   └── main.tsx
├── public/
├── vite.config.ts
└── package.json
```

## API Integration

- **REST** — Commands, config, status, discovery, new releases, import lists
- **Dev proxy** — Vite proxies `/api` (and related paths) to FastAPI

## Dark Mode

Theme preference is stored in `localStorage` (`cmdarr-ui-theme`) and toggled from the header.
