# Cmdarr Frontend

Modern React frontend for Cmdarr built with TypeScript, Vite, TailwindCSS, and shadcn/ui.

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TailwindCSS 4** - Utility-first CSS framework
- **shadcn/ui** - Accessible component library
- **React Router** - Client-side routing
- **Sonner** - Toast notifications
- **WebSocket** - Real-time updates

## Development

### Prerequisites

- Node.js 18+ and npm
- FastAPI backend running on http://localhost:8080

### Setup

```bash
cd frontend
npm install
```

### Development Server

```bash
npm run dev
```

The dev server will start on http://localhost:5173 with:
- Hot module replacement
- Proxy to FastAPI backend (http://localhost:8080)
- WebSocket proxy for real-time updates

### Build for Production

```bash
npm run build
```

Builds the app to the `dist/` directory, which FastAPI will serve in production.

### Preview Production Build

```bash
npm run preview
```

## Features

### Commands Page
- Card and table view modes
- Real-time status updates via WebSocket
- Advanced filtering (status, type, search)
- Sorting by name, last run, status
- Command execution, editing, and management
- Properly positioned "New Command" button (finally!)

### Configuration Page
- Tabbed interface organized by category:
  - Application (logging, web, output)
  - Music Sources (LastFM, ListenBrainz, Spotify, etc.)
  - Media Servers (Plex, Jellyfin)
  - Music Management (Lidarr)
  - Performance (cache, library, commands)
- Compact form design (no more massive boxes!)
- Search across all settings
- Connectivity testing
- Real-time save tracking

### Status Page
- System health monitoring
- Uptime tracking
- Database and configuration status
- API endpoint information

### Dark Mode
- Automatic dark mode support
- Persisted user preference
- System preference detection
- Smooth transitions

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/              # shadcn/ui components
│   │   └── Layout.tsx       # App layout with navigation
│   ├── lib/
│   │   ├── api.ts           # FastAPI client
│   │   ├── websocket.ts     # WebSocket client
│   │   ├── types.ts         # TypeScript types
│   │   ├── utils.ts         # Utility functions
│   │   └── theme.tsx        # Theme provider
│   ├── pages/
│   │   ├── Commands.tsx     # Commands page
│   │   ├── Config.tsx       # Configuration page
│   │   ├── Status.tsx       # Status page
│   │   └── ImportLists.tsx  # Import lists page
│   ├── App.tsx              # Main app component
│   ├── main.tsx             # Entry point
│   └── index.css            # Global styles
├── public/                  # Static assets
├── components.json          # shadcn/ui configuration
├── tailwind.config.js       # Tailwind configuration
├── vite.config.ts           # Vite configuration
└── tsconfig.json            # TypeScript configuration
```

## API Integration

The frontend communicates with the FastAPI backend through:

1. **REST API** - CRUD operations for commands and configuration
2. **WebSocket** - Real-time command status updates
3. **Proxy** - Development proxy configuration in vite.config.ts

## Design Philosophy

- **Minimal & Clean** - Reduced visual clutter, compact layouts
- **Type-Safe** - Full TypeScript coverage
- **Accessible** - Built on Radix UI primitives
- **Responsive** - Mobile-first design with Tailwind
- **Fast** - Optimized build with code splitting

## Troubleshooting

### Port 5173 already in use
```bash
lsof -ti:5173 | xargs kill -9
```

### Build fails
```bash
rm -rf node_modules dist
npm install
npm run build
```

### WebSocket connection issues
Ensure FastAPI backend is running on http://localhost:8080
