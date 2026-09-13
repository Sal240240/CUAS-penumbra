# PENUMBRA webapp

React + TypeScript + Vite. Architecture explainer, an in-browser link-budget
simulator, a mesh coverage-map visualizer, an evidence-ledger demo, hardware
and program pages, and full citations/image credits.

## Development

```bash
npm install
npm run dev      # local dev server
npm run build    # type-check (tsc -b) + production build to dist/
npm run preview  # serve the production build locally
```

## Physics parity

Every equation in `src/physics/*.ts` is a line-by-line port of the
corresponding module in `../penumbra/physics/` and `../penumbra/sim/`. This
is checked, not assumed: each port was run against its Python source on
shared scenarios (same illuminator, target, and geometry) and compared field
by field. Example (see git history / `docs/10_red_team_ledger.md` RT-12 for
the full set):

```
TS : {"pRDbw":-128.43207530841704,"snrDbw":30.34663825080677,...}
PY : LinkBudget(p_r_dbw=-128.43207530841704, snr_db=30.34663825080677, ...)
```

identical to full floating-point precision. If you change a physics equation
in one language, change it in the other and re-verify — the whole point of
the in-browser simulator is that it cannot quietly disagree with the offline
analysis.

Ported modules: `constants.ts`, `bistatic.ts`, `rcs.ts`, `illuminators.ts`,
`propagation.ts`, `scene.ts`, `coverage.ts`, `evidence.ts`. The ML detector,
DSP (cross-ambiguity/CFAR), and multistatic UKF tracker are **not** ported —
those run offline/server-side (`penumbra/ml/`, `penumbra/dsp/`,
`penumbra/tracking/`) and are represented in the webapp as explained results
(the Evidence page), not re-executed in the browser.

## Deployment

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for AWS Amplify Hosting.

## Images

All photography is Creative Commons-licensed and credited on the References
page (`src/pages/References.tsx`) and inline via `src/components/Credited.tsx`
— no stock photography, no AI-generated imagery. Source metadata lives in
`src/data/credits.ts`.
