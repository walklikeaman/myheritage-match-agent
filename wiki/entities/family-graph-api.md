---
type: entity
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing]
confidence: high
status: active
relates_to: [myheritage, agent-architecture]
staleness_window: 180d
tags: [api, deferred]
---

# Entity: Family Graph API

**Status: deferred** — not needed for Phase 1-2. OAuth approval takes time.

## What it is
Public REST API at `familygraph.myheritage.com`. Authentication: OAuth 2.0 (application key + bearer token per user). All responses JSON. Register at `https://www.familygraph.com/getAccess`.

## What it CAN do
- Read user profile, trees, individuals, families
- Read photos and media
- Read citations and sources
- Access `MatchingRequest` objects — counts of pending/confirmed/rejected matches
- Export GEDCOM (requires special `ExportGEDCOM` scope approval)

## What it CANNOT do (critical)
- **No write API for confirming/rejecting matches**
- No endpoint to extract match data into the tree
- No API to save new person data from a match

## Usage (when we get to it)
```python
import os
BEARER_TOKEN = os.environ["MYHERITAGE_BEARER_TOKEN"]
headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
response = requests.get("https://familygraph.myheritage.com/me", headers=headers)
```

## Why deferred
The API is read-only for match operations. Playwright handles all writes. The API's main future value would be: reading current tree state before saving data, validating that a person exists before attempting to write, getting match counts without scraping the UI. None of these are blockers for Phase 1-3.

## Silent failure risk
Rate limits and expired tokens often return 200 with empty body or a re-auth redirect, not a clean error. Always assert on response shape, not just status code.
