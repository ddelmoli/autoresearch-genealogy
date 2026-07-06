# Open Question Resolution

Systematically attack every open question in your research using web sources.

> **Sharded trees (optional):** if your `Family_Tree.md` has grown and been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in this prompt as also covering those shard files: read them all, and route new people to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder

## Autoresearch Configuration

**Goal**: For every open question in `vault/Open_Questions.md`, execute the search strategy described and attempt resolution.

**Metric**: Number of open questions with status OPEN (not RESOLVED or PARTIALLY_RESOLVED)

**Direction**: Minimize (lower is better)

**Verify**: `grep -c "OPEN" vault/Open_Questions.md` (count lines containing OPEN but not PARTIALLY or RESOLVED)

**Guard**:
- Respect the confidence tiers. Do not mark a question as RESOLVED unless the evidence meets the Strong Signal standard (two independent sources, or one authoritative primary source).
- Mark as PARTIALLY_RESOLVED when progress is made but the question is not definitively answered.
- Do not change an answer that is already marked RESOLVED unless new contradicting evidence is found.

**Iterations**: 15

**Protocol**:

1. **Read all open questions**: Parse `vault/Open_Questions.md`. For each question with status OPEN, extract:
   - The exact question
   - The search strategy listed
   - The decisive records that would resolve it
   - Any partial evidence already gathered

2. **Prioritize**: Attack questions in this order:
   a. High priority with HIGH solvability
   b. High priority with MODERATE solvability
   c. Medium priority with HIGH solvability
   d. Everything else

3. **For each question**:
   a. Execute the search strategy as written (web searches, database lookups)
   b. Evaluate results against the confidence tier framework
   c. Update Open_Questions.md with findings
   d. If resolved: mark RESOLVED with date, brief statement, and source. Move the full resolution text (question, answer, and all supporting evidence) to `vault/Open_Questions_Resolved.md`, appending it as a new entry with a level-2 heading and the resolution date.
   e. If partially resolved: mark PARTIALLY_RESOLVED with what was found and what remains
   f. If no progress: log the searches attempted as negative results in `vault/logs/YYYY-MM-DD-open-questions.md` (use today's date)

4. **Cascade updates**: When resolving a question changes facts in the tree:
   a. Update the appropriate Family Tree shard (route by the line's Region per the File Index in `Family_Tree.md`)
   b. Update affected person files
   c. Update Timeline.md
   d. Check whether the resolution opens new questions (add to Open_Questions.md)

5. **Report**: After all iterations, summarize: questions resolved, questions partially resolved, questions with no progress, new questions discovered.

6. **Record Keeping**: After final iteration, create a session log at `vault/logs/YYYY-MM-DD-open-questions.md` (use today's date) with a summary of all questions addressed, searches attempted, and outcomes. Then add a one-line summary entry to the session index in `vault/Research_Log.md`.