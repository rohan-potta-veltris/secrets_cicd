# Troubleshooting

## `Not authorized to perform sts:AssumeRoleWithWebIdentity`

The trust policy's `Condition` block doesn't match the token GitHub sent.
Most common causes:

- **Wrong repo/owner casing** — `sub` matching is case-sensitive. Confirm
  `repo:<owner>/<repo>:ref:refs/heads/main` in the trust policy exactly
  matches your GitHub org/user and repo name.
- **Running from a different branch/PR** — the trust policy in this repo
  only allows `ref:refs/heads/main`. A workflow run triggered from a PR
  branch or a tag won't match. That's by design for `fetch-secret.yml`
  (see [`01-architecture.md`](01-architecture.md)) — either merge to `main`
  first, or deliberately broaden the `StringLike` pattern if you need more.
- **Missing `id-token: write` permission** — check the workflow file has
  `permissions: id-token: write` at the job or workflow level. Without it,
  GitHub never issues an OIDC token to request in the first place.
- **`aud` mismatch** — must be exactly `sts.amazonaws.com` in both the OIDC
  provider's configured audience and the trust policy condition.

## `AccessDeniedException` when calling `GetSecretValue`

The role assumed successfully, but its permission policy doesn't allow this
call. Check:

- The inline policy's `Resource` ARN exactly matches the secret's ARN,
  **including the random suffix** AWS appended (e.g. `-AbCdEf`). A common
  mistake is using the ARN without the suffix, which won't match.
- The `Action` includes `secretsmanager:GetSecretValue` (not just
  `DescribeSecret` or similar).
- You're checking the secret in the same AWS **region** the policy/ARN
  references — Secrets Manager is regional.

## `Could not connect to the endpoint URL` or region errors

`AWS_REGION` repo variable doesn't match the region the secret and role
actually live in. All three (OIDC provider trust, IAM role, and the secret)
don't have to be in the same region for the *role*, but the secret ARN and
the `AWS_REGION` passed to `boto3` in `fetch_secret.py` must match where the
secret was created.

## Workflow doesn't pause for approval

Confirm the job in `fetch-secret.yml` has `environment: production` set, and
that the `production` environment (Settings → Environments) actually has a
required reviewer configured — a newly created environment with no
protection rules will not block anything.

## `pytest` fails with `ModuleNotFoundError: No module named 'fetch_secret'`

Make sure you're running from the repo root with
`pytest app/tests/`, or `cd app && pytest`. The
[`conftest.py`](../app/tests/conftest.py) adds `app/` to `sys.path`, but only
once pytest actually discovers and loads it — running `pytest` from an
unrelated directory outside the repo won't find it.

## gitleaks fails on a false positive

If `ci.yml`'s `secret-scan` job flags something that isn't actually a
secret (e.g. a placeholder in these docs), add a `.gitleaksignore` file
listing the specific finding, rather than disabling the whole job.
