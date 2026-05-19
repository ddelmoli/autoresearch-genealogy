# Review Card: Timeline Gap Analysis

Prompt: [07 Timeline Gap Analysis](../prompts/07-timeline-gap-analysis.md)

## Good Output

- Missing life events are listed by person.
- Suggested record types fit the time, place, and religion.
- The output distinguishes missing records from missing facts.
- Search priorities are realistic.
- Negative results are preserved.

## Red Flags

- The AI invents dates to fill gaps.
- A record type is suggested for a place or period where it did not exist.
- The timeline ignores migration distance or historical context.
- Every gap is treated as equally important.

## Verify Manually

- Check whether the suggested record type exists for the location.
- Confirm the person was likely in that place at that time.
- Search one high-priority gap before accepting the full plan.
- Use [Verify An AI Finding](../checklists/verify-an-ai-finding.md).

## Reject The Result When

- The gap plan creates facts instead of research targets.
- The proposed search cannot be tied to a real archive or record set.
- The timeline contradicts already sourced events.

## Next Prompt

Run [08 Open Question Resolution](../prompts/08-open-question-resolution.md).

