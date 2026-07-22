#!/usr/bin/env ruby
# frozen_string_literal: true
#
# validate-genealogy-vault.rb - Structure and privacy validator for the live
# genealogy vault (not this repo; see validate-repo for that). Checks that the
# core research files and the methodology mirror are present, that the mirror
# excludes repo internals, and that living/unknown person files do not leak
# exact dates. Relocated out of the vault (vaults hold markdown only).
#
# Usage:
#   ruby scripts/validate-genealogy-vault.rb
#   GENEALOGY_VAULT="/path/to/Vault/Genealogy" ruby scripts/validate-genealogy-vault.rb

require "date"
require "yaml"

DEFAULT_VAULT_NAME = [%w[Pru sak].join, "Vault"].join(" ")
ROOT = ENV["GENEALOGY_VAULT"] || File.expand_path(File.join("Vaults", DEFAULT_VAULT_NAME, "Genealogy"), Dir.home)
CORE_FILES = %w[
  _Index.md
  Family_Tree.md
  Research_Log.md
  Open_Questions.md
  Data_Inventory.md
  Timeline.md
  Genetic_Profile.md
  Chromosome_Painting.md
  Witness_Network.md
  Unresolved_Persons.md
  Research_Strategy.md
].freeze
TOOLKIT_FILES = %w[
  _Toolkit/autoresearch-genealogy/START_HERE.md
  _Toolkit/autoresearch-genealogy/guides/privacy-mode.md
  _Toolkit/autoresearch-genealogy/guides/prompt-picker.md
  _Toolkit/autoresearch-genealogy/guides/no-obsidian-setup.md
  _Toolkit/autoresearch-genealogy/checklists/share-safely.md
  _Toolkit/autoresearch-genealogy/review-cards/01-tree-expansion.md
  _Toolkit/autoresearch-genealogy/review-cards/12-dna-chromosome-analysis.md
].freeze

errors = []

def rel(path)
  path.delete_prefix("#{ROOT}/")
end

def frontmatter_for(path, errors)
  text = File.read(path)
  return {} unless text.start_with?("---\n")

  yaml = text.split(/^---\s*$/, 3)[1]
  YAML.safe_load(yaml, permitted_classes: [Date]) || {}
rescue Psych::SyntaxError, Psych::DisallowedClass => e
  errors << "#{rel(path)}: invalid YAML frontmatter: #{e.message}"
  {}
end

# --------------------------------------------------------------------------
# Day-precision: THE rule, one place per language, for "does this value disclose
# a specific DAY?". Every privacy call site below references it; do not
# re-implement it inline.
#
# Until 22 JUL 2026 `exact_date?` matched ONLY ISO `YYYY-MM-DD`, while the body
# scan already matched `3 Sep 1780`. Adopting GEDCOM 7 `DateValue` for born/died
# (spec/structured-dates) makes `born: '3 SEP 1780'` a legal frontmatter value —
# under the ISO-only rule that returned false and the gate would have PASSED a
# living person's exact date of birth, with no error and no warning. Hence one
# predicate covering both notations, shared by both call sites.
#
# DAY-PRECISION is the trigger, not the presence of a year. `1780`, `ABT 1780`,
# `BEF 1780`, `BET 1779 AND 1781` stay permitted for a living person: the vault
# publishes approximate years for the living by design ("Living people stay
# terse (approximate year only, no exact DOB)").
#
# It SEARCHES rather than anchors, so a day-precise bound inside a range
# (`BET 3 SEP 1780 AND 1790`) trips it too. That is deliberate fail-closed
# behaviour for a privacy gate.
#
# Years are `\d{4}` on purpose. This gate protects LIVING people, none of whom
# have a 3-digit birth year; wider year support belongs to gdate (Spec 02), and
# widening it here would only add false positives.
MONTH_ABBR = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
DAY_PRECISE = Regexp.union(
  /\b\d{4}-\d{2}-\d{2}\b/,                                        # ISO 1780-09-03
  /\b\d{1,2}\s+(?:#{MONTH_ABBR})[a-z]*\.?\s+\d{4}\b/i,            # GEDCOM 7 / prose: 3 SEP 1780
  /\b(?:#{MONTH_ABBR})[a-z]*\s+\d{1,2},\s+\d{4}\b/i               # US prose: Sep 3, 1780
).freeze

# Frontmatter keys screened against DAY_PRECISE for a living/unknown person.
# The `*_phrase` keys are the GEDCOM 7 PHRASE escape hatch — free text, so they
# need the SAME screen as the date keys, not a weaker one.
PRIVATE_DATE_KEYS = %w[born died born_phrase died_phrase].freeze

def day_precise?(text)
  DAY_PRECISE.match?(text.to_s)
end

def exact_date?(value)
  return true if value.is_a?(Date)

  day_precise?(value)
end

def exact_private_date_in_body?(text)
  day_precise?(text)
end

CORE_FILES.each do |file|
  errors << "missing core file #{file}" unless File.exist?(File.join(ROOT, file))
end

TOOLKIT_FILES.each do |file|
  errors << "missing mirrored toolkit file #{file}" unless File.exist?(File.join(ROOT, file))
end

%w[
  _Toolkit/autoresearch-genealogy/.git
  _Toolkit/autoresearch-genealogy/.private
  _Toolkit/autoresearch-genealogy/privacy-audits
].each do |path|
  errors << "mirrored toolkit must not include #{path}" if File.exist?(File.join(ROOT, path))
end

root_entries = Dir.children(ROOT)
CORE_FILES.each do |file|
  lower = file.downcase
  next if lower == file

  errors << "duplicate lowercase core file #{lower}; use #{file}" if root_entries.include?(lower)
end

Dir[File.join(ROOT, "**/*.md")].sort.each do |path|
  text = File.read(path)
  errors << "#{rel(path)}: old confidence frontmatter remains" if text.match?(/^confidence:/)

  data = frontmatter_for(path, errors)
  next unless data["type"] == "person"

  %w[life_status evidence_tier profile_status].each do |key|
    errors << "#{rel(path)}: person file missing #{key}" unless data.key?(key)
  end

  if %w[living unknown].include?(data["life_status"])
    PRIVATE_DATE_KEYS.each do |key|
      errors << "#{rel(path)}: #{data["life_status"]} person must not expose exact #{key} date" if exact_date?(data[key])
    end

    body = text.split(/^---\s*$/, 3)[2] || text
    if exact_private_date_in_body?(body)
      errors << "#{rel(path)}: #{data["life_status"]} person body contains exact date-like private detail"
    end
  end
end

if errors.empty?
  puts "validate-genealogy-vault: ok"
else
  warn "validate-genealogy-vault: #{errors.length} failure(s)"
  errors.each { |message| warn "- #{message}" }
  exit 1
end
