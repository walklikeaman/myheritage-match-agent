# Wiki Index — MyHeritage Automation Agent

> READ THIS FIRST before any domain question. Catalog of all wiki pages.

## Sources (ingested raw material)
| Slug | What it is |
|------|-----------|
| [agent-briefing](sources/agent-briefing.md) | Full project brief: goals, API situation, architecture, auth strategy, UI flow, decision logic, risk mitigation |

## Entities (services, systems, features)
| Slug | What it is |
|------|-----------|
| [myheritage](entities/myheritage.md) | The MyHeritage platform — subscription, tree size, bot detection |
| [smart-matches](entities/smart-matches.md) | Smart Matches feature — UI flow, confidence score, confirm + extract actions |
| [record-matches](entities/record-matches.md) | Record Matches feature — historical documents, census, immigration records |
| [family-graph-api](entities/family-graph-api.md) | Read-only REST API at familygraph.myheritage.com — what it can/cannot do |

## Concepts (rules, workflows, algorithms)
| Slug | What it is | Staleness |
|------|-----------|-----------|
| [match-evaluation](concepts/match-evaluation.md) | 80% threshold, accept/skip/flag logic | stable |
| [browser-auth](concepts/browser-auth.md) | Cookie export, Playwright session state, re-auth strategy | 90d |
| [rate-limiting](concepts/rate-limiting.md) | Human-like delays, session caps, anti-detection rules | stable |
| [data-extraction](concepts/data-extraction.md) | What to save vs flag, priority order, conflict rules | stable |
| [agent-architecture](concepts/agent-architecture.md) | Hybrid API+Playwright design, module map, phase plan | active |
| [selectors](concepts/selectors.md) | CSS selectors for MyHeritage UI — MUST recon before use | 30d |
| [session-economics](concepts/session-economics.md) | Why MAX=100; the extract-step root cause of "saveButton not found"; safety verdict | 60d |
| [graph-accumulation](concepts/graph-accumulation.md) | Incremental local family-graph capture during confirmation, no manual GEDCOM re-export needed; generation-depth limitation | 60d |

## Status
- **Phase 1**: `auth/browser_auth.py` + `recon.py` + `storage/db.py` ✅
- **Phase 2**: Browser automation + evaluator — waiting on recon output
- **Recon**: waiting for cookie export from Nikita
