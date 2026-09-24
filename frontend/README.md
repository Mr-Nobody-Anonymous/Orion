This is Orion's [Next.js](https://nextjs.org) Mission Control frontend.

## Getting Started

Install dependencies and run the development server:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Orion API setup

The frontend calls the API and market WebSocket through the same origin
(`/api/v1`). In development, configure your reverse proxy (or Next.js hosting
layer) to forward `/api/v1/*` to the Orion backend and preserve WebSocket
upgrades. The WebSocket client automatically uses `ws` for HTTP pages and
`wss` for HTTPS pages, so no environment-specific URL is required in the
frontend.

The backend API exposes its routes under `/api/v1`; start it before using
pages that load live data. Do not hard-code a backend host or port in client
code.

Useful checks:

```bash
npm run lint
npx tsc --noEmit
npm run build
```

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts)
to automatically optimize and load [Geist](https://vercel.com/font).

## Learn More

- [Next.js Documentation](https://nextjs.org/docs)
- [Learn Next.js](https://nextjs.org/learn)
