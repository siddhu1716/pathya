# Pathya Frontend

Phone-first React app for Pathya: family nutrition, from a phone call to the plate.
See the [project README](../README.md) for the full feature set and backend setup.

## Features

- Home, Family, Meals, Orders and More navigation.
- Family profiles, personal targets, food logs and medicine reminders.
- One household menu with a plate per person.
- Browser calls and camera capture.
- Swiggy Instamart order cards, with Zepto as a fallback for unavailable items.
- Human approval before orders or prescription reminders are committed.

There is no scraping or price comparison. `DRY_RUN=1` is the backend default.

## Stack

React 18, TypeScript, Vite, Tailwind CSS, Radix UI and React Query.
The interface is dark and phone-first, with reduced-motion support.

## Development

Run the FastAPI backend on port 8000 as described in the project README.
From this directory:

```bash
npm install
npm run dev
```

Vite runs on port 5173 and proxies `/api` and `/calls` to the backend.

## Build and checks

```bash
npm run build
npx tsc --noEmit -p tsconfig.app.json
npm run lint
```

The production build is written to `dist/` and served by FastAPI.

## Connecting a separately hosted frontend

The API uses the same origin by default. Set `VITE_API_BASE` at build time for a
different backend, or open the app with `?server=https://your-server&key=...`.
The server and key are remembered on that device. Never commit keys.
Browser calls require HTTPS and microphone permission.

## Acknowledgments

- Radix UI for accessible component primitives.
- Tailwind CSS for utility-first styling.
- React Query for data fetching.
- Lucide React for icons.