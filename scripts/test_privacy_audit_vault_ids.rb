#!/usr/bin/env ruby
# frozen_string_literal: true
#
# test_privacy_audit_vault_ids.rb — the vault person-id check must not pass on zero.
#
# Runnable with no test framework, mirroring test_privacy_audit_locale.rb:
#   ruby scripts/test_privacy_audit_vault_ids.rb      (exit 0 = pass)
#
# WHY THIS EXISTS (13 SEP 2026). privacy-audit-repo resolves vault `P-` ids against
# the reachable vault and flags any that name a real person. Its reader was one
# regex, `\{id: (P-...)` over `Family_Tree*.md`, and it resolved NOTHING -- while the
# audit still printed `ok` -- in two ordinary cases:
#
#   - a vault on the `file` person model, the framework default, whose ids live in
#     per-person frontmatter the reader never opened;
#   - a narrative meta line whose `id` key is not written first, valid YAML that
#     person_store parses.
#
# An empty id set is not nil, so neither fell into SKIPPED: the report said
# "resolved against 0 person ids" and passed. Every case below builds a scratch
# vault, points AUTORESEARCH_VAULT at it, and runs the real script.
#
# The "real person" in these vaults is a FIXTURE id that already sits in the
# tracked tree, so a working reader must report it as a finding and a blind one
# passes it. No real vault data is read or written.

require "open3"
require "tmpdir"
require "fileutils"

ROOT = File.expand_path("..", __dir__)
SCRIPT = File.join(ROOT, "scripts", "privacy-audit-repo")
DENYLIST = File.join(ROOT, ".private/anonymization-denylist.txt")

# In the tracked tree (a test fixture), so a vault naming it must produce a finding.
TRACKED_ID = "P-TST001"
# Built at runtime so the literal never lands in the tracked tree.
UNTRACKED_ID = "P-#{'7W' * 3}"

failures = []

def check(desc, failures)
  ok, detail = yield
  puts(format("  %-70s %s", desc, ok ? "ok" : "FAIL"))
  failures << "#{desc}: #{detail}" unless ok
end

puts "test_privacy_audit_vault_ids.rb"

unless File.exist?(DENYLIST)
  warn "SKIP: no denylist at .private/ — the script aborts before the vault check"
  exit 0
end

tracked, = Open3.capture2("git", "-C", ROOT, "grep", "-l", TRACKED_ID)
untracked, = Open3.capture2("git", "-C", ROOT, "grep", "-l", UNTRACKED_ID)
unless !tracked.strip.empty? && untracked.strip.empty?
  warn "SKIP: fixture preconditions do not hold (#{TRACKED_ID} must be tracked, " \
       "the runtime id must not be)"
  exit 0
end

# Returns [exit status, the report's vault line, the report's vault section].
def audit(files)
  Dir.mktmpdir("privacy-vault-") do |vault|
    files.each do |rel, text|
      path = File.join(vault, rel)
      FileUtils.mkdir_p(File.dirname(path))
      File.write(path, text)
    end
    Dir.mktmpdir("privacy-reports-") do |reports|
      env = { "AUTORESEARCH_VAULT" => vault, "PRIVACY_AUDIT_REPORT_DIR" => reports }
      _out, _err, status = Open3.capture3(env, SCRIPT)
      report = File.read(Dir.glob(File.join(reports, "*.md")).first.to_s) rescue ""
      line = report[/^- Vault person ids.*$/].to_s
      section = report[/## Vault Person-Id Findings.*?(?=^## Result)/m].to_s
      return [status.exitstatus, line, section]
    end
  end
end

NARRATIVE = %({"person_model": "narrative"})

puts "\nA working reader reports a real id, whatever the key order or model:"
rc, line, section = audit(
  ".autoresearch.json" => NARRATIVE,
  "Family_Tree_Scratch.md" => "**A Person** (b. 1850)\n" \
                              "- meta: {generation: 5, id: #{TRACKED_ID}, fs: TBD}\n"
)
check("narrative, `id` NOT the first key: the id is a finding", failures) do
  [rc == 1 && section.include?("- `sha256:"), "exit=#{rc} #{line}"]
end

rc, line, section = audit(
  ".autoresearch.json" => "{}",
  "people/A_Person.md" => "---\ntype: person\nname: A Person\nid: #{TRACKED_ID}\n---\n\nBody.\n"
)
check("file model (the default): a frontmatter id is a finding", failures) do
  [rc == 1 && section.include?("- `sha256:"), "exit=#{rc} #{line}"]
end

rc, line, = audit(
  ".autoresearch.json" => NARRATIVE,
  "Family_Tree_Scratch.md" => "**A Person** (b. 1850)\n- meta: {id: #{UNTRACKED_ID}, generation: 5}\n"
)
check("an id the repo never mentions passes, counted", failures) do
  [rc.zero? && line.include?("resolved against 1 person ids"), "exit=#{rc} #{line}"]
end

puts "\n⛔ Zero ids never passes quietly:"
rc, line, = audit(
  ".autoresearch.json" => "{}",
  "Family_Tree_Scratch.md" => "**A Person** (b. 1850)\n- meta: {id: #{UNTRACKED_ID}, generation: 5}\n"
)
check("model mismatch (narrative data, file config): BLIND, exit 1", failures) do
  [rc == 1 && line.include?("BLIND") && line.include?("resolved 0"), "exit=#{rc} #{line}"]
end

rc, line, = audit(
  ".autoresearch.json" => %({"person_model": "narative"}),
  "Family_Tree_Scratch.md" => "- meta: {id: #{UNTRACKED_ID}}\n"
)
check("an unknown person_model: BLIND, exit 1", failures) do
  [rc == 1 && line.include?("BLIND"), "exit=#{rc} #{line}"]
end

rc, line, = audit(
  ".autoresearch.json" => NARRATIVE,
  "Research_Log.md" => "# Research Log\n\nNothing yet.\n"
)
check("a vault with NO P- tokens at all is honestly empty: passes, says so", failures) do
  [rc.zero? && line.include?("holds no P- ids"), "exit=#{rc} #{line}"]
end

if failures.empty?
  puts "PASS"
  exit 0
end
puts "\nFAILURES:"
failures.each { |f| puts "  - #{f}" }
exit 1
