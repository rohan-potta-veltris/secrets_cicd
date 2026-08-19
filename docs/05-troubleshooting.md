# Troubleshooting

## `Not authorized to perform sts:AssumeRoleWithWebIdentity`

The trust policy's `Condition` block doesn't match the token GitHub sent.
This was the single hardest failure to debug while building this repo —
everything *looked* correct (right account, right audience, right branch)
and it still failed, because the actual mismatch was in a claim shape we
hadn't considered. In order of likelihood:

- **Your job uses `environment:` and the trust policy assumes a branch
  ref.** This was the actual root cause here. If the job has
  `environment: production` (as `fetch-secret.yml` does, for the
  required-reviewer gate), GitHub's `sub` claim is
  `repo:<owner>/<repo>:environment:production` — there is **no**
  `ref:refs/heads/...` segment at all, ever, regardless of which branch the
  run is on. A trust policy written to match `ref:refs/heads/main` will
  never match an environment-gated job's token, full stop. See
  [`02-aws-console-setup.md`](02-aws-console-setup.md) Step 3a for the
  correct pattern.
- **GitHub embeds immutable numeric IDs in `sub`.** Even after fixing the
  branch-vs-environment shape, the `sub` claim can look like
  `repo:owner@177530384/repo@1339256549:environment:production` — with IDs
  spliced into the owner/repo names. A plain-text `StringLike` pattern like
  `repo:owner/repo:*` will **not** match this, because the literal prefix
  before the wildcard no longer matches character-for-character. Don't
  guess — decode a real token and copy the exact value (see the debug
  snippet in Step 3a).
- **AWS rejects a trust policy with no scoped `sub`/`job_workflow_ref`
  condition at all.** If you try to drop `sub` entirely and rely only on
  `repository`/`environment` conditions, AWS's console will refuse to save
  the policy with an error naming this requirement explicitly. You must
  keep a `sub` condition; it just doesn't have to be your only one.
- **Wrong repo/owner casing** — `sub`/`repository` matching is
  case-sensitive. Confirm the trust policy's values exactly match your
  GitHub org/user and repo name.
- **Missing `id-token: write` permission** — check the workflow file has
  `permissions: id-token: write` at the job or workflow level. Without it,
  GitHub never issues an OIDC token to request in the first place.
- **`aud` mismatch** — must be exactly `sts.amazonaws.com` in both the OIDC
  provider's configured audience and the trust policy condition.

**If in doubt, don't keep editing the policy by guesswork** — add the debug
step from [`02-aws-console-setup.md`](02-aws-console-setup.md) Step 3a,
run the workflow once, and read the actual claims GitHub sent. Every cause
above was ultimately found this way, not by re-reading the policy JSON.

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
