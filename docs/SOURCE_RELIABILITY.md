# Outpace Source Reliability

Competitive sources are heterogeneous. A new provider or access
constraint is expected operational work, not an exceptional product
failure. Outpace therefore separates source collection health from
competitive change detection.

## Provider selection order

Use the first permitted source that supplies stable identifiers:

1. Official public API or ATS adapter.
2. Official RSS/Atom or structured feed.
3. Official server-rendered HTML.
4. Controlled browser rendering when permitted and reliable.
5. Mark the source unsupported or blocked.

Outpace does not bypass CAPTCHAs, Cloudflare challenges, authentication,
or provider entitlements.

## Failure rules

- A failed collection never becomes an empty snapshot.
- The last successful snapshot remains the current evidence baseline.
- `blocked` means access controls prevented collection.
- `unsupported` means no implemented or permitted provider is available.
- `degraded` means a normally supported source failed temporarily or its
  structure could not be validated.
- `failed` is an unexpected collector error requiring investigation.
- A successful stored snapshot resets the consecutive-failure count.

## Adapter contract

Every adapter must:

- use a provider-stable item ID;
- return normalized structured fields;
- distinguish a verified zero-result state from parsing failure;
- label fixtures with `test_fixture: true`;
- avoid secrets in source metadata and health messages;
- produce stable output across two immediate live collections;
- reject access challenges before snapshot insertion.

## Adding a provider

1. Confirm the source is public and permitted.
2. Identify its stable API, feed, or page contract.
3. Add the provider to the source constraint and collector dispatch.
4. Normalize a recorded fixture and test zero, populated, and malformed
   responses.
5. Run two live collections and confirm a zero-change diff.
6. Record the provider and verification result in `PROGRESS.md` and the
   provider matrix.

## Onboarding discovery roadmap

Onboarding should probe provider capabilities in this order:

- known ATS URLs and public APIs (Ashby, Greenhouse, Lever);
- RSS/Atom discovery links;
- server-rendered structured HTML;
- supported browser-rendered pages;
- explicit `blocked` or `unsupported` result with remediation guidance.

Users should choose what to monitor. They should not need to understand
the underlying adapter name.
