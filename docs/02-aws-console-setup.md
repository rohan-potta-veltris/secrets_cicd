# AWS Console Setup (Manual, Step by Step)

No Terraform or CLI scripting here on purpose — every resource is created by
hand in the AWS Console so you can see exactly what gets created and why.
Do these in order; later steps reference ARNs created in earlier ones.

Throughout, replace:
- `<AWS_ACCOUNT_ID>` with your 12-digit AWS account ID
- `<YOUR_GITHUB_USERNAME>` / `<YOUR_REPO_NAME>` with your actual GitHub org/user and repo name
- `us-east-1` with your preferred region (keep it consistent everywhere)

### Pick your region first

Decide this **before** you start clicking, and use the same value everywhere
below (the console's region selector top-right, the ARNs in the IAM policy,
and the `AWS_REGION` GitHub variable in [`03-github-setup.md`](03-github-setup.md)):

- **IAM is global** — the OIDC identity provider (Step 1) and the IAM role
  (Step 3) aren't tied to any region; the console's region dropdown doesn't
  even affect them.
- **Secrets Manager is regional** — the secret (Step 2) is created in
  whichever region you have selected at the time, and its ARN bakes that
  region in permanently. If you later call `GetSecretValue` from a
  different region than where the secret lives, it will fail even with
  correct permissions.

So the one thing that actually needs deciding is: **which region will the
secret live in?** This repo uses `us-east-1` as the example throughout — swap
it for your preferred region, but use that same one consistently in Step 2's
secret creation, Step 3b's policy `Resource` ARN, and the `AWS_REGION`
variable later.

---

## Step 1 — Create the GitHub OIDC Identity Provider

This tells AWS "trust identity tokens signed by GitHub Actions." You only
need to do this **once per AWS account** — if you already have one for
another project, skip to Step 2.

> **This step is AWS-specific.** Azure and GCP use the same underlying idea
> (GitHub OIDC federation) but call it something else and configure it in a
> different place: Azure uses **Workload Identity Federation** via a
> *federated credential* on an App Registration; GCP uses a **Workload
> Identity Pool + Provider** mapped to a Service Account. Same trust
> relationship, different console screens — see the AWS vs. Azure vs. GCP
> comparison earlier in this conversation if you're evaluating another cloud.

1. Go to **IAM Console → Identity providers → Add provider**.
2. Provider type: **OpenID Connect**.
3. Provider URL: `https://token.actions.githubusercontent.com`
4. Click **Get thumbprint** (AWS fetches it automatically).
5. Audience: `sts.amazonaws.com`
6. Click **Add provider**.

**What is the "Audience"?** It's the `aud` claim inside the OIDC token —
basically "who this token is meant for." GitHub stamps every OIDC token it
issues with an audience value, and AWS STS only accepts tokens whose `aud`
matches what you registered here. `sts.amazonaws.com` is the fixed value
AWS expects for `AssumeRoleWithWebIdentity`; it's also referenced again in
the IAM role's trust policy condition in Step 3a as a second check. Think of
it as a basic anti-confused-deputy guard: it stops a token GitHub issued for
some *other* audience (e.g. a different cloud's OIDC integration) from being
replayed against AWS.

You now have a provider ARN like:
`arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com`

---

## Step 2 — Create the Secret in Secrets Manager

1. Go to **Secrets Manager Console → Store a new secret**.
2. Secret type: **Other type of secret**.
3. Under **Key/value pairs**, add:
   - Key: `demo_api_key`
   - Value: any placeholder string for now, e.g. `local-test-value-change-me`
     (this matches the field name `app/fetch_secret.py` reads — see [`../app/fetch_secret.py`](../app/fetch_secret.py))
4. Encryption key: leave as the default `aws/secretsmanager` KMS key (fine
   for learning; a dedicated customer-managed key is a production upgrade —
   see [`04-security-best-practices.md`](04-security-best-practices.md)).
5. Click **Next**.
6. Secret name: `cicd-demo/api-key` (or any name — just keep it consistent
   with what you put in your GitHub repo variables in Step 2 of
   [`03-github-setup.md`](03-github-setup.md)).
7. Click **Next** twice (skip automatic rotation for this learning project),
   then **Store**.
8. Open the secret you just created and **copy its full ARN** — you'll need
   it in Step 4. It looks like:
   `arn:aws:secretsmanager:us-east-1:<AWS_ACCOUNT_ID>:secret:cicd-demo/api-key-AbCdEf`

   Note the random 6-character suffix AWS appends — that's why the IAM
   policy below is written after the secret exists, not before.

---

## Step 3 — Create the IAM Role for GitHub Actions

IAM roles are always created for some **trusted entity** — the thing that's
allowed to assume the role. AWS groups the options by *what kind of caller*
you're trusting: another AWS account, an AWS service (like Lambda or EC2), a
SAML-based corporate identity provider, or a **web identity** — an external
OIDC/OAuth identity provider like Google, Cognito, or, in this case, GitHub
Actions. GitHub's OIDC tokens are exactly that: a web identity token issued
by an external OIDC provider, not an AWS-native identity — so **Web
identity** is the trusted-entity type that matches what we registered in
Step 1, and it's what makes `AssumeRoleWithWebIdentity` (the API call in the
architecture diagram) the right action for the trust policy.

1. Go to **IAM Console → Roles → Create role**.
2. Trusted entity type: **Web identity**.
3. Identity provider: select `token.actions.githubusercontent.com` (created in Step 1).
4. Audience: `sts.amazonaws.com`.
5. The console shows **GitHub organization** (required), **GitHub
   repository** (optional), and **GitHub branch** (optional) fields — these
   pre-fill part of the trust policy for you. They come from your GitHub
   repo's identity, not from anything in AWS, so decide your GitHub
   username/org and repo name first if you haven't already:
   - **GitHub organization**: your GitHub username or org — just the name,
     e.g. if your repo will be `github.com/rohanpotta/secrets_cicd`, enter
     `rohanpotta`.
   - **GitHub repository**: just the repo name, no slashes, e.g.
     `secrets_cicd`. Leave as `*` to allow any repo under that org (broader
     than we want — fill it in).
   - **GitHub branch**: `main`. Leave as `*` to allow any branch (broader
     than we want — fill it in).

   Filling all three in gives the wizard enough to generate a `sub`
   condition close to the one in Step 3a below — but **don't skip Step 3a**:
   depending on which fields you left blank, the auto-generated policy can
   end up looser than intended, so verify/replace it explicitly.
6. Click **Next**. **Don't attach any AWS managed policies** — you'll add a
   tightly-scoped inline policy instead.
7. Name the role: `github-actions-secrets-demo-role` (or any name you
   prefer, e.g. `cidc_test_role` — the name itself has no functional effect,
   it's just what you'll recognize it by in the console and what you'll see
   in the ARN in Step 3c below).
8. Click **Create role**.

### Step 3a — Lock down the trust policy

If you filled in the **GitHub organization** / **GitHub repository** /
**GitHub branch** fields in Step 3.5 above, AWS may have already generated a
trust policy close to (or identical to) the one below — the console uses
those three fields to pre-fill the `sub` condition's `StringLike` pattern
for you. Open the new role → **Trust relationships** tab and check what's
there before assuming you need to write this from scratch.

That said, still treat it as something to **verify, not trust blindly**: the
console-generated policy can end up broader than you want (e.g. if you left
**GitHub branch** as `*`, it'll allow any branch/tag in the repo; if you left
**GitHub repository** as `*` too, it'll allow any repo under that org).

**Important caveat, found the hard way:** the "obvious" pattern below —
matching `sub` against `repo:<owner>/<repo>:ref:refs/heads/main` — only
applies to jobs that **don't** specify a GitHub `environment:`. Because
[`fetch-secret.yml`](../.github/workflows/fetch-secret.yml)'s job sets
`environment: production` (the required-reviewer gate from
[`03-github-setup.md`](03-github-setup.md) Step 3), GitHub emits a
completely different `sub` shape for it — see the callout below before you
write this policy.

For a plain job with **no** `environment:` key, this is correct:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

> Want to also allow tags or `workflow_dispatch` from other branches? Use
> `StringLike` with a pattern like `repo:owner/repo:ref:refs/heads/*` — but
> the narrower you keep this, the smaller your blast radius if a workflow
> file is ever compromised.

#### If your job uses `environment:` (this repo's case) — use this instead

Two things are different once a job is gated by a GitHub Environment:

1. **The `sub` shape changes entirely.** Instead of `ref:refs/heads/<branch>`,
   GitHub emits `repo:<owner>/<repo>:environment:<environment-name>` — there
   is no branch/ref segment in it at all, no matter what branch the run is on.
2. **GitHub may embed immutable numeric IDs** in the owner/repo names inside
   `sub` — e.g. `repo:owner@177530384/repo@1339256549:environment:production`
   — so you can't reliably pattern-match `sub` against a plain `owner/repo`
   string. These IDs are stable even across a repo/org rename, which is the
   point of them, but they mean the "obvious" `sub` pattern above will
   silently never match and every run will fail with
   `Not authorized to perform sts:AssumeRoleWithWebIdentity`
   (see [`05-troubleshooting.md`](05-troubleshooting.md)).

You don't need to know your repo's exact immutable IDs up front — there are
two valid ways to write this policy, and only one of them requires any
extra work:

**Option A — wildcard the ID, works immediately for any new project (start here):**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:repository": "<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>",
          "token.actions.githubusercontent.com:environment": "production"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:<YOUR_GITHUB_USERNAME>*/<YOUR_REPO_NAME>*:environment:production"
        }
      }
    }
  ]
}
```

Just substitute your own owner/repo names — no debugging, no token
decoding, nothing to look up. The trailing `*` after each name absorbs
GitHub's optional `@<id>` suffix wherever it does or doesn't appear; the
literal `repo:<owner>` and `/<repo>` text before each `*` still has to
match exactly, so this isn't meaningfully looser than knowing the real IDs
— a different repo's token can never satisfy this pattern. AWS's console
will show an advisory warning about the wildcard in `sub` (it doesn't know
the wildcard only ever consumes an internal ID), but it still saves fine —
this is what actually got this repo working the first time.

**Option B — exact match, no wildcards, for eliminating that warning:**

If Option A works but you want to clear the console warning, or you just
prefer zero wildcards, you can look up your repo's exact IDs by adding this
step to your workflow temporarily, running it once, then deleting it:

```yaml
- name: Debug - print OIDC token claims
  run: |
    IDTOKEN=$(curl -sSL -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
      "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=sts.amazonaws.com" | jq -r '.value')
    PAYLOAD=$(echo -n "$IDTOKEN" | cut -d '.' -f2 | tr '_-' '/+')
    case $(( ${#PAYLOAD} % 4 )) in
      2) PAYLOAD="${PAYLOAD}==" ;;
      3) PAYLOAD="${PAYLOAD}=" ;;
    esac
    echo "$PAYLOAD" | base64 -d | jq '{aud, sub, repository, ref, repository_owner, environment}'
```

Then swap Option A's `StringLike` block for an exact `StringEquals` line
using the printed `sub` value verbatim (IDs included):

```json
"token.actions.githubusercontent.com:sub": "repo:<owner>@<owner-id>/<repo>@<repo-id>:environment:production"
```

This is optional hardening, not a requirement — Option A is already
correctly scoped to this exact repo and environment. Save whichever
version you choose.

**Option C — match `job_workflow_ref` instead of `sub`:** AWS's validator
error explicitly names this as the other accepted claim
(`sub` **or** `job_workflow_ref`). Instead of pinning to a repo+environment,
it pins to the actual **workflow file that ran**:

```json
"token.actions.githubusercontent.com:job_workflow_ref": "<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>/.github/workflows/fetch-secret.yml@refs/heads/main"
```

This isn't obviously better or worse than Options A/B — it's a different
axis of coupling. `sub`-based matching breaks if you rename the
environment; `job_workflow_ref`-based matching breaks if you rename or
move the workflow file. Pick whichever failure mode you'd rather deal
with. We didn't need this for this repo (Option A already works), and
haven't verified whether `job_workflow_ref` is also subject to the
immutable-ID splicing described above for every account — add it to the
debug snippet's `jq` filter if you want to check before relying on it.

### Step 3b — Add the least-privilege permission policy

On the same role, go to **Permissions** tab → **Add permissions → Create
inline policy** → JSON, and paste (using the secret ARN you copied in Step 2.8):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:<AWS_ACCOUNT_ID>:secret:cicd-demo/api-key-AbCdEf"
    }
  ]
}
```

Name it `read-cicd-demo-secret` and save. Notice this policy grants
**exactly one action on exactly one resource** — no `secretsmanager:*`, no
wildcard ARN, no other services.

### Step 3c — Copy the Role ARN

From the role's summary page, copy its ARN, e.g.:
`arn:aws:iam::<AWS_ACCOUNT_ID>:role/github-actions-secrets-demo-role`

You'll paste this into a GitHub repository variable in the next doc.

---

## Verification checklist

- [ ] OIDC provider exists for `token.actions.githubusercontent.com`
- [ ] Secret `cicd-demo/api-key` exists with a `demo_api_key` key
- [ ] Role's trust policy `sub` condition matches your exact repo + branch
- [ ] Role's inline policy grants only `GetSecretValue` on that one secret ARN
- [ ] You have the Role ARN and Secret ARN copied somewhere for the next step

## Next

Continue to [`03-github-setup.md`](03-github-setup.md) to wire these ARNs
into your GitHub repository.
