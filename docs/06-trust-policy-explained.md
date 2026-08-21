# Trust Policy, Explained Line by Line

This walks through exactly what the final IAM role trust policy from
[`02-aws-console-setup.md`](02-aws-console-setup.md) Step 3a does and why
each line exists. Useful if you want to actually understand the policy
you pasted in, not just copy it.

```json
{
    "Version": "2012-10-17",
```
Fixed IAM policy-language schema version. Not a real date — just AWS's way
of versioning the policy grammar. Every IAM policy uses this exact string.

```json
    "Statement": [
        {
            "Effect": "Allow",
```
One statement, granting (not denying) whatever the `Action` below allows —
but only when every `Condition` further down matches.

```json
            "Principal": {
                "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
            },
```
**Who** is allowed to try this: not an IAM user or another AWS account, but
a **federated** identity — anyone holding a valid token signed by the OIDC
provider registered at that ARN (the GitHub Actions provider created in
Step 1). This is what makes GitHub's tokens acceptable to AWS at all.

```json
            "Action": "sts:AssumeRoleWithWebIdentity",
```
**What** they're allowed to do: exchange that OIDC token for temporary AWS
credentials. This is the OIDC-specific sibling of the regular
`sts:AssumeRole`.

```json
            "Condition": {
                "StringEquals": {
```
Everything inside must match **exactly** — this policy uses only
`StringEquals`, no `StringLike`, no wildcards anywhere. Without these
conditions, *any* GitHub Actions workflow from *anyone's* repo could
assume this role. This block is the actual security boundary; the
`Principal`/`Action` above just say "OIDC tokens can request this," not
"any OIDC token can."

```json
                    "token.actions.githubusercontent.com:sub": "repo:<owner>@<owner-id>/<repo>@<repo-id>:environment:production",
```
The token's **subject claim** — GitHub's answer to "which exact workflow
run is this." Decoded: repo owner (permanently tied to the GitHub account's
numeric ID), repo name (permanently tied to the repo's numeric ID), running
under the `production` Environment. The `@<id>` parts are GitHub's
**immutable subject claims** feature (see Step 3a for the full
explanation) — pinned to the account/repo forever, immune to the name ever
being deleted and reused by a different account.

```json
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
```
The token's **audience claim** — confirms it was minted specifically to
talk to AWS STS, not some other service that might also request a GitHub
OIDC token for a different purpose.

```json
                    "token.actions.githubusercontent.com:environment": "production",
```
A separate, plain claim restating the Environment. Redundant with part of
`sub` above, but kept so a human reading this policy doesn't have to decode
the `sub` string to see at a glance that it's scoped to `production` (the
Environment with the required-reviewer approval gate).

```json
                    "token.actions.githubusercontent.com:repository": "<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>",
```
Same idea — a clean, unmangled `owner/repo` claim with no ID suffixes,
also redundant with `sub`, also there purely for human readability.

```json
                    "token.actions.githubusercontent.com:ref": "refs/heads/main"
```
The actual git branch the run came from. This is the piece that closes a
real gap: the environment-based `sub` never encodes a branch on its own, so
without this, a `workflow_dispatch` run from a non-`main` branch would
still produce a matching token. See Step 3a for how this was discovered
(AWS's console flags its absence as a wildcard-equivalent risk).

```json
                }
            }
        }
    ]
}
```
Closing braces.

## Net effect

AWS hands out credentials only when **all five** conditions match
simultaneously: right repo+account+repo-ID (via `sub`), right audience,
right environment, right repository name, and right branch. `repository`
and `environment` are technically redundant with what `sub` already
encodes — they're there so someone reading the policy doesn't need to
mentally decode an opaque ID-laden string to understand what it's scoped
to.
