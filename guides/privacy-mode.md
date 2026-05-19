# Privacy Mode

Use privacy mode before pasting family history into a public AI tool, opening an issue, sharing a GEDCOM, or contributing examples.

## What Never To Paste

Do not paste these for living or possibly living people:

- Exact birth dates.
- Addresses.
- Phone numbers.
- Email addresses.
- Workplaces, schools, or current locations.
- Medical, adoption, parentage, legal, financial, or conflict details.
- DNA match names, messages, kit numbers, or raw segment files without consent.
- Private document scans that include living people.

## What To Redact

Redact or generalize:

- Names of living people.
- Exact dates for living people.
- Small places that identify a living person.
- Private filenames and folder paths.
- Account IDs, tree IDs, subscription screenshots, and browser sidebars.
- Any source note that would expose a living person indirectly.

## Living-Person Checklist

- [ ] Living people are marked `Living` or `life_status: living`.
- [ ] Possibly living people are marked `life_status: unknown`.
- [ ] Exact dates are removed from public prompts.
- [ ] Contact and location details are removed.
- [ ] Autonomous prompts are told not to search living people.
- [ ] Shared GEDCOM exports hide or omit living people.

## Before And After Redaction

Fictional unsafe prompt:

```text
Search for Casey Example, born March 18, 1984 in Harbor Town, now living at 22 Pine Street. Their DNA match Taylor Example says the biological father may be Morgan Vale.
```

Safer version:

```text
Do not search living people. In this branch, Living Person A has a private DNA lead involving a possible parentage question. Search only deceased ancestors already listed in Family_Tree.md and keep living-person details redacted.
```

Fictional unsafe source note:

```text
Riley Example, born July 4, 1979, emailed me from riley@example.test and said their current address is 10 Cedar Lane.
```

Safer version:

```text
Living relative provided oral-history context in 2026. Exact private details are withheld. Treat as a clue, not proof.
```

## How To Anonymize A Prompt

1. Replace living-person names with labels like `Living Person A`.
2. Replace exact dates with decades or `Living`.
3. Replace addresses with city or state only, if needed.
4. Replace private surnames with fictional surnames if the example will be public.
5. Remove DNA match names and kit identifiers.
6. Keep the research question, source type, and evidence problem.

Good anonymization preserves the structure of the problem while removing the private identity.

## GEDCOM Sharing

Before sharing a GEDCOM:

- Export with living people hidden or privatized.
- Re-open the file and search for living-person names.
- Search for exact modern dates, emails, phone numbers, and addresses.
- Check notes, sources, media paths, and submitter fields.
- Use [Share Safely](../checklists/share-safely.md).
- Run [04 GEDCOM Completeness](../prompts/04-gedcom-completeness.md) only after redaction settings are clear.

## Public Repo Safety

For contributors:

- Use fictional or synthetic examples.
- Do not paste from a private family vault.
- Do not commit `.private/`.
- Do not commit privacy audit reports.
- Keep `.private/anonymization-denylist.txt` local and untracked.
- Put sensitive surnames, places, and exact phrases in the denylist.

Run:

```bash
scripts/validate-repo
scripts/privacy-audit-repo
```

The validation script scans tracked files for local denylist terms. The privacy audit script also scans reachable Git history. Reports are written outside the repo by default under `~/.cache/autoresearch-genealogy/privacy-audits/`.

Failed audit reports do not print the exact private term. They show a short fingerprint, term length, file path, and line number so you can fix the leak using your local denylist.

## Private Denylist Example

Create this only in your local checkout:

```text
# .private/anonymization-denylist.txt
private surname
private place
exact private phrase
```

Do not commit that file.

## When In Doubt

- Share the method, not the private data.
- Use the synthetic fixture under `fixtures/minimal-vault/`.
- Use the [First Run Walkthrough](../walkthroughs/first-run.md).
- Keep uncertain or sensitive material local.
