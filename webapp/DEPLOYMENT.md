# Deploying to AWS Amplify Hosting

This is a static single-page app (Vite build output in `dist/`) with
client-side routing (`react-router-dom`, `BrowserRouter`). Two things matter
for Amplify specifically: the build settings, and the SPA rewrite rule so
deep links (e.g. `/simulator`) don't 404 on refresh.

## Option A — Amplify Console, connected to a Git repo

1. Push this repository (or just the `webapp/` directory as its own repo) to
   GitHub/GitLab/CodeCommit/Bitbucket.
2. In the Amplify Console: **New app → Host web app**, connect the repo and
   branch.
3. If `webapp/` is a subdirectory of a larger repo, set the app root /
   monorepo package path to `webapp` in the build settings.
4. Amplify auto-detects a Vite app; confirm or paste this build spec
   (`amplify.yml`, already included in this directory):

   ```yaml
   version: 1
   frontend:
     phases:
       preBuild:
         commands:
           - npm ci
       build:
         commands:
           - npm run build
     artifacts:
       baseDirectory: dist
       files:
         - '**/*'
     cache:
       paths:
         - node_modules/**/*
   ```
5. **Rewrites and redirects** (Amplify Console → App settings → Rewrites and
   redirects) — add a rule so client-side routes resolve on a hard refresh
   or direct link:

   | Source address | Target address | Type |
   |---|---|---|
   | `</^[^.]+$/>` | `/index.html` | 200 (Rewrite) |

   (This regex matches any path without a file extension — i.e. not
   `/assets/foo.js` — and serves `index.html`, letting React Router take
   over client-side.)
6. Deploy. Amplify builds on every push to the connected branch.

## Option B — Amplify Hosting via the CLI, without connecting a Git provider

```bash
npm install -g @aws-amplify/cli   # if not already installed
cd webapp
npm run build
amplify init
amplify add hosting   # choose "Amplify Hosting (manual deployment)" or "S3 and CloudFront"
amplify publish
```

For a manual/one-off deploy, `amplify hosting add` with the manual option
uploads the contents of `dist/` directly — still add the same SPA rewrite
rule (200 rewrite to `/index.html` for extensionless paths) in the Console
afterward.

## Custom domain / HTTPS

Amplify Hosting provisions HTTPS automatically for both the default
`*.amplifyapp.com` domain and any custom domain attached via
**App settings → Domain management** — no separate ACM/CloudFront setup
needed for the common case.

## Environment

No environment variables or backend are required — everything (physics,
scene data, evidence ledger) computes client-side from the bundled
TypeScript in `src/physics/` and `src/data/`.
