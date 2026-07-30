# Review Card: Edge Verification

Prompt: [18 Edge Verification](../prompts/18-edge-verification.md)

## Good Output

- Each resolved edge says which surface confirmed it, and on what date.
- Edges that cannot be confirmed keep their `?` and gain a written reason.
- The unverified count falls toward a stated floor, not toward zero.
- CONTRADICTED edges are raised as questions, not corrected in place.
- Each edge was checked from the child's own page, not a parent's child list.

## Red Flags

- The `?` count drops sharply in one pass.
- A `?` was stripped because a tree agreed, with no record behind it.
- A `?` that recorded a *scholarly doubt* was removed as if it meant "not yet checked".
- An absent relative is reported as a disproof rather than a gap in the source.
- The floor is described as zero, which would mean every edge is confirmable.

## Verify Manually

- Pick two cleared edges and confirm the cited surface actually shows the relationship.
- Pick one surviving `?` and confirm its reason is specific, not "unverified".
- Confirm no edge was cleared on a name-and-approximate-date match alone.
- Use [Verify An AI Finding](../checklists/verify-an-ai-finding.md).

## Reject The Result When

- A number moved but the entries do not say what was read.
- Any `?` was removed from an edge whose entry documents a source-based doubt.
- Confirmations rest on a tree that may itself be copying your vault.

## Next Prompt

Run [17 FamilySearch Tree Contribution](../prompts/17-familysearch-tree-contribution.md) for the edges that are correct but missing upstream.
