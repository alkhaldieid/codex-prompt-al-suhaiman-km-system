# MoJ Legislation Portal — API discovery

Discovery run: 2026-05-25, via `scripts/discover_moj_api.py` (Playwright
+ headless Chromium). Raw captures live in
`tests/fixtures/moj_api_samples/captures.json` (66 XHRs across 4 phases).

## TL;DR for the connector design

- **PDFs are not the right ingest target.** The portal's
  `/document/download` endpoint exists but returns 400 to every public
  caller — including in-browser Playwright fetches with the SPA's
  full cookie set. The SPA itself never calls it; "تصدير إلى PDF" is a
  client-side jsPDF render of the page, not a server fetch. There is
  no public way to download the source PDF.
- **The detail JSON already contains the full statute text** —
  cleanly chunked by section / chapter / article in
  `statuteStructure[].items[].text` as small HTML fragments, with no
  website chrome. Per-statute we see ≈30 KB of Arabic content split
  across ≈230 article-level text fields. **This is the source of
  truth we should ingest.**
- Authentication is not required for listing or detail. Set-Cookie
  headers are session-tracking (Akamai TS, Dynatrace dt/rx, MOJe
  load-balancer affinity) but not load-bearing for content access.
- Connector plan therefore: list → detail → ingest the inlined
  statute text. Bypass PDF entirely. No OCR needed for MoJ content.

## Authentication posture

| Concern | Verdict |
|---|---|
| OAuth or API key required for listing? | No. Open POST with `Content-Type: application/json`. |
| OAuth or API key required for detail? | No. Open GET with `Serial` query param. |
| 401/403 on any open endpoint? | None observed. |
| Set-Cookie headers? | Yes (`dtCookie`, `MOJe`, `TS01ae1234`, `rxVisitor`, `i18n_redirected`) — load-balancer affinity + analytics. Not load-bearing. |
| Rate limiting? | Not observed in discovery; treat as polite (2 s spacing) until we have signal. |

`/document/download` returns 400 even with all cookies. The error body
is RFC 7807 `{"errors": {"Document": ["The input was not valid."]}}`.
This is a server-side parameter rejection, not an auth failure — and
the SPA never exercises this code path in the public UI, so we have no
worked example to copy. Treat the download endpoint as effectively
unavailable.

## Discovered endpoints

### 1. Listing — `POST /apis/legislations/v1/statute/section-search`

```bash
curl -sS -X POST 'https://laws-gateway.moj.gov.sa/apis/legislations/v1/statute/section-search' \
  -H 'Accept: application/json' \
  -H 'Accept-Language: ar' \
  -H 'Content-Type: application/json' \
  -H 'Referer: https://laws.moj.gov.sa/' \
  -d '{
    "pageNumber": 1,
    "pageSize": 9,
    "sortingBy": 7,
    "detailsKeyword": "",
    "LegalStatue": null,
    "classificationId": null,
    "statuteIssueDateFrom": null,
    "statuteIssueDateTo": null,
    "statuteName": "",
    "statutePublishDateFrom": null,
    "statutePublishDateTo": null,
    "statuteType": null,
    "keyword": "",
    "isSearch": false,
    "identityNumber": ""
  }'
```

Response (excerpt):

```json
{
  "statusCode": 200,
  "success": true,
  "model": {
    "collection": [
      {
        "statuteId": "mpVEWcnvQGJerTgRQqnnsw",
        "serial": "g28zaD-gXzN_8DAm9qbydw",
        "statuteName": "نظام التوثيق",
        "legalType": "نظام",
        "issuanceDate": null,
        "issuanceDateGerogian": null,
        "legalStatus": 0
      },
      ...9 items per page
    ],
    "totalCount": <int>
  }
}
```

Sort options: `sortingBy=7` is newest-first by publish date (confirmed
by SPA behaviour). Other values (1–6) need probing if we want a
different sort.

### 2. Detail — `GET /apis/legislations/v1/statute/get-Statute-gateway-Detail`

```bash
curl -sS \
  -H 'Accept: application/json' \
  -H 'Accept-Language: ar' \
  -H 'Referer: https://laws.moj.gov.sa/' \
  'https://laws-gateway.moj.gov.sa/apis/legislations/v1/statute/get-Statute-gateway-Detail?Serial=UbB0wpvasVhoTAgmYKUA7A&identityNumber='
```

The `identityNumber=` is intentionally empty (the SPA also passes it
empty for anonymous users).

Response top-level model keys (selected):

| Field | Type | Purpose |
|---|---|---|
| `id`, `statuteId`, `statuteVersionId` | string | The three internal IDs — see Change detection. |
| `serial` | string | The slug used in the URL `/ar/legislation/<serial>`. |
| `name` | string | Title in Arabic, e.g. `نظام الإثبات`. |
| `legalType`, `legalTypeName` | string | e.g. `نظام`, `لائحة`. |
| `classificationId`, `classificationName` | int/string | Practice-area-ish, e.g. `1` / `القضاء`. |
| `issuanceDate`, `gregorianValidFromDate` | ISO | Royal decree date (Hijri + Gregorian). |
| `publishDate`, `publishDateGerogian` | ISO | Umm Al-Qura publish date. |
| `legalStatueId`, `legalStatueName` | int/string | `1` / `ساري` (in force), `2` / `ملغي` (repealed). |
| `statuteStructure[]` | array | The full statute body, recursively chunked. |
| `pdfCopy.downloadUrl` | string | A 400-only endpoint (see TL;DR). |
| `bureauOfExpertsAtTheCouncilOfMinistersUrl` | string | Cross-link back to BOE. |

### 3. Statute body — inline in detail response

Each detail response contains `statuteStructure`, a list of `Section`s
(باب / فصل / فرع). Each Section has `items`, recursively. The leaves
carry `text` (HTML fragments with `<p>`, `<ol>`, `<li>` only — no
chrome). The text comes pre-numbered by article: each item's `name`
(or its parent's `name`) carries the article label, and each item has
its own `id` for stable referencing.

Example leaf (from `نظام الإثبات`):

```json
{
  "id": "g69gQZRAXYqRbyAFxSCE-g",
  "name": "المادة الأولى",
  "text": "<p>تسري أحكام هذا النظام على المعاملات المدنية والتجارية.</p>",
  "isCancelled": false,
  "isPublished": true,
  "legalStatusName": "ساري"
}
```

So the connector flow is:
1. List page 1 newest-first.
2. For each `serial`, GET detail.
3. Walk `statuteStructure` recursively. Concatenate `text` leaves in
   tree order. Use the parent `name` chain to label each chunk.
4. Persist as one `Document` per statute, with article-aware chunks
   from the existing `text_processing.chunk_text` (each statuteStructure
   item naturally already respects the spec §6.1 article boundaries).

### 4. Lookup tables — `GET /apis/legislations/v1/gatewaylookups/get`

```bash
curl -sS \
  -H 'Accept: application/json' \
  'https://laws-gateway.moj.gov.sa/apis/legislations/v1/gatewaylookups/get?catalog=4'
```

Returns enum-style metadata: legal types, statuses, etc. Useful for
mapping `legalType` strings to our internal `doc_type` enum, but we
can hardcode the small known set instead.

## Change detection strategy

The detail response does not expose a free-standing `updated_at`
field. The candidates we have:

| Field | Stability | Use |
|---|---|---|
| `statuteVersionId` | Changes when the statute body is amended. | Primary signal — store on `documents.source_external_id` companion column or in `source_external_etag` style. |
| `publishDate` / `publishDateGerogian` | Gazette date. Changes on amendment via a new gazette. | Secondary signal for human display. |
| `legalStatueId` | Goes `1 → 2` if the law is repealed. | Watch for status flips even when version is stable. |

Proposed: connector keeps `(serial, statuteVersionId, legalStatueId)`
as the change-detection tuple. If any changes, re-ingest.

## Things the connector should NOT do

- Do not call `/document/download` — the public flow has no path to a
  valid token / encoding and the SPA itself never uses it.
- Do not depend on `pdfCopy`, `hardCopy`, or `wordCopy` fields. They
  appear to be admin-only.
- Do not try to parse the SPA's HTML pages. The Nuxt shell is empty
  until JS runs, and we have the JSON API.

## Open questions surfaced

1. **Total corpus size.** Listing shows 9 per page; we don't yet
   know the total page count. Page-2 returned `نظام الإثبات` as item 1,
   meaning the full set is at least ~18 statutes. Spec §1.2 only needs
   a few; the connector should accept a `max_pages` argument.
2. **Whether `classificationId` aligns with our `practice_area` enum.**
   The lookup `catalog=4` returns Arabic names; needs mapping table.
3. **Rate limiting.** We didn't probe — recommend 2 s spacing and 3 s
   backoff on any 429, polite-fetcher-style.

## Sanity-check checklist before building the connector

Confirm before Step 2:

- [x] Listing endpoint signature is correct.
- [x] Detail endpoint signature is correct.
- [x] Statute text is available in the JSON, full, clean.
- [x] No auth required.
- [x] PDF endpoint is dead-on-arrival — abandoned.
- [ ] **You sign off on ingesting the inlined HTML instead of PDFs.**
      This is the load-bearing reversal vs the previous prompt.
