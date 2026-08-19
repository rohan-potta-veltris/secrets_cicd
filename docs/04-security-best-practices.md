# Security Best Practices — Applied Here, and What's Next

## What this repo already does

| Practice | Where | Why |
|---|---|---|
| No long-lived AWS credentials anywhere | OIDC trust policy, [`fetch-secret.yml`](../.github/workflows/fetch-secret.yml) | A leaked GitHub secret can't be replayed outside the ~1 hour token lifetime, and can't be used from outside GitHub Actions at all. |
| Trust policy scoped to one repo + branch | [`02-aws-console-setup.md`](02-aws-console-setup.md) Step 3a | Prevents any other repo, fork, or branch from assuming the role — even within the same AWS account/GitHub org. |
| IAM policy scoped to one action, one resource | [`02-aws-console-setup.md`](02-aws-console-setup.md) Step 3b | If the role is ever assumed unexpectedly, the blast radius is "read this one secret," not "do anything in this account." |
| Secret value never logged or printed | [`fetch_secret.py`](../app/fetch_secret.py) `mask()` | Defense in depth — GitHub redacts registered secrets from logs automatically, but a value that was never a *registered* GitHub secret (it's fetched at runtime from AWS, not stored in GitHub) wouldn't be redacted, so the app masks it itself. |
| Two-workflow split (safe CI vs. AWS-touching) | [`ci.yml`](../.github/workflows/ci.yml) vs [`fetch-secret.yml`](../.github/workflows/fetch-secret.yml) | PRs — including from forks — can never reach AWS credentials, because only `fetch-secret.yml` requests `id-token: write` and only it runs on `main`/manual dispatch. |
| Required-reviewer Environment gate | [`03-github-setup.md`](03-github-setup.md) Step 3 | A human must approve before the workflow can actually call AWS, even on `main`. |
| Secret scanning (gitleaks in CI + GitHub push protection) | [`ci.yml`](../.github/workflows/ci.yml), [`03-github-setup.md`](03-github-setup.md) Step 4 | Two independent layers catch an accidentally committed credential before and after it reaches the remote. |
| Unit tests use a mocked AWS (`moto`), not real credentials | [`test_fetch_secret.py`](../app/tests/test_fetch_secret.py) | CI never needs real AWS access to verify the app logic, shrinking the credential surface further. |

## What a real production deployment should add on top

These are deliberately **out of scope** for this learning repo (to keep the
manual-console setup simple) but worth knowing about:

- **Secret rotation** — enable automatic rotation on the Secrets Manager
  secret (Secrets Manager can invoke a Lambda on a schedule to rotate it).
  Manual, one-time secrets like this demo's are fine for learning, not for
  production credentials.
- **Customer-managed KMS key** — the default `aws/secretsmanager` key is
  fine here; production secrets often use a dedicated CMK so you can control
  and audit exactly who can decrypt, independent of Secrets Manager access.
- **CloudTrail** — enable it (if not already on by default in your account)
  and specifically look for `secretsmanager:GetSecretValue` events, ideally
  shipped to a SIEM/alerting pipeline so unexpected access is noticed fast.
- **IaC instead of console clicks** — this repo intentionally skips
  Terraform/CloudFormation for learning clarity, but a real production setup
  should define the OIDC provider, role, and secret as code, reviewed via
  PR, so infrastructure changes go through the same review process as
  application code.
- **Remove the required-reviewer bottleneck at scale** — manual approval
  works for a demo; a real pipeline with frequent deploys would instead rely
  on the tightly-scoped trust policy + IAM policy as the actual control, and
  use monitoring/alerting instead of a manual gate on every run.
- **Least-privilege review cadence** — periodically audit IAM roles/policies
  for drift (permissions added "temporarily" that were never removed).
- **Separate AWS accounts per environment** — a real setup typically uses
  distinct dev/staging/prod AWS accounts (via AWS Organizations) rather than
  one account with a "production" secret, so a mistake in one environment
  can't reach another.
- **Branch protection on `main`** (require PR review, required status
  checks, no bypassing for admins) — general repo hygiene rather than
  something specific to the secrets/OIDC pattern this repo demonstrates, so
  it's left out of [`03-github-setup.md`](03-github-setup.md), but any real
  project should still have it.

## Next

See [`05-troubleshooting.md`](05-troubleshooting.md) if something didn't
work as expected.
