# Review Card: Source Citation Audit

Prompt: [05 Source Citation Audit](../prompts/05-source-citation-audit.md)

## Good Output

- Under-sourced people are listed clearly.
- Claims are separated into sourced, weakly sourced, and unsourced.
- The audit distinguishes primary, secondary, and tertiary material.
- Missing citations become specific follow-up tasks.
- Evidence tiers are not inflated to hide gaps.

## Red Flags

- A person is marked complete because one copied tree exists.
- Citations point only to search-result pages.
- The audit counts two copied trees as two independent sources.
- Missing citations are fixed with vague source labels.

## Verify Manually

- Open a sample of cited sources.
- Confirm that each citation supports the exact claim.
- Check whether the sources are independent.
- Use [Verify An AI Finding](../checklists/verify-an-ai-finding.md).

## Reject The Result When

- Citations are generic or cannot be reopened.
- Source quality is misclassified.
- The audit upgrades speculative claims without new evidence.

## Next Prompt

Run [08 Open Question Resolution](../prompts/08-open-question-resolution.md).

