# Playwright + Axe baseline

This is a starter accessibility test harness for frontend pages.

## Install

```bash
npm install
npm run a11y:install
```

## Run

Start the app locally, then run:

```bash
A11Y_BASE_URL=http://127.0.0.1:5000 npm run a11y:test
```

If `A11Y_BASE_URL` is not set, the tests are skipped by design.

## Current scope

- Pages checked: `/`, `/signin`
- Rules checked: `wcag2a`, `wcag2aa`
- Fails only on `serious` and `critical` violations

Expand `playwright/tests/a11y.spec.js` in follow-up PRs as needed.
