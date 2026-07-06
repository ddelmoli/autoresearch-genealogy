# Common Genealogy Pitfalls

Mistakes that both humans and AI frequently make in genealogy research.

## Source Reliability Pitfalls

### The Ancestry Hint Trap
Ancestry.com's "hints" are algorithmic matches, not verified connections. They match based on name similarity and approximate dates. A hint does not mean the record is for your ancestor. Always view the original record and verify name, dates, AND location.

### The Geni Merge Problem
Geni.com's collaborative model allows anyone to edit any profile. Profiles are frequently merged incorrectly, combining two different people into one. If Geni data conflicts with a primary source, the primary source wins.

### The Transcription Cascade
One volunteer misreads a headstone date. It gets transcribed into Find a Grave. Someone copies it into their Ancestry tree. Dozens of other trees copy that tree. Now the wrong date appears in 50 sources, creating a false impression of consensus. Always trace data back to its original source.

### The "Multiple Sources" Illusion
Two Ancestry trees that copied the same data are ONE source, not two. Three websites that all cite the same published genealogy are ONE source. Independent means the sources were created separately from different original evidence.

## Name Pitfalls

### Patronymic Confusion
In Scandinavian genealogy, "Hansen" is not necessarily a fixed family name; historically it can mean "son of Hans." The same family may appear under a patronymic, an Americanized spelling, or a completely different farm name in different records. Do not assume all Hansens in a region are related.

### The "Same Name, Same Dates" Fallacy
Two people named John Smith born around 1850 in the same county are not necessarily the same person. Common names produce frequent false matches. Require corroborating evidence (spouse's name, children's names, occupation, specific address) before merging.

### Americanization Patterns
Immigrants commonly changed their names. Patterns include:
- Translation (Johannes → John, Wilhelm → William)
- Simplification (Nordlie → Nordli → Nordlien)
- Complete change (Nowak → Lis, when a hereditary nickname replaced the legal surname)
- Phonetic spelling by the immigration official
Do not assume the American name resembles the original name.

### Maiden Name vs Married Name vs Widowed Name
Women may appear under different names in different records: maiden name (birth certificate), married name (census), second married name (later records), or "widow of [husband]" (probate). Track all variants.

## Date Pitfalls

### Census Age Rounding
People frequently gave rounded ages on census forms. An age of "40" in the 1900 census does not mean birth year 1860. It could be anywhere from 1855 to 1865. Use census ages as approximations, not facts.

### Delayed Registration
A birth certificate filed 50 years after the birth contains the informant's memories, not firsthand knowledge. Delayed certificates are common for pre-1900 births and may have errors in dates, parents' names, or birthplace.

### Old Style vs New Style Dates
Before 1752 (in British colonies), the year started on March 25, not January 1. A date recorded as "February 10, 1731" Old Style is "February 10, 1732" New Style. Some records use dual dating: "February 10, 1731/32."

### Tombstone Date Errors
Headstones are often erected years after death, based on family memory. They may contain errors, especially for older family members whose birth dates were not well documented.

## DNA Pitfalls

### Over-Trusting Percentages
The difference between 47% and 52% Scandinavian is meaningless. Consumer DNA percentages are estimates with margins of error. Treat them as approximate ranges.

### Trace Ancestry Hunting
Do not build research theories on trace ancestry (<2%). These percentages are within the noise floor and change between algorithm updates. They likely reflect ancient admixture or statistical noise, not a specific ancestor.

### Ethnicity ≠ Identity
DNA reflects genetic populations, not nationalities, religions, or ethnicities. "Ashkenazi Jewish" is a genetic signature, not a religious determination. "Eastern European" includes dozens of distinct nations and cultures.

### The "Missing Ancestor" Problem
DNA inheritance is random. You do not inherit DNA from every ancestor. Beyond 6 to 7 generations back, some ancestors contribute zero DNA to you. A missing genetic signal does not mean the ancestor is not real.

## Organizational Pitfalls

### Not Logging Negative Results
"I searched and found nothing" is valuable data. Without logging negative results, you (or your AI) will repeat the same fruitless searches. Always log: what you searched, where, when, and that you found nothing.

### Single-Source Persons
Every person in your tree should have at least two independent sources. A person supported by only a single user-contributed family tree is barely better than speculation. Flag single-source persons and prioritize finding corroboration.

### Ignoring Discrepancies
When two sources disagree, do not quietly pick one. Document both, note which is more reliable and why, and mark the discrepancy for future resolution. Silent choices become invisible errors.

## Search Strategy Pitfalls

### Skipping the FS Source Citation Check Before Gap-Fill Scans
When a person's death date (or other event) is unknown, the instinct is to launch register scans across a plausible date window: 1816, 1817, 1818, ... year by year. This can burn days or weeks of scanning if the underlying hypothesis is wrong.

Before launching any gap-fill scan of a known archive (Antenati ARKs, FamilySearch image collections), open the target person's FamilySearch profile (or other community-tree profile), open the Sources tab, toggle Detail View on, and check each attached source for a "Web Page (Link to the Record)" field. Community contributors often paste the direct archive URL to the source image. That image is often part of an adjacent fascicolo (e.g., an Italian matrimoni processetti bundle containing certified extracts of birth, death, and consent records for both spouses and their parents) — drilling 5-10 adjacent pages may surface documents that resolve the question in one pass.

This single check takes minutes; skipping it can cost weeks of scans on the wrong hypothesis. Worked example: one Italian ancestor (b. ~1770) accumulated roughly 1,200 negative *atti* scans across an 1816-1850 death-register window before a single FS source-citation trace on his wife's profile led straight to an 1852 *matrimoni processetti* page proving him still alive at age 82 — the death-window hypothesis had been off by decades.

The pattern generalizes to any record system where contributors attach source images to person profiles: Antenati (via FamilySearch), Geneteka (Polish), ScotlandsPeople (Scottish), etc. See [workflows/source-citation-trace.md](../workflows/source-citation-trace.md) for the step-by-step trace procedure.
