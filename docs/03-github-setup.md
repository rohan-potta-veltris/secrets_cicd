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

1. **Settings → Environments → New environment**, name it `production`.
2. Under **Deployment protection rules**, check **Required reviewers** and
   add yourself (or your team).
3. Save.

## Step 4 — Enable branch protection on `main`

**Settings → Branches → Add branch protection rule**, branch name pattern
`main`:

- ✅ Require a pull request before merging
- ✅ Require approvals (at least 1)
- ✅ Require status checks to pass before merging → select the `lint-and-test`
  and `secret-scan` jobs from `ci.yml` once they've run at least once
- ✅ Do not allow bypassing the above settings (even for admins, if you want
  the rule to actually hold)

## Step 5 — Enable secret scanning (GitHub-native, in addition to gitleaks)

**Settings → Code security and analysis**, enable:
- **Secret scanning** (and **Push protection**, if available on your plan) —
  this blocks commits containing recognizable secret patterns *before* they
  even reach the repo, as a second layer alongside the `gitleaks` job in `ci.yml`.

## Step 6 — Trigger the pipeline

- Open a PR that touches `app/` — confirm `ci.yml`'s `lint-and-test` and
  `secret-scan` jobs run and pass, and that merging is blocked until they do.
- Merge to `main` (or use **Actions → Fetch Secret from AWS → Run workflow**
  for manual `workflow_dispatch`) — confirm the run pauses for your
  `production` environment approval, then succeeds and logs a masked secret
  value like:

  ```
  INFO: Retrieved secret (masked): su******************** (length=23)
  INFO: Pretending to call an external API with the secret... success!
  ```

## Next

Read [`04-security-best-practices.md`](04-security-best-practices.md) for
why each of these choices matters and what to add for a real production
deployment. If something above fails, check
[`05-troubleshooting.md`](05-troubleshooting.md).
