# GitHub Repository Setup

Assumes you've completed [`02-aws-console-setup.md`](02-aws-console-setup.md)
and have the IAM **Role ARN** copied.

## Step 1 — Push this repo to GitHub

```bash
git init
git add .
git status   # sanity-check nothing sensitive (.env, real secrets) is staged
git commit -m "Initial commit: secure secrets CI/CD reference"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>.git
git push -u origin main
```

> If your IAM trust policy (Step 3a in the previous doc) already references
> `<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>`, make sure this matches exactly —
> it's case-sensitive.

## Step 2 — Add repository variables

Neither the role ARN, the region, nor the secret's *name* are sensitive by
themselves (the IAM trust policy is what actually restricts access) — so
these are stored as **Variables**, not **Secrets**, which keeps them visible
in workflow logs for easier debugging.

Go to **Settings → Secrets and variables → Actions → Variables tab → New
repository variable**, and add:

| Name | Value |
|---|---|
| `AWS_ROLE_ARN` | `arn:aws:iam::<AWS_ACCOUNT_ID>:role/github-actions-secrets-demo-role` |
| `AWS_REGION` | `us-east-1` (or whatever region you used) |
| `SECRET_NAME` | `cicd-demo/api-key` |

## Step 3 — Create the `production` Environment

This gates [`fetch-secret.yml`](../.github/workflows/fetch-secret.yml) behind
a manual approval, so an accidental push to `main` can't silently pull the
secret without a human noticing.

> If you've already created a `production` environment (e.g. while poking
> around **Settings → Environments** earlier), you don't need to create it
> again — GitHub won't let you create a duplicate anyway. Just click into
> the existing one and pick up at step 2 below.

1. **Settings → Environments → New environment**, name it `production`.
2. Under **Deployment protection rules**, check **Required reviewers** and
   add yourself (or your team). This is the part that actually matters —
   an environment with no protection rules exists but doesn't gate anything.
3. Save.

## Step 4 — Enable secret scanning (GitHub-native, in addition to gitleaks)

Go to the **Security** tab → **Security and quality** (GitHub has renamed
this section a few times — older docs/screenshots call it "Code security
and analysis"; look for the tab next to **Insights**).

- **Secret scanning alerts** — for a **public** repo, GitHub enables this by
  default, so you may see it already showing **Enabled**. If so, nothing to
  do here — just confirm it via **View detected secrets**. For a private
  repo, click to enable it.
- **Push protection** — a stricter mode that blocks the push itself (not
  just alerts after the fact) when it detects a recognizable secret pattern.
  This is a separate toggle from plain secret scanning and is not always on
  by default even on public repos — check for it and enable it if present.

This step is really just a **verification**, not a from-scratch setup, since
both are commonly on by default for public repos. On the same page (GitHub
currently nests this under **Code scanning → Protection rules**, alongside
CodeQL's settings — not the most intuitive placement, but that's where it
lives), you'll see **Secret Protection** and **Push protection** rows with
an **Enable**/**Disable** button next to each. The button always shows the
action you *could* take, not the current state — so a button reading
**Disable** means the feature is already **on**, and you don't need to
click it.

Either way, this is a second, independent layer alongside the `gitleaks`
job in [`ci.yml`](../.github/workflows/ci.yml) — one catches it at push
time, the other at PR/CI time.

## Step 5 — Trigger the pipeline

- Open a PR that touches `app/` — confirm `ci.yml`'s `lint-and-test` and
  `secret-scan` jobs run and pass.
- Merge to `main` (or use **Actions → Fetch Secret from AWS → Run workflow**
  for manual `workflow_dispatch`) — confirm the run pauses for your
  `production` environment approval, then succeeds and logs a masked secret
  value like:

  ```
  INFO: Retrieved secret (masked): su******************** (length=23)
  INFO: Pretending to call an external API with the secret... success!
  ```

### Verifying the actual secret value (optional, one-off)

`fetch-secret.yml`'s manual dispatch has a checkbox: **"Print the raw secret
value in logs (debug only - leave off)"**. It's wired to a `SHOW_RAW_SECRET`
environment variable that [`fetch_secret.py`](../app/fetch_secret.py)
checks — when true, it logs the raw value (with a loud `WARNING` prefix)
*in addition to* the normal masked line, so you can confirm the pipeline
is actually pulling the value you expect it to.

Use it like this: **Actions → Fetch Secret from AWS → Run workflow**, check
the box, run it, read the `WARNING: Raw secret value: ...` line in the
**Fetch and use secret** step, confirm it's correct, then **leave the box
unchecked for every run after that**. It defaults to `false` and only
applies to manual `workflow_dispatch` runs — a plain push to `main` never
sets it — but there's nothing stopping someone from checking it
accidentally, so treat it as a one-time verification tool, not something to
leave on.

## Next

Read [`04-security-best-practices.md`](04-security-best-practices.md) for
why each of these choices matters and what to add for a real production
deployment. If something above fails, check
[`05-troubleshooting.md`](05-troubleshooting.md).
