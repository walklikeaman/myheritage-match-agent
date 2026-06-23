# MyHeritage Automation Agent — Project Briefing

> **Prepared for:** Claude Code  
> **Context:** This document captures a full conversation between Nikita and Claude Chat about automating genealogy work on MyHeritage. Read everything before writing a single line of code.

---

## 🧬 What This Agent Actually Needs to Do

Nikita has a MyHeritage family tree with **~10,000 people**. MyHeritage continuously generates:
- **Smart Matches** — connections to other users' trees that share the same person
- **Record Matches** — matches to historical documents (census records, birth/death certificates, newspapers, immigration records, etc.)
- **Discoveries** — broader category that includes both of the above plus Instant Discoveries

The volume is unmanageable manually. The agent must:

1. **Iterate through all pending matches** (Smart Matches + Record Matches)
2. **Evaluate confidence** — accept if ≥ 80%, skip if below
3. **Confirm the match** on accepted ones
4. **Extract enrichment data** — not just click "accept", but pull out new info: additional relatives, photos, dates, places, sources
5. **Save new data to the tree** selectively (not blindly dump everything)
6. **Log everything** — what was accepted, rejected, what new data was extracted, for which person

This is a **data enrichment agent**, not just a click-bot.

---

## 🔑 The API Situation (Read This Carefully)

### What Exists: Family Graph API

MyHeritage has a public REST API at `familygraph.myheritage.com`. Key facts:

- **Authentication:** OAuth 2.0. You need an application key (request at familygraph.com/get-access) and a bearer token per user
- **Format:** All responses are JSON
- **Base URL:** `https://familygraph.myheritage.com/`
- **Example call:** `https://familygraph.myheritage.com/me` → returns current user object

**What the API CAN do:**
- Read user profile, trees, individuals, families
- Read photos and media
- Read citations and sources
- Access `MatchingRequest` objects — these contain counts of pending/confirmed/rejected matches for Smart Matches and Record Matches
- Export GEDCOM (requires special `ExportGEDCOM` scope approval from MyHeritage)

**What the API CANNOT do (critical limitation):**
- **No write API for confirming/rejecting matches** — the Family Graph API is officially read-only for match actions
- No API endpoint to extract match data into the tree
- No API to save new person data pulled from a match

**Conclusion:** The Family Graph API is useful for **reading tree data and match counts**, but **cannot confirm matches or save extracted data**. For those actions, we need browser automation.

### What This Means for Architecture

The agent needs a **hybrid approach**:
- Use the Family Graph API where possible (reading tree structure, fetching individual profiles, getting match counts)
- Use **Playwright browser automation** for everything that requires clicking (confirming matches, extracting new info, saving to tree)

---

## 🏗️ Recommended Architecture

```
myheritage_agent/
├── main.py                  # Entry point, orchestration loop
├── config.py                # Thresholds, credentials, settings
├── auth/
│   ├── api_auth.py          # OAuth2 token management for Family Graph API
│   └── browser_auth.py      # Session/cookie management for Playwright
├── api/
│   └── family_graph.py      # Wrapper for read-only Family Graph API calls
├── browser/
│   ├── driver.py            # Playwright setup, stealth config, anti-bot measures
│   ├── smart_matches.py     # Navigate + process Smart Matches
│   ├── record_matches.py    # Navigate + process Record Matches
│   └── extractor.py         # Extract and selectively save new data to tree
├── agent/
│   ├── evaluator.py         # Decision logic: accept/reject based on confidence
│   └── enricher.py          # Data enrichment: photos, relatives, sources
├── storage/
│   ├── db.py                # SQLite for progress tracking (resume capability)
│   └── log.py               # Structured logging of all actions
└── tests/
    └── dry_run.py           # Run on 10 matches without saving, for validation
```

---

## 🤖 Browser Automation: Playwright (Not Selenium)

**Use Playwright, not Selenium.** Reasons:
- Handles JavaScript-heavy SPAs better (MyHeritage is a React app)
- Built-in async support — faster iteration
- Better stealth options (critical: MyHeritage has bot detection)
- Auto-waiting for elements eliminates most timing hacks

**Setup:**
```bash
pip install playwright
playwright install chromium
```

**Anti-detection (important):**
```python
# Use persistent context to reuse saved session/cookies
context = await browser.new_context(
    storage_state="myheritage_session.json",  # pre-saved cookies
    user_agent="Mozilla/5.0 ...",  # real UA string
    viewport={"width": 1440, "height": 900}
)
```

**Rate limiting — mandatory:**
- Random delay between 2–6 seconds between actions
- Random delay between 15–45 seconds between matches
- Max ~200 matches per session, then break for 30+ minutes
- Never run during peak hours if possible

---

## 🔐 Authentication Strategy

### Option A: Cookie-based (Recommended for start)

1. Log into MyHeritage manually in Chrome
2. Export cookies using a browser extension (e.g., EditThisCookie)
3. Load cookies into Playwright context:
```python
await context.add_cookies(cookies_from_export)
```
4. Verify session is alive before starting batch

**Pros:** Simple. No OAuth dance. Works immediately.  
**Cons:** Cookies expire (typically 30 days). Need to re-export periodically.

### Option B: Family Graph API OAuth (for read operations)

1. Register for an application key at `https://www.familygraph.com/getAccess`
2. Implement OAuth2 authorization code flow
3. Store bearer token securely (not in plaintext — use environment variables or keyring)
4. Use for read operations: fetching individual profiles, tree data, match counts

```python
import os
BEARER_TOKEN = os.environ["MYHERITAGE_BEARER_TOKEN"]
headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
response = requests.get("https://familygraph.myheritage.com/me", headers=headers)
```

---

## 📋 MyHeritage Web UI: Key URLs and Flow

The agent needs to know how the UI is structured:

### Matches Entry Points
- **All Discoveries:** `https://www.myheritage.com/discoveries`
- **Smart Matches:** `https://www.myheritage.com/smart-matches`
- **Record Matches:** `https://www.myheritage.com/record-matches`

### Smart Match Review Flow
1. Land on Smart Matches list
2. Each match card shows: person name, confidence indicator, "New info" badge
3. Click match card → opens comparison view
4. Review both sides (your tree vs. their tree)
5. Click **"Confirm"** button
6. Page shows extraction options — selectively check what to save
7. Click **"Save to tree"** (or click "Back to match" to confirm without saving data)

**Important UX detail:** Confirming and saving data are TWO separate actions. Confirming just registers the link between trees. Actually saving new data requires going through the extraction step. The agent must handle both flows.

### Record Match Review Flow
1. Land on Record Matches list
2. Each card shows: record type, source (census, newspaper, immigration, etc.), confidence
3. Click → opens record comparison view
4. Historical record data shown on left, tree person on right
5. Click **"Confirm"** then selectively save fields
6. Photos/documents can be attached to the person profile

### Confidence Score Location
MyHeritage shows confidence as a percentage or stars on each match card. The agent must read this value before deciding to accept. The exact CSS selector needs to be identified during initial reconnaissance (see Phase 1 below).

---

## 🧠 Decision Logic

```python
CONFIDENCE_THRESHOLD = 80  # percent

def should_accept(match):
    if match.confidence >= CONFIDENCE_THRESHOLD:
        return True
    return False

def should_extract_data(match, accepted):
    if not accepted:
        return False
    # Only extract if there's actually new info
    if match.new_info_count > 0:
        return True
    return False
```

**Extraction priority (what to pull when saving new data):**
1. Birth/death dates and places (high value, often missing)
2. Photos (grab everything — very hard to find manually)
3. Additional relatives (parents, siblings — tree expansion)
4. Source citations (links to original records — critical for genealogy integrity)
5. Newspapers/obituaries (rich narrative context)

**What NOT to auto-save:**
- Names that differ from existing data (flag for manual review instead)
- Dates that conflict with existing data (flag, don't overwrite)
- Relationships that would restructure the tree (always flag)

---

## 📦 Data Storage & Resume

The agent must be resumable — it'll run for hours and may get interrupted.

```sql
-- SQLite schema
CREATE TABLE processed_matches (
    id TEXT PRIMARY KEY,
    match_type TEXT,  -- 'smart' or 'record'
    person_id TEXT,
    person_name TEXT,
    confidence INTEGER,
    decision TEXT,    -- 'accepted', 'rejected', 'skipped', 'flagged'
    data_saved TEXT,  -- JSON: what fields were actually saved
    processed_at TIMESTAMP,
    notes TEXT
);

CREATE TABLE flagged_matches (
    id TEXT PRIMARY KEY,
    reason TEXT,
    match_data TEXT,  -- full JSON for manual review
    flagged_at TIMESTAMP
);
```

On startup: check which match IDs are already in `processed_matches` and skip them.

---

## 🔍 Phase 1: Reconnaissance (Do This First)

Before writing the full agent, run a **reconnaissance script** that:

1. Logs into MyHeritage via saved cookies
2. Navigates to the Smart Matches page
3. Takes a screenshot
4. Dumps the page HTML/accessibility tree
5. Identifies the CSS selectors for:
   - Match card container
   - Confidence score element
   - Person name element
   - "New info" count badge
   - Confirm button
   - Extraction checkboxes
   - Save to tree button

This recon data feeds into all subsequent selectors. Do NOT hardcode selectors without first inspecting the live page, because MyHeritage updates their UI.

```python
# recon.py
async def recon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state="session.json")
        page = await context.new_page()
        await page.goto("https://www.myheritage.com/smart-matches")
        await page.screenshot(path="recon_smart_matches.png")
        html = await page.content()
        with open("recon_smart_matches.html", "w") as f:
            f.write(html)
        print("Recon complete. Check screenshots and HTML.")
```

---

## 🧪 Testing Protocol

**Never run full automation without a dry run first.**

1. **Dry run mode:** navigate and read matches, log decisions, take screenshots — but never click Confirm or Save
2. **10-match pilot:** run on exactly 10 matches with actual clicking, verify log output manually
3. **50-match run:** check acceptance rate, spot-check 5 random entries in the tree for data quality
4. **Full run:** only after pilot validation

Add a `--dry-run` flag to `main.py`:
```python
parser.add_argument("--dry-run", action="store_true", help="Read and evaluate without clicking")
parser.add_argument("--limit", type=int, default=None, help="Max matches to process")
```

---

## ⚠️ Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| MyHeritage detects automation | Human-like delays, real browser UA, persistent cookies, headless=False initially |
| Account gets flagged/banned | Never run more than 200-300 matches per day. Spread across hours. |
| Wrong data saved to tree | Flag conflicting data instead of auto-saving. Always log what was saved. |
| Session expires mid-run | Check session validity before each batch. Auto-re-authenticate if possible. |
| UI changes break selectors | Build selector config in one place. Add screenshot on failure for debugging. |
| Tree corruption | Never use "Extract all info" button. Always save field-by-field. |

---

## 🚀 Implementation Order

1. `auth/browser_auth.py` — cookie loading, session validation
2. `browser/driver.py` — Playwright setup with anti-detection
3. `recon.py` — run this, document all selectors
4. `storage/db.py` — SQLite setup
5. `browser/smart_matches.py` — Smart Match navigation + reading (no clicking yet)
6. `agent/evaluator.py` — confidence scoring logic
7. `main.py` with `--dry-run` — full dry run pipeline
8. Add clicking + confirmation to `smart_matches.py`
9. `browser/extractor.py` — selective data extraction
10. `browser/record_matches.py` — Record Match flow (same pattern, different selectors)
11. Logging, error handling, resume logic
12. 10-match pilot. Review. Iterate.

---

## 🔧 Dependencies

```
playwright==1.44+
requests
sqlite3 (stdlib)
python-dotenv
rich (for nice CLI output)
loguru (structured logging)
```

---

## 📝 Notes from the Conversation

- Nikita has an active **MyHeritage Premium/PremiumPlus subscription** (renewed today) — required for confirming/rejecting matches
- Tree size: ~10,000 people — this is a large tree, match volume is in the thousands
- Priority order: Smart Matches first (higher accuracy per Nikita), then Record Matches
- Confidence threshold: **≥ 80%** for auto-accept
- Everything below 80% → log as skipped, never auto-reject (could review manually later)
- The agent should be **genuinely intelligent** — not just clicking, but reading extracted data and deciding what's worth saving

---

## 💬 First Message to Send Claude Code

> "Read this briefing fully before doing anything. Start with Phase 1: write `recon.py` and `auth/browser_auth.py`. Do not start on the full agent until we've run recon on the live MyHeritage pages and I've confirmed the selectors look correct. Ask me for the cookie export once you've written the session loading code."
