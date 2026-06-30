# Image Archive Deep Dive

Exhaust an online image-only archive (digitized church books, civil registers, parish records, scanned record collections) by browsing page images directly, reading the relevant entries, and saving a cropped evidence image for every record you cite.

This is the prompt for collections that are scanned but not transcribed or indexed. You cannot full-text search them. You have to open page images, narrow by date or image number, read handwriting, and crop the exact row. Pair it with [09 Local History Extraction](09-bygdebok-extraction.md) for printed books and [03 Find a Grave Sweep](03-findagrave-sweep.md) for indexed memorials.

> **Sharded trees (optional):** if your `Family_Tree.md` has grown and been split into shard files (listed in its File Index — see `vault-template/Family_Tree.md`), treat every reference to `Family_Tree.md` in this prompt as also covering those shard files: read them all, and route new people to the shard whose Region matches their line. Un-sharded vaults can ignore this note.

## Inputs To Replace

- `[VAULT_PATH]`: path to the genealogy vault folder
- `[ANCESTOR NAME]`: the target ancestor whose record you are hunting
- `[EVENT TYPE]`: the record event you expect (birth, baptism, marriage, burial, confirmation, census)
- `[EVENT YEAR]`: known or approximate year of the event
- `[PARISH OR LOCATION]`: parish, town, county, province, or country that holds the record
- `[ARCHIVE_URL]`: the online archive or collection viewer (for example a national archive, FamilySearch image group, or regional digitization portal)
- `[COLLECTION]`: the specific book, register, or collection name within the archive
- `[IMAGE_ID_RANGE]`: a starting image number or ID range if you already know roughly where to look, otherwise leave blank
- `[EVIDENCE_DIR]`: folder for saved record crops (for example `[VAULT_PATH]/Evidence/`)

## Autoresearch Configuration

**Goal**: For each deceased, source-suitable target event in `[VAULT_PATH]/Open_Questions.md` and `[VAULT_PATH]/Family_Tree.md`, locate the original record inside `[ARCHIVE_URL]` by browsing page images, read the entry, save a cropped evidence image of the exact row to `[EVIDENCE_DIR]`, and record a full image-level citation. Stop only when the relevant pages of `[COLLECTION]` are exhausted or the event is found.

**Metric**: Number of target events located in image-only archives with (a) a saved evidence crop, (b) a full image citation, and (c) an assigned evidence tier (`strong_signal`, `moderate_signal`, `speculative`, or rejected)

**Direction**: Maximize confirmed image-backed events. Do not maximize images opened or pages skimmed. An event read from the original register outranks an indexed hint every time.

**Verify**: In `[VAULT_PATH]/Research_Log.md`, count this iteration's events confirmed from original images, events still unresolved after exhausting the candidate page range, pages checked with no match, and events skipped because the person is living or privacy blocked. Confirm every confirmed event has a crop file in `[EVIDENCE_DIR]` and a citation that names the archive, collection, page or image ID, and entry number.

**Guard**:
- Do not fabricate a record. If you cannot read the entry, mark it `[unclear]` and keep the event unresolved. A confident transcription of an illegible scan is a failure.
- Do not infer an entry from a neighboring page. Cite the page you actually read.
- Do not crop loosely. The crop must contain the full entry, including the parent or witness line. If the first crop clips a line, redo it before saving.
- Do not accept an index entry as the record. An index or transcription is a finding aid; open the linked image and confirm.
- Do not download, crop, or save record images for living or possibly living people. Treat the starting person, their siblings, parents, and anyone without a death date as living unless the vault clearly states otherwise.
- Do not publish exact birth dates, addresses, or contact details for living or possibly living people.
- Do not modify confirmed dates or names in `Family_Tree.md`; route a conflict to `Open_Questions.md` and let [02 Cross-Reference Audit](02-cross-reference-audit.md) reconcile it.
- Respect each archive's terms of use and rate limits. Slow down rather than hammering a viewer.

**Iterations**: 8

**Protocol**:

1. **Baseline**: Read `[VAULT_PATH]/Open_Questions.md` and `[VAULT_PATH]/Family_Tree.md`. Build a hunt list of deceased target events: for each, note `[ANCESTOR NAME]`, `[EVENT TYPE]`, `[EVENT YEAR]`, `[PARISH OR LOCATION]`, and any known image range. Confirm `[EVIDENCE_DIR]` exists; create it if missing.

2. **Locate the collection**: For each target, identify the right `[COLLECTION]` inside `[ARCHIVE_URL]`. Match on parish, record type, and a year range that brackets `[EVENT YEAR]`. If you do not know the archive, consult the matching guide in `archives/` first and record the collection path in `Research_Log.md`.

3. **Triage with a contact sheet**: When a collection has many page images, build a contact sheet rather than opening pages one at a time. Use the thumbnail or grid view in the viewer, or generate a montage locally (see [Image Archive Navigation](../workflows/image-archive-navigation.md)). Read the visible year and section headers to narrow to the likely page range. Record the candidate `[IMAGE_ID_RANGE]`.

4. **Read at full size**: Open each candidate page at full resolution. Do not guess from thumbnails. Scan for `[ANCESTOR NAME]`, the patronymic or farm-name variant, and the `[EVENT YEAR]`. For Scandinavian, German, and other historic scripts, read the handwriting directly; preprocess for contrast if the scan is faint.

5. **Confirm the entry**: When you find a candidate entry, verify it matches on name, date, and place, and that any stated parents, spouse, or witnesses are consistent with the vault. Could another same-name person explain it? Assign an evidence tier.

6. **Crop the evidence**: Crop the exact entry row from the full-size image and save it to `[EVIDENCE_DIR]` with a descriptive name (for example `[parish]-[surname]-[event]-[year]-[imageid].jpg`). Include the full entry, including the parent or witness line. Inspect the crop. If it clips a line or is misaligned, redo the crop before continuing. Never save a crop you have not visually checked.

7. **Synthesize**: Create or update a transcription note from `[VAULT_PATH]/templates/transcription.md`. Fill the `source` and `evidence_crop` fields, transcribe the entry, mark unreadable text `[unclear]`, and extract facts with confidence levels. Add `strong_signal` or `moderate_signal` events to `Family_Tree.md` with the image citation; route weak or single-source events to `Open_Questions.md`.

8. **Log and exhaust**: In `Research_Log.md`, record the archive, collection, image range checked, queries and page numbers, the entry found or the negative result, and the crop path. If the event is unresolved, log the exact page range already checked so the next iteration does not repeat it. Move to the next target. Treat the collection as exhausted only when the bracketing year range has been read end to end.

## Tips

- **Image IDs are addresses**: Many archives expose a stable image ID or sequence number per page. Citing the image ID makes a record re-findable and lets you scan a range systematically instead of clicking blindly.
- **Read the spine dates**: Register pages usually carry the year and month in a header or margin. Use these to jump, not the thumbnail layout.
- **Negative ranges matter**: "Read images 80668640 through 80668660 of the [COLLECTION] burial register, no [ANCESTOR NAME] entry" is a durable result. Log it so you never re-read that range.
- **Crop, do not screenshot the whole page**: A tight, checked crop of the entry row is a reusable evidence image. A full-page screenshot buries the one line that matters and is easy to mismatch with the wrong entry later.
- **Patronymics and farm names**: The same person may appear under a patronymic, a farm name, or an Americanized name. Read every column, not just the given-name column.
- **When the script defeats you**: If you genuinely cannot read an entry, save the crop, mark the facts `[unclear]`, and route it to a human in the review step rather than inventing a reading.
