#!/usr/bin/env ruby
# frozen_string_literal: true
#
# test_privacy_gate.rb — regression tests for the living-person date gate in
# validate-genealogy-vault.rb (spec/structured-dates Spec 01).
#
# Runnable with no test framework, mirroring test_person_store.py:
#   ruby scripts/test_privacy_gate.rb      (exit 0 = pass)
#
# WHY THIS EXISTS. Adopting GEDCOM 7 `DateValue` for born/died makes
# `born: '3 SEP 1780'` a legal frontmatter value. The pre-22-JUL `exact_date?`
# matched ONLY `\A\d{4}-\d{2}-\d{2}\z`, so the moment that value became legal the
# gate would have stopped recognising an exact date for a LIVING person — no
# error, no warning, no failing test. A vault whose Generation-1 anchors are
# living — the common case — would have been exposed. This file is the test that
# had to exist before any date could be written in the new grammar.
#
# It builds a throwaway fixture vault (core + mirrored-toolkit stubs so the
# structural checks are satisfied and only date findings remain), runs the real
# validator against it via GENEALOGY_VAULT, and asserts the exact error set.

require "fileutils"
require "tmpdir"

VALIDATOR = File.expand_path("validate-genealogy-vault.rb", __dir__)

PASS = [0]
FAIL = [0]

def check(cond, label)
  if cond
    PASS[0] += 1
    puts "  ok   #{label}"
  else
    FAIL[0] += 1
    puts "  FAIL #{label}"
  end
end

# name => [life_status, frontmatter date lines, expect_error?]
CASES = {
  "gedcom_day"      => ["living",   ["born: '3 SEP 1780'"],              true],
  "gedcom_julian"   => ["living",   ["born: 'JULIAN 30 JAN 1649'"],      true],
  "gedcom_approx"   => ["living",   ["born: 'ABT 1780'"],                false],
  "bare_year"       => ["living",   ["born: '1780'"],                    false],
  "phrase_day"      => ["living",   ["born_phrase: '3 September 1780'"], true],
  "iso_day"         => ["living",   ["born: 1780-09-03"],                true],
  "range_years"     => ["living",   ["died: 'BET 1779 AND 1781'"],       false],
  "deceased_gedcom" => ["deceased", ["born: '3 SEP 1780'",
                                     "born_phrase: '3 September 1780'",
                                     "died: 1901-11-12"],                false],
  "unknown_gedcom"  => ["unknown",  ["born: '3 SEP 1780'"],              true],
}.freeze

CORE = %w[
  _Index.md Family_Tree.md Research_Log.md Open_Questions.md Data_Inventory.md
  Timeline.md Genetic_Profile.md Chromosome_Painting.md Witness_Network.md
  Unresolved_Persons.md Research_Strategy.md
].freeze
TOOLKIT = %w[
  START_HERE.md guides/privacy-mode.md guides/prompt-picker.md
  guides/no-obsidian-setup.md checklists/share-safely.md
  review-cards/01-tree-expansion.md review-cards/12-dna-chromosome-analysis.md
].freeze

def build_vault(root)
  CORE.each { |f| File.write(File.join(root, f), "# stub\n") }
  TOOLKIT.each do |f|
    path = File.join(root, "_Toolkit/autoresearch-genealogy", f)
    FileUtils.mkdir_p(File.dirname(path))
    File.write(path, "# stub\n")
  end
  CASES.each do |name, (life_status, date_lines, _)|
    body = <<~MD
      ---
      type: person
      name: "Fixture #{name}"
      life_status: #{life_status}
      evidence_tier: moderate_signal
      profile_status: stub
      #{date_lines.join("\n")}
      ---

      Body text with no dates in it.
    MD
    File.write(File.join(root, "#{name}.md"), body)
  end
end

Dir.mktmpdir("privacy-gate-fixture") do |root|
  build_vault(root)
  output = IO.popen({ "GENEALOGY_VAULT" => root, "LANG" => "en_US.UTF-8" },
                    ["ruby", "-E", "utf-8", VALIDATOR],
                    err: [:child, :out]) { |io| io.read }
  lines = output.lines.map(&:chomp)

  # Nothing structural should fire; if it does, the fixture is wrong, not the gate.
  structural = lines.select { |l| l.start_with?("- ") && !l.include?("must not expose exact") }
  check(structural.empty?,
        "fixture is structurally clean (no non-date findings)#{structural.empty? ? "" : ": #{structural.inspect}"}")

  CASES.each do |name, (life_status, _, expect_error)|
    hit = lines.any? { |l| l.include?("#{name}.md: #{life_status} person must not expose exact") }
    if expect_error
      check(hit, "#{life_status} + #{name}: BLOCKED")
    else
      check(!hit, "#{life_status} + #{name}: permitted")
    end
  end

  # Body-text path must keep working off the same shared predicate.
  File.write(File.join(root, "body_leak.md"), <<~MD)
    ---
    type: person
    name: "Fixture body_leak"
    life_status: living
    evidence_tier: moderate_signal
    profile_status: stub
    born: 'ABT 1780'
    ---

    She was born 3 SEP 1780 in Boston.
  MD
  out2 = IO.popen({ "GENEALOGY_VAULT" => root, "LANG" => "en_US.UTF-8" },
                  ["ruby", "-E", "utf-8", VALIDATOR],
                  err: [:child, :out]) { |io| io.read }
  check(out2.include?("body_leak.md: living person body contains exact date-like private detail"),
        "living + GEDCOM date in body: BLOCKED")
end

puts "\n#{PASS[0]} passed, #{FAIL[0]} failed"
exit(FAIL[0].zero? ? 0 : 1)
