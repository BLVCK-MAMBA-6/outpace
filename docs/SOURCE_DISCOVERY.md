# Careers Source Discovery

Outpace turns one official careers URL into a confirmed monitoring source. The user does not need to know which applicant-tracking system a competitor uses.

## Discovery order

1. Recognize a directly supplied Deel, Ashby, Greenhouse, Lever, or GitHub URL.
2. Fetch the public careers page and inspect it for embedded hosted-board references.
3. Probe a small set of company/domain identifiers against supported official public APIs.
4. Offer the existing public HTML provider only when the page loaded and no structured provider was verified.

Every result is a suggestion. The API returns `requires_confirmation: true`, and onboarding does not store the source until the user continues.

Indirect structured discovery requires at least one published role. A directly supplied hosted-board URL may still verify with zero roles because the user explicitly selected that board. This prevents stale embeds or unrelated company-slug matches from replacing a visibly active careers listing.

## Supported structured providers

| Provider | Public endpoint | Stored identifier |
| --- | --- | --- |
| Deel-hosted | `jobs.deel.com/{tenant}` JSON-LD | Tenant |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{board}` | Board name |
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs` | Board token |
| Lever | `api.lever.co/v0/postings/{site}` | Site name + region |
| Lever EU | `api.eu.lever.co/v0/postings/{site}` | Site name + `eu` region |
| GitHub | Public repository URL | `owner/repository` |

## Safety properties

- Only HTTP and HTTPS careers URLs are accepted.
- Localhost, private, link-local, and other non-public destinations are rejected before fetching.
- Redirects are followed manually and each destination is revalidated.
- HTML reads are bounded to 3 MB.
- Provider identifiers are restricted before storage.
- Query-based job-detail URLs are preserved without adding a corrupt trailing slash.
- HTML fallback infers a repeated job-detail path such as `/careers/job` before using the broader careers-page path.
- Discovery failures do not create a source or an empty snapshot.
- Zero-role embedded references and guessed provider slugs are not accepted as source proof.
- Deel boards are verified through their embedded `ItemList` JSON-LD, then
  job-detail pages are read at low concurrency for `JobPosting` JSON-LD.
- Incomplete Deel detail crawls are rejected instead of storing a partial
  snapshot that could create false job-removal alerts.
- Access controls, CAPTCHAs, Cloudflare challenges, and provider entitlements are never bypassed.

## Confidence

- `high`: direct hosted-board URL or embedded provider reference verified against its public endpoint.
- `medium`: conservative company/domain slug verified against a public provider endpoint.
- `low`: public HTML fallback after structured probes fail.

Confidence is explanatory, not authorization. All three levels require confirmation.

## Tests

Run:

```bash
python -m unittest -v \
  tests.test_job_source_discovery \
  tests.test_job_provider_parsers
```

The parser tests cover stable Deel UUIDs and JobPosting normalization.
They also deliberately treat a valid zero-job Greenhouse board as successful
live data. An invalid response shape is still rejected.
