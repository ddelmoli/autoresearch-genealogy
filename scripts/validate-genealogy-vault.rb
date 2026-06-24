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

ROOT = ENV["GENEALOGY_VAULT"] || File.expand_path("Vaults/Prusak Vault/Genealogy", Dir.home)
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

def exact_date?(value)
  return true if value.is_a?(Date)

  value.to_s.match?(/\A\d{4}-\d{2}-\d{2}\z/)
end

def exact_private_date_in_body?(text)
  text.match?(/\b\d{4}-\d{2}-\d{2}\b/) ||
    text.match?(/\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4}\b/i) ||
    text.match?(/\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b/i)
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
    %w[born died].each do |key|
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
