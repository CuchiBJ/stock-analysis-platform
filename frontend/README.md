# Stock Analysis Platform - Frontend

Next.js frontend for stock momentum and sector rotation analysis.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Configure environment:
```bash
cp .env.local.example .env.local
# Edit .env.local with your API URL
```

3. Run development server:
```bash
npm run dev
```

4. Build for production:
```bash
npm run build
npm start
```

## Tech Stack

- Next.js 14 with App Router
- React 18
- TypeScript
- TailwindCSS
- TanStack Query (React Query)
- Zustand (state management)
- TradingView Lightweight Charts

## Project Structure

- `app/` - Next.js App Router pages
- `components/` - Reusable React components
- `lib/` - Utilities, API client, hooks, store
- `types/` - TypeScript type definitions
