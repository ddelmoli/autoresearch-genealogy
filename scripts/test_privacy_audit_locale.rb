#!/usr/bin/env ruby
# frozen_string_literal: true
#
# test_privacy_audit_locale.rb — regression test for privacy-audit-repo under a
# LOCALE-LESS environment (the cron / git-hook / CI condition).
#
# Runnable with no test framework, mirroring test_privacy_gate.rb:
#   ruby scripts/test_privacy_audit_locale.rb      (exit 0 = pass)
#
# WHY THIS EXISTS (23 JUL 2026). privacy-audit-repo crashed outright when LANG
# and LC_ALL were unset:
#
#     shellwords.rb:150:in `gsub!': invalid byte sequence in US-ASCII
#
# Ruby derives Encoding.default_external from the locale. With no locale it is
# US-ASCII, so a denylist term containing a non-ASCII byte came back tagged
# US-ASCII-but-invalid, and the first thing done with it — Shellwords.shellescape,
# building a shell string for `git log -S<term>` — raised.
#
# The reason this deserves a permanent test rather than a note in a handoff:
# **an unset LANG is the NORMAL condition under cron, git hooks and CI.** Those
# are precisely the unattended runs where a PII gate is the only thing looking.
# A privacy audit that works interactively and dies in automation is worse than
# no audit, because the green interactive run is what people remember.
#
# It failed CLOSED (exit 1), which is the one mercy here — it did not silently
# report success. This test keeps it from regressing to failing at all.
#
# The fix being guarded is twofold, and the second half matters even without a
# shell: (1) run_git passes an argv ARRAY to IO.popen, so no shell and no
# Shellwords; (2) every read is pinned to UTF-8 and scrubbed, because matching a
# US-ASCII-tagged term against UTF-8 repo content raises
# Encoding::CompatibilityError just as fatally.
#
# NOTE ON PRIVACY: this test never reads, prints, or asserts on denylist CONTENT.
# It only counts non-ASCII terms to decide whether the case is even exercised.

require "open3"

ROOT = File.expand_path("..", __dir__)
SCRIPT = File.join(ROOT, "scripts", "privacy-audit-repo")
DENYLIST = File.join(ROOT, ".private/anonymization-denylist.txt")

failures = []

def check(desc, failures)
  ok, detail = yield
  puts(format("  %-58s %s", desc, ok ? "ok" : "FAIL"))
  failures << "#{desc}: #{detail}" unless ok
end

puts "test_privacy_audit_locale.rb"

unless File.exist?(SCRIPT)
  warn "SKIP: #{SCRIPT} not present"
  exit 0
end

unless File.exist?(DENYLIST)
  # A fresh clone has no private denylist. The script aborts early and there is
  # nothing to exercise; say so rather than passing silently.
  warn "SKIP: no denylist at .private/ — locale case not exercised on this checkout"
  exit 0
end

non_ascii = File.binread(DENYLIST)
              .split("\n")
              .reject { |l| l.strip.empty? || l.start_with?("#") }
              .count { |l| l.bytes.any? { |b| b > 127 } }

if non_ascii.zero?
  warn "SKIP: denylist has no non-ASCII term, so the crash path is unreachable here"
  exit 0
end
puts "  (#{non_ascii} non-ASCII denylist term(s) present — crash path is live)"

# The environments that used to break it. `env -u LANG -u LC_ALL` is the shape a
# cron job or a git hook actually runs in.
[
  ["no locale at all", { "LANG" => nil, "LC_ALL" => nil }],
  ["LC_ALL=C",         { "LANG" => "C", "LC_ALL" => "C" }],
  ["UTF-8 locale",     { "LANG" => "en_US.UTF-8", "LC_ALL" => "en_US.UTF-8" }]
].each do |label, env|
  stdout, stderr, status = Open3.capture3(env, SCRIPT)
  combined = "#{stdout}\n#{stderr}"

  check("#{label}: does not raise an encoding error", failures) do
    bad = combined.match?(/invalid byte sequence|Encoding::CompatibilityError|shellwords\.rb/)
    [!bad, combined.lines.first(3).join.strip]
  end

  check("#{label}: exits 0 (clean) or 1 (real finding), not a crash", failures) do
    # 0 = clean, 1 = findings. Anything else, or a Ruby backtrace, is a crash.
    crashed = combined.include?("(ArgumentError)") || combined.include?("backtrace")
    [[0, 1].include?(status.exitstatus) && !crashed, "exit=#{status.exitstatus}"]
  end
end

if failures.empty?
  puts "PASS"
  exit 0
end
puts "\nFAILURES:"
failures.each { |f| puts "  - #{f}" }
exit 1
