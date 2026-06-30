# Source Citation Trace

Before launching repeated gap-fill scans of archive registers (Antenati, FamilySearch image collections, Geneteka, etc.) for a known person, run this trace first. A single check often saves days or weeks of scanning by leading directly to the source image in an adjacent document bundle (a marriage-paperwork file, a baptism register, etc.) that contains the answer in one drill.

The core idea: a community-tree profile frequently already links the exact register image you are about to spend hours hunting for. Contributors paste the direct archive link into the source citation. Check the citations before you scan.

## When to run this workflow

Always run before:
- Launching an archive gap-fill scan across multiple years for one person's death/birth/marriage record
- Launching a FamilySearch image-browse session across an unindexed collection
- Opening any new research question of the form "person X's [event] is unknown, search [archive] [date range]"

Skip this workflow when:
- Your research log already records that the source citation was checked for this person
- No community tree exists for the person (recent immigrant, brick-wall ancestor)
- The trace was completed in a prior session (check your logs first)

## The procedure

### Step 1. Open the target person's community-tree profile

Navigate to the person's FamilySearch profile at `https://www.familysearch.org/tree/person/details/[PID]`, where `[PID]` is the FamilySearch identifier.

If the person has no FamilySearch profile, check other community trees (Geni, Ancestry, WikiTree) using the same logic. The "link to the original record" pattern exists on most community-tree platforms.

### Step 2. Open the Sources tab and turn Detail View on

The Sources tab sits between Details and Collaborate in the top tab strip. Switch to it.

In Sources view, find the **Detail View** toggle on the left (next to "+ Add Source") and turn it on. This expands each source row to show all metadata fields, including the source URL. With Detail View off, the link-to-record field is not rendered, so you can miss a populated link entirely.

### Step 3. Check each source for a "link to the record" field

Expand each source row by clicking its title. In Detail View, each source shows:
- **Tags** (Name, Birth, Death, etc.)
- **Source Date** (when the original record was created)
- **Web Page (Link to the Record)** — the key field
- **Where the Record Is Found (Citation)** — the archive hierarchy
- **Notes** — contributor notes about what the image contains

The "link to the record" field, when populated, holds a direct URL to the source image. For records held by national digital archives this is typically a stable persistent identifier (for example, an Antenati ARK such as `https://antenati.cultura.gov.it/ark:/12657/.../...`).

### Step 4. If a URL exists, follow it and drill the adjacent pages

The source URL usually lands on one page inside a larger document bundle. In many civil-register systems, the most valuable bundle is the **marriage-paperwork file** (in the Italian system, the *processetti* or *allegati*) — a packet of certified extracts gathered to authorize one marriage. It can contain:
- Both spouses' birth extracts
- Death extracts for any deceased parents of the couple
- Parental-consent documents (for living fathers, where required by the era)
- The marriage banns
- The marriage act itself

These documents are grouped sequentially per couple. One such packet typically spans 5-15 pages.

**Action**: use the archive's page viewer to move backward and forward from the linked page. Read each adjacent page until you exit the current packet (a new heading for the next couple signals the boundary). Transcribe the relevant details from each page in the packet — the answer to your question is often a few pages away from the linked one.

### Step 5. Cross-reference findings against the open question

Compare the new primary-source data against the hypothesis behind your planned gap-fill scan. Register paperwork frequently states a parent's living-or-deceased status directly (for example, Italian acts prefix a deceased person's name with "fu"). That single detail often resolves an alive/deceased question with no scanning at all.

If the question is resolved, record it as resolved, write a log entry, and pivot the next search to whatever the new primary source points toward.

### Step 6. If no URL exists, the trace concludes

If no source has a populated link-to-record field, the trace is complete. Log "source-citation trace attempted, no linked image found," then proceed with the gap-fill scan as originally planned. The negative result is worth recording so a later session does not repeat the check.

## Worked example (anonymized)

A typical resolution follows this exact procedure:

1. **Target**: the death record of a male ancestor born about 1770. Working hypothesis: he died in his home comune sometime in a ~35-year window.
2. **Prior work**: roughly 1,200 negative register entries scanned across several sessions, with zero hits on the target — a classic sign the hypothesis or the date window is wrong.
3. **Trigger**: a record turned up on the ancestor's *wife's* profile, prompting a citation check rather than yet another scan.
4. **Trace**: wife's profile → Sources tab → Detail View on → expand the relevant source row.
5. **Link to the record**: an archive ARK pointing to a specific page of a marriage-paperwork file from a year well *after* the assumed death window.
6. **Notes field**: confirmed the page was a death extract included inside that later marriage packet.
7. **Drill the adjacent pages**: the surrounding pages held the bride's birth extract, the linked death extract, the marriage notice, and the marriage act — and the act named the target ancestor as *present in person* to give consent, with no "deceased" prefix on his name.
8. **Resolved**: the ancestor was demonstrably alive years past the window that had been scanned. The death search pivoted to the later period.

The trace took about ten minutes from opening the profile to reading the decisive act. The earlier scans on the wrong window had consumed tens of hours.

## Anti-pattern

If you find yourself launching a **second** session of gap-fill scans for a person whose event date is still unknown, stop and run this trace. The cost of the trace is bounded (5-15 minutes); the cost of continuing a wrong-hypothesis scan is unbounded.

## Handling downloaded register images

Register pages from these archives are typically 3000-4500 px wide. A multimodal model downsizes large images internally before reasoning over them, but the full-resolution file is still transmitted on every read, so repeatedly reading one large page wastes bandwidth and can fail outright on request-size limits. Downsize once before reading:

```bash
sips -Z 1500 input.jpg --out /tmp/page-small.jpg          # macOS built-in
# or, cross-platform with ImageMagick:
magick input.jpg -resize 1500x page-small.jpg
```

To read one specific entry at full cursive detail without paying for the whole page, crop just that region instead of downsizing the page:

```bash
magick input.jpg -crop WxH+X+Y /tmp/entry.png             # +X+Y offset from top-left
# optionally aid 19th-century cursive:
magick input.jpg -crop WxH+X+Y -resize 180% -normalize -sharpen 0x1 /tmp/entry.png
```

Then read the small crop — full detail for the region of interest at a fraction of the payload. If you genuinely need full resolution across a whole page (for interactive locating), serve the file over a local HTTP server and zoom in a browser rather than reading the full-resolution file directly, which keeps the large image out of the model's context entirely.

After the session, triage the downloaded images: move pages that became part of a vault entry into your images directory, and delete exploratory-only pages.

## See also

- `reference/common-pitfalls.md` — Search Strategy Pitfalls
- `workflows/discrepancy-resolution.md` — for conflicts between a citation-linked source and gap-fill findings
- `workflows/image-archive-navigation.md` — driving archive image viewers
