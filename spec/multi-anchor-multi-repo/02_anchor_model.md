# Spec 02: Anchor Model
**Goal:** Let a vault be anchored on an individual or a married couple, with generation counting keyed on the anchor set. Conversion from individual to couple must not renumber any existing entry.
**Depends on:** 01

## Design notes
- A married couple is one generation. Generation 1 is the set of anchor people (one or two). Generation 2 is their parents (up to four people for a couple), and so on. The two ancestral trees above Generation 1 are disjoint absent consanguinity.
- Because a couple's second tree is entirely new Generation 2+ entries, converting an `individual` vault to a `couple` vault adds a second Generation 1 person and their ancestors without changing any existing generation number. This is a required property, not an incidental one.

## Requirements
- Generation-counting logic and any generation-anchor documentation must reference the anchor *set* from `get_anchor`, not a single subject.
- Prompts that take `[SUBJECT_PID]` must accept the anchor set: for a couple, the pedigree-root and gen-counting steps operate per anchor person. Update the prompt input docs so `[SUBJECT_PID]` reads as "an anchor person's PID (one per anchor spouse for a couple vault)".
- `CLAUDE.instance.md` guidance (the per-client subject and generation-anchor table) must show how a couple anchor is expressed. The tracked framework docs must not hardcode a single-subject assumption.
- Any script or audit that currently assumes one Generation 1 person must accept an anchor set. Identify these by grepping for single-subject assumptions before implementation.

## Files
- Modify: prompts that reference `[SUBJECT_PID]` or a single subject (`prompts/01-tree-expansion.md`, `17`, `18`, `19`, `prompts/README.md`)
- Modify: `CLAUDE.method.md` and the tracked generation-counting guidance
- Modify: any script that hardcodes a single Generation 1 anchor (enumerate during implementation)

## Boundary Map
- **Produces**: an anchor-set generation model and prompt inputs that accept one or two anchor people.
- **Consumes**: `get_anchor` from Spec 01.

## Acceptance Criteria
- [ ] A `couple` anchor with two people is accepted everywhere `[SUBJECT_PID]` is consumed.
- [ ] Converting a fixture vault from `individual` to `couple` leaves all pre-existing generation numbers unchanged.
- [ ] Generation counting produces Generation 1 = anchor set, Generation 2 = union of both people's parents.
- [ ] `scripts/gen_person_index.py --integrity` passes on a couple-anchor fixture.

## Test Plan
- Build a small couple-anchor fixture (two Generation 1 people, disjoint parents) and run the roster and integrity check.
- Diff generation numbers of a fixture before and after an individual-to-couple conversion; expect no change to existing entries.
