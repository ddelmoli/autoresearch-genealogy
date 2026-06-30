# GitHub Triage Lane

This repository can receive issue requests and pull requests from people who have very different goals: some are asking for genealogy help, some are contributing archive guidance, and some are unrelated or unsafe for a public tracker.

Use `scripts/github-triage` to keep that queue reviewable without giving an agent unattended write authority.

## Operating Model

The lane has two parts:

1. Research lane: fetch open issues and pull requests, classify them, write local state, and produce a markdown report.
2. Repair lane: only after maintainer authorization, apply labels, comments, closures, merges, or a maintainer branch.

The script is read-only against GitHub. It shells to `gh`, stores a local PStore database under `.github-triage/state.pstore`, and prints recommendations. The state directory is ignored because issue bodies can contain private genealogy details.

## Commands

```bash
scripts/github-triage sync --repo mattprusak/autoresearch-genealogy
scripts/github-triage report --repo mattprusak/autoresearch-genealogy
scripts/github-triage report --repo mattprusak/autoresearch-genealogy --refresh
```

## Classifications

| Classification | Meaning | Default action |
|---|---|---|
| `repair-ready` | A small tooling fix that can be validated mechanically. | Run validation, merge or include in a maintainer branch. |
| `docs-ready` | Documentation-only contribution that appears relevant. | Review source claims and links, run validation, then merge or include. |
| `needs-human-review` | Material change or new tooling that needs careful review. | Inspect patch, test locally, then decide. |
| `draft` | Pull request is explicitly draft. | Wait for author. |
| `stacked` | Pull request depends on another pull request. | Resolve the base change first. |
| `usage-question` | User is asking how to use the toolkit. | Answer publicly, update docs if needed, then close. |
| `needs-info` | User wants help but did not provide enough redacted context. | Request redacted self-service intake. Do not run public family research. |
| `privacy-risk` | Issue may expose living-person or private details. | Ask author to redact. Avoid quoting the sensitive detail. |
| `spam` | Unrelated promotion or obvious junk. | Close as unrelated. |
| `duplicate-docs-paste` | Issue body appears to be pasted repo documentation. | Close as accidental duplicate. |

## Maintainer Gate

Before merging or closing anything:

1. Run `scripts/validate-repo`.
2. For validator changes, also run `LC_ALL=C scripts/validate-repo`.
3. For archive guides, check that new external claims are generic and sourceable.
4. For prompts and examples, verify they do not add real family data.
5. For public genealogy requests, do not research a private family in the issue thread. Route the user to the starter docs and ask for redacted, deceased-person facts only.

## Labels

The triage script recommends only existing repository labels: `bug`, `documentation`, `duplicate`, `enhancement`, `invalid`, `question`, and `wontfix`. Labels are advisory. The script does not apply them.
