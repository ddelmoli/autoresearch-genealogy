# Research Techniques and Tool Pipelines

The **HOW** layer: how to drive the archive viewers, read register images economically, work the major genealogy platforms, and divide labor with account-gated resources. Companion material:
- `archives/` — the **WHAT/WHERE** (site URLs and finding aids by country).
- `reference/common-pitfalls.md` and `reference/what-ai-can-and-cannot-do.md` — failure modes and scope.
- `workflows/` — step-by-step procedures (source-citation-trace, onomastic-origins, ocr-pipeline, image-archive-navigation, etc.).

These techniques are platform mechanics that change over time — verify endpoints and viewer behavior against the live site before relying on them.

---

## Local tooling

Two command-line tools cover almost all image and OCR preprocessing. Install whichever your platform provides:

- **ImageMagick** — crop and resize register pages. Extract one record at full resolution instead of downsizing the whole page: `magick page.jpg -crop WxH+X+Y record.png` (the `+X+Y` offset is measured from the top-left). For faded 19th-century cursive, `-resize 180% -normalize -sharpen 0x1` helps. Note that Python's Pillow is a separate dependency; ImageMagick on the PATH is the more portable choice.
- **Tesseract** — OCR for **printed** text and typed metadata, with language packs (Italian, Latin, Polish, Russian, Ukrainian, German/Fraktur, etc.). It is **weak on 19th-century cursive** and fails outright on early-modern secretary hand — for handwriting, use a multimodal model's own vision (read the cropped image directly) rather than Tesseract.

## Reading register images — the universal rule

**Download the image first; do not fight the in-browser viewer.** FamilySearch DeepZoom, Antenati IIIF, and the Polish metryki canvas viewer all have unreliable zoom, can freeze under repeated zooming, and a screenshot captures only the low-resolution rendered viewport, not the underlying high-resolution image. Fighting a viewer is one of the most common multi-hour time sinks in this work.

Once downloaded, **downsize or crop before reading.** A multimodal model downsizes large images internally before reasoning over them, but the full-resolution file is still transmitted on every read, so repeatedly reading one large page wastes bandwidth and can fail on request-size limits. Downsize a whole page with `sips -Z 1500 page.jpg --out small.jpg` (macOS) or `magick page.jpg -resize 1500x small.jpg`, or crop a single record with `magick -crop`. See `workflows/source-citation-trace.md` for the full image-handling note.

---

## Image-download pipelines (three viewers, three mechanisms)

The three big register hosts each expose images differently. The mechanism matters because what works for one is blocked on another.

### Antenati (Italian civil records) — IIIF, scriptable

Antenati honors cross-origin requests, so its images can be fetched and saved programmatically.

1. **Find the register.** Each register is one year and one record type (Nati / Morti / Matrimoni / **Matrimoni processetti** / pubblicazioni). Reach it through *Esplora gli Archivi* → archive → comune, or from a known record's breadcrumb.
2. **Register identifiers run contiguously by year** within a type, so once you map one year you can extrapolate adjacent years. Pull the container hash from the page HTML (it appears in a `containers/{hash}` path).
3. **Get the page list** from the IIIF manifest: `fetch('https://dam-antenati.cultura.gov.it/antenati/containers/{containerHash}/manifest', {credentials:'include'})`, then read `sequences[0].canvases` (labeled "pag. N"); each canvas exposes its image service id.
4. **Download** by building an `Image` with `crossOrigin='anonymous'` from the IIIF endpoint (request a bounded width such as `/full/1723,/0/default.jpg` — `full/full` may return 503), draw it to a canvas, and save the blob via an anchor click.
5. **Browsers block the second and later automated download per page-load.** The person at the keyboard either accepts the prompt or allow-lists the domain under the browser's automatic-downloads setting; then a script loop can pull many pages.
6. **Validate each file** (`file --mime-type`) — a failed IIIF fetch silently saves a few-KB HTML error body with a `.jpg` extension. Read the annual *Tavola alfabetica* index page first when one exists.

**Marriage-paperwork bundles (processetti) are unusually high-value:** they carry birth extracts for the spouses' parents and death extracts for any deceased parents, reaching a generation deeper than a single marriage act — but only when the relevant ascendants had already died by the marriage date.

### FamilySearch films — DeepZoom, manual download

FamilySearch serves film images as DeepZoom tiles, and **cross-origin fetch/canvas-stitching fails** (the request is blocked, and a `crossOrigin` image taints the canvas) — do not reuse the Antenati approach here.

- **Working method:** navigate the viewer to the target image (`/search/film/{filmNumber}?i={imageIndex}`), have the person at the keyboard click the **Download** button in the viewer toolbar to save the image, then move, crop, and read it. Some collections are image-restricted and offer no Download button.
- **Locating a year with no name index:** extrapolate from a mapped waypoint (e.g. "1832 marriages start around image 584, roughly 8 images per year") and walk chronologically. Registers before the late 1790s usually lack an annual index. The grid view is a virtualized list that resists programmatic scrolling — step through single images by index instead.

### metryki.genealodzy.pl (Polish parish/civil registers) — canvas viewer

- **Scan availability is per-collection, not per-parish** — a record type being absent for one parish-year says nothing about another type or era at the same parish. Check which holding institution and fonds a given parish-year belongs to (state archive vs. diocesan archive); only some are digitized here.
- The viewer renders to a `<canvas>` rather than an `<img>`, so there is no direct image URL to fetch — use the viewer's own save icon, or zoom the rendered canvas. Page-file numbering does not reliably equal the record number; verify per collection.

---

## FamilySearch techniques

- **Full-Text Search:** use unquoted multi-keyword queries spanning all name variants plus status terms (for Italian: `fu`, `morto`, `vedova`, `figlia di`, occupations); strict-quoted phrases often error or miss matches. It works well to **drill a known, located record**, but is poor for a **blind surname sweep** of a single locality — relevance ranking favors generic place and date terms, cursive OCR mangles surnames, and the collection filter is only country/state granular.
- **Source-citation trace:** before any gap-fill scan, open the person's Sources tab, turn **Detail View on**, and check each source's "Web Page (Link to the Record)" for a direct image link; repeat on the spouse, parents, and children. One trace can resolve a wall that an entire scan cannot. Full procedure in `workflows/source-citation-trace.md`.
- **Source harvesting — independent primary records only.** When recording what a profile cites, include indexed-record and register-image links plus links to external archives (Antenati, the Polish state-archive viewers); **exclude** published book/journal citations (cite those in prose with page numbers, do not turn them into record links) and other user trees (they copy each other and are not independent evidence). Detail View must be on, or the links are not rendered and you get a false "no sources" read.
- **Family walk:** the internal tree-data JSON endpoints change and break, and family links are rendered client-side rather than sitting in the initial HTML. Read the rendered page text after it loads (poll until at least two related profile IDs are present — the page skeleton renders before the data). Check any newly adopted profile for having been deleted-by-merge or left as an orphan stub before relying on it.
- **Parent-name search to find siblings:** some FamilySearch collections (for example, Scotland Births and Baptisms) support searching by **parent** name where the official national index does not. When a person's own baptism is unindexed, searching for their siblings by the parents' names can pin the parish.
- **Fixing a conflated parent (re-parenting):** detach each wrong parent (the platform requires a reason); create a **clean couple with the dates left blank** so the system does not auto-merge it back; do **not** click "Add Parent" twice (that creates two uncoupled singles) — instead add the spouse by ID and the child by ID; add a do-not-merge alert note; then update your own records to point at the corrected profiles.

---

## Account-gated and paid resources — dividing the labor

Several of the most valuable sources require an account, paid credits, or institutional access. An AI assistant **cannot authenticate, pay, or create accounts** — treat those as steps for the person at the keyboard, and **flag every credit or fee spend for explicit approval** before incurring it. Within that boundary, the assistant can drive the searches and read the results. Never store credentials in the repository or in notes.

The division of labor below applies to each resource: **the human logs in, buys credits, and performs trusted clicks; the assistant drives searches and reads pages in the already-authenticated browser.**

- **Internet Archive (borrow in-copyright books).** The account holder clicks **Borrow**; the assistant can then read without downloading the whole book by using the search-inside endpoint (`.../fulltext/inside.php?...&q={query}` with credentials) to get match locations — note these are internal *leaf* indices, not printed page numbers — then jumping the BookReader to each leaf. Public-domain texts can be pulled in full as plain text (`archive.org/download/{id}/{id}_djvu.txt`). This is mainly an Anglo-American lever (New England town vital records, compiled family genealogies, lineage-society volumes); it does little for immigrant lines whose evidence is archival registers rather than published books.
- **Academic/library SSO (e.g. via a public or university library's OpenAthens).** Can unlock scholarly reference sets — national biography dictionaries, county-history and state-papers collections, early-printed-book databases — that are strong for titled, notable, and medieval context. These typically do **not** include a parish-register or commercial-tree subscription, so they cannot close a wall that needs an actual baptism or burial entry. Check exactly which databases a given institution's access includes before relying on it.
- **National civil-registration portals (pay-per-record).** Some jurisdictions sell index views and register images by credit (for example, the General Register Office of Northern Ireland for the six counties the all-island service excludes). Typical pattern: a basic index view is free or cheap, the full record and register image cost more; online viewing is gated by record age (births, marriages, then deaths become viewable at increasing year thresholds). The full transcription often omits the most valuable fields (address/townland, informant, cause of death) which live only on the image — and some portals prohibit screenshotting the image, in which case the account holder must read it off-screen and relay it. Registrars spelled names phonetically, so search by child name and registration district rather than by a mother's maiden surname, and map a family's full movements before concluding a same-name record is "the wrong one."
- **Lineage-society ancestor databases (e.g. the DAR Genealogical Research System).** Often **free to search without login** even when record copies cost money. The full entry usually adds the spouse — the decisive disambiguator for a common name — and shows which children have approved lines of descent. Cite the ancestor name and number; do not bulk-redistribute proprietary society data.
- **National archives wills and probate (e.g. UK PCC wills, series PROB 11).** Searching the catalogue is usually free via a public API; a digitised document may show a fee when logged out but be **free to download once signed into a free registered account** (add to basket, check out at zero cost). Read a secretary-hand will by rasterizing the PDF at higher density and cropping bands — OCR cannot read the hand, so a multimodal model's vision must. Interpretively, **a child absent from an otherwise even-handed will likely predeceased the testator** — a useful negative signal when testing a disputed descent.

---

*Platform mechanics drift. Endpoints, viewer internals, fee thresholds, and which collections are restricted all change — re-verify against the live site before depending on any specific URL or behavior described here.*
