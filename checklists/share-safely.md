# Share Safely

Use this before sharing a prompt, GEDCOM, screenshot, issue, pull request, or exported tree.

## Redact Living People

- [ ] Remove exact birth dates for living or possibly living people.
- [ ] Remove addresses, phone numbers, emails, workplaces, schools, and private notes.
- [ ] Replace living-person names with `Living Person A`, `Living Parent`, or similar labels.
- [ ] Remove DNA match names unless you have consent.
- [ ] Check screenshots for sidebars, tabs, filenames, and browser autofill.

## Redact Sensitive Context

- [ ] Remove adoption, parentage, medical, legal, and financial details unless explicitly safe to share.
- [ ] Replace private family surnames with fictional names in examples.
- [ ] Replace exact document scans with short excerpts or synthetic examples.
- [ ] Keep local denylist terms out of public files.

## Before Publishing

- [ ] Run `scripts/validate-repo` if you are contributing to this repo.
- [ ] Run `scripts/privacy-audit-repo` if you maintain `.private/anonymization-denylist.txt`.
- [ ] Re-open the exported file and inspect it manually.
- [ ] Ask whether the same result can be shared with less detail.

## Safe Defaults

- [ ] Share methodology before raw data.
- [ ] Share deceased-person records before living-person details.
- [ ] Share source citations before private scans.
- [ ] When unsure, do not publish the detail.

