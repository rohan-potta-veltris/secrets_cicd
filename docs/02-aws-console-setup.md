# AWS Console Setup (Manual, Step by Step)

Follow these steps in order to set up the AWS side of the pipeline by hand
in the Console — every resource is created manually so you can see exactly
what gets created and why. Later steps reference ARNs created in earlier
ones, so don't skip around.

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
4. Encryption key: leave as the default `aws/secretsmanager` KMS key.
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

1. Right after creating the OIDC provider in Step 1, AWS shows a success
   banner with an **Assign role** button — click it. This carries the
   provider and audience over automatically and drops you straight into
   role creation with **Trusted entity type: Web identity** and
   **Identity provider: `token.actions.githubusercontent.com`** already
   selected, so there's nothing to pick manually here.
   (Starting fresh instead via **IAM Console → Roles → Create role**? Set
   those two fields yourself, plus **Audience: `sts.amazonaws.com`**, to
   land on the same screen.)
2. The next screen shows **GitHub organization** (required), **GitHub
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
3. Click **Next**. **Don't attach any AWS managed policies** — you'll add a
   tightly-scoped inline policy instead.
4. Name the role: `github-actions-secrets-demo-role` (or any name you
   prefer, e.g. `cidc_test_role` — the name itself has no functional effect,
   it's just what you'll recognize it by in the console and what you'll see
   in the ARN in Step 3c below).
5. Click **Create role**.

Once the trust policy is finalized in Step 3a below, see
[`04-trust-policy-explained.md`](04-trust-policy-explained.md) for a full
line-by-line breakdown of what it does and why.

### Step 3a — Lock down the trust policy

If you filled in the **GitHub organization** / **GitHub repository** /
**GitHub branch** fields in Step 3.2 above, AWS may have already generated a
trust policy close to (or identical to) the one below — the console uses
those three fields to pre-fill the `sub` condition's `StringLike` pattern
for you. Open the new role → **Trust relationships** tab and check what's
there before assuming you need to write this from scratch.

That said, still treat it as something to **verify, not trust blindly**: the
console-generated policy can end up broader than you want (e.g. if you left
**GitHub branch** as `*`, it'll allow any branch/tag in the repo; if you left
**GitHub repository** as `*` too, it'll allow any repo under that org).

**Important caveat, found the hard way:** a naive pattern matching `sub`
against `repo:<owner>/<repo>:ref:refs/heads/main` would **not** work here.
That pattern only applies to jobs that don't specify a GitHub
`environment:`. Because [`fetch-secret.yml`](../.github/workflows/fetch-secret.yml)'s
job sets `environment: production` (the required-reviewer gate from
[`03-github-setup.md`](03-github-setup.md) Step 3), GitHub emits a
completely different `sub` shape for it. Two things are different once a
job is gated by a GitHub Environment:

1. **The `sub` shape changes entirely.** Instead of `ref:refs/heads/<branch>`,
   GitHub emits `repo:<owner>/<repo>:environment:<environment-name>` — there
   is no branch/ref segment in it at all, no matter what branch the run is on.
2. **GitHub embeds immutable numeric IDs** in the owner/repo names inside
   `sub` — e.g. `repo:owner@177530384/repo@1339256549:environment:production`.
   This isn't a quirk or a bug — it's a deliberate GitHub security feature
   ([announced April 2026](https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/)):
   **every repository created after July 15, 2026 gets this format
   automatically, with no opt-out.** It exists to close a real vulnerability
   called *namespace recycling* — without the ID, if your GitHub org/repo
   name were ever deleted and re-registered by someone else, their new
   repo's token would produce the exact same `sub` string as yours, and any
   trust policy matching on the plain name would trust them too. The numeric
   ID is permanently tied to your specific repo and can never be reused by
   anyone else, even if the name is.

**Because of what this feature protects against, do not wildcard the ID
away.** A pattern like `repo:<owner>*/<repo>*:environment:production`
technically "works" (AWS will save it, and it'll match your token), but it
defeats the entire point: if your org/repo name is ever recycled by a
different account, their token would *still* satisfy the wildcard, since
the literal name prefix is identical and the wildcard just absorbs whatever
ID follows. The [AWS community guidance on this change](https://dev.to/aws-builders/github-changed-its-oidc-subject-claims-and-broke-my-aws-deploys-for-new-repos-2cfp)
is explicit: **pin the ID, don't wildcard it.**

**Getting your exact IDs doesn't require running a workflow — and doesn't
require the command line either.** Two ways to get them, easiest first:

- **Via the UI (confirmed, this is the easiest option):** go to the repo's
  **Settings → Actions → OIDC**. Under **Subject claim**, you'll see:
  - **Use default template** (checked) and **Use immutable subject claim**
    (checked, greyed out/locked — "Automatically enabled for this
    repository" for repos created after July 15, 2026)
  - A **Default subject claim prefix** box showing the exact value, e.g.
    `repo:<owner>@<owner-id>/<repo>@<repo-id>` with a green checkmark next
    to it, and the hint text "Use this prefix when configuring trust
    policies in your cloud provider" — which is exactly what you're doing
    here. No CLI, no API call, no workflow run — just read the value
    straight off this box.
- **Via the API** (handy if you're scripting this, or want to confirm a
  different account/repo without opening the UI): the same numeric IDs are
  returned by GitHub's public REST API for any user/org and repo:

  ```bash
  curl -s https://api.github.com/users/<YOUR_GITHUB_USERNAME> | grep '"id"'
  curl -s https://api.github.com/repos/<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME> | grep '"id"'
  ```

  (For a **private** repo, add `-H "Authorization: Bearer <a PAT>"` — the
  unauthenticated endpoint only sees public repos.)

Either way: the owner ID is the same for every repo you own — look it up
once and reuse it. If you add another repo under the same account later,
you only need to look up that new repo's ID. Both values are stable and
knowable before you've written a single workflow run.

With both numbers in hand, write the trust policy as an exact match:

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
          "token.actions.githubusercontent.com:sub": "repo:<owner>@<owner-id>/<repo>@<repo-id>:environment:production",
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:environment": "production",
          "token.actions.githubusercontent.com:repository": "<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>",
          "token.actions.githubusercontent.com:ref": "refs/heads/main"
        }
      }
    }
  ]
}
```

Every condition is `StringEquals` — no wildcards anywhere.

**Why the `ref` condition matters here, specifically:** an environment-based
`sub` (`...:environment:production`) is emitted identically **no matter
which branch triggered the run** — `fetch-secret.yml` allows
`workflow_dispatch` from any branch selection, so without `ref`, a run
dispatched from a non-`main` branch would still produce a `sub` that
matches. AWS's console will actually warn you about this if you save the
policy without it ("Using a wildcard... specify the branch name... in a
`ref` condition key") — not because there's a literal wildcard character
anywhere, but because omitting branch info from the only scoping claim is
functionally the same thing. GitHub still emits `ref` as its own top-level
claim even when `sub` uses the environment format, so adding this condition
costs nothing and closes the gap. Save it.

Want this policy explained condition-by-condition, line by line? See
[`04-trust-policy-explained.md`](04-trust-policy-explained.md).

> **Alternative claim: `job_workflow_ref`.** AWS's own policy validator
> error names this as the other accepted claim besides `sub`
> (`"...must evaluate...sub or job_workflow_ref..."`). It pins to the
> workflow **file** instead of the repo+environment:
> `"token.actions.githubusercontent.com:job_workflow_ref": "<owner>/<repo>/.github/workflows/fetch-secret.yml@refs/heads/main"`.
> Not obviously better or worse — it breaks if you rename/move the workflow
> file instead of if you rename the environment. This repo doesn't use it,
> and we haven't verified whether it also carries immutable IDs.

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
