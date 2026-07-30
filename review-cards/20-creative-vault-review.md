# Review Card: Creative Whole-Vault Enhancement & Extension Review

Prompt: [20 Creative Vault Review](../prompts/20-creative-vault-review.md)

## Good Output

- Every logged lead names a concrete, verifiable NEXT ACTION (a specific record to pull or search to run), not "investigate further."
- Each lead is tiered Strong / Moderate / Speculative, and speculative leads are flagged for human review, never acted on.
- Leads GENERATE research; no name, date, or place is written into a person entry from a lens inference alone.
- Negative lens results are logged ("pattern checked, no lead"), not silently dropped.
- Culture-appropriate naming/patronymic conventions are applied to each ancestor's own tradition.
- Corroborating lenses (patronymic + burial society + manifest pointing at the same person) are noted and raise the tier.
- Cemetery leads read all three signals — stone vitals/inscription, plot-adjacency kinship, and the interment-office record — and cross independent gravestone databases; a "no stone" across all is logged as a result.
- Living or possibly-living people are skipped for any web-facing lens.

## Red Flags

- A "lead" adopts a derived father's name or origin town straight into a person entry without finding the record.
- Surname or place coincidence alone is rated Strong or Moderate.
- The lead log inflates with speculation to raise the count.
- A generic naming rule is applied across cultures (e.g., an Ashkenazi rule to an Italian family).
- A previously documented dead-end (in `logs/` or `Open_Questions.md`) is re-proposed as new.
- A cemetery age or date is silently averaged with a census age instead of flagging a possible same-name mix-up.
- Plot-adjacency kinship is adopted as fact without confirming the relationship in a record.
- Leads have no downstream prompt / no way to execute them.

## Verify Manually

- Pick several leads and confirm each has a real, runnable next action.
- Spot-check a patronymic or namesake inference against the actual record grammar.
- Confirm speculative leads are quarantined, not queued for autonomous action.
- Confirm no vault person-entry vitals changed from this prompt (it is ideation only).

## Reject The Result When

- The output edits person entries with lens-inferred facts.
- Leads are surname/place coincidences dressed up as Strong/Moderate.
- The naming or chronological inference misreads the culture's convention.
- The run reports a lead count but the leads carry no next action.

## Next Prompt

Execute the top leads with the matching doing-prompt: [01 Tree Expansion](../prompts/01-tree-expansion.md), [05 Source Citation Audit](../prompts/05-source-citation-audit.md), [08 Open Question Resolution](../prompts/08-open-question-resolution.md), or [11 Immigration Search](../prompts/11-immigration-search.md).
