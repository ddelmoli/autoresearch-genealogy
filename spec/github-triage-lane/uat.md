# UAT: GitHub Triage Lane

## Spec 01: Baseline And PR Gates
**Demo**: Repository validation is green before PR triage.
- [ ] `scripts/validate-repo` prints `validate-repo: ok`.
- [ ] `LC_ALL=C scripts/validate-repo` prints `validate-repo: ok`.
- [ ] `rg "Prusak Vault|/Users/mattprusak" scripts spec/github-triage-lane` prints no matches.

## Spec 02: Durable Triage State
**Demo**: The local triage script can sync and report GitHub state without mutating GitHub.
- [ ] `scripts/github-triage --help` prints usage.
- [ ] `scripts/github-triage sync --repo mattprusak/autoresearch-genealogy` writes `.github-triage/state.pstore`.
- [ ] `scripts/github-triage report --repo mattprusak/autoresearch-genealogy` prints a markdown report with issue and PR classifications.
- [ ] `git status --ignored --short .github-triage` shows the state directory as ignored.

## Spec 03: Issue Intake And Cleanup
**Demo**: New issues are structured, and current public items have an explicit maintainer route.
- [ ] `ruby -e 'require "yaml"; Dir[".github/ISSUE_TEMPLATE/*.yml"].each { |p| YAML.safe_load(File.read(p)); puts p }'` lists all issue template files without errors.
- [ ] Open the GitHub new issue page and confirm blank issues are disabled.
- [ ] Open each issue template and confirm it warns against living-person private details.
- [ ] Run `scripts/github-triage report --repo mattprusak/autoresearch-genealogy --refresh` and verify every open issue and PR has a recommended action.
- [ ] Check GitHub issue and PR queues for labels, comments, closures, merges, or deferrals that match the report.
