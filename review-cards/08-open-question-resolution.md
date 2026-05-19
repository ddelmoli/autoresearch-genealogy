# Review Card: Open Question Resolution

Prompt: [08 Open Question Resolution](../prompts/08-open-question-resolution.md)

## Good Output

- Each question gets an answer, partial answer, or clear unresolved status.
- Sources and failed searches are logged.
- The output explains why a question remains open when evidence is missing.
- Next searches are narrow and practical.
- Evidence tiers remain conservative.

## Red Flags

- Every question appears “resolved” after one search.
- The AI accepts a weak source because it fits the desired answer.
- Failed searches are omitted.
- A broad brick wall produces a broad unspecific answer.

## Verify Manually

- Open the cited sources.
- Confirm the answer addresses the exact question.
- Check alternative explanations.
- Use [Verify An AI Finding](../checklists/verify-an-ai-finding.md).

## Reject The Result When

- The answer is unsupported.
- The source does not mention the target person or family.
- The result resolves a different question than the one asked.

## Next Prompt

Run [02 Cross-Reference Audit](../prompts/02-cross-reference-audit.md).

