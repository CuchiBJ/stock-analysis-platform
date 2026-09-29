# Frontend

## Conventions

- Use App Router patterns and preserve established component and data-fetching conventions.
- Route authenticated API traffic through `lib/api-client.ts`; do not bypass its cookie, CSRF, unauthorized-session, or cleanup behavior with ad hoc fetch wrappers.
- Preserve the institutional visual language: restrained color, clear hierarchy, compact context, and functional rather than decorative presentation.
- Avoid giant raw-data tables, equal visual weight, unnecessary panels, gradients, gamification, and prediction-style messaging.
- Treat loading, empty, error, unauthorized, and session-expired states as part of the feature contract.

## Verification

- From `frontend/`, run `npm test`; use `npm run lint` and `npm run typecheck` for static checks.
- Run `npm run build` for integration-sensitive frontend or production changes.
