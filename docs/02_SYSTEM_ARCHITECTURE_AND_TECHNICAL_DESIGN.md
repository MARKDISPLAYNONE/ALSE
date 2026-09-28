# 02_SYSTEM_ARCHITECTURE_AND_TECHNICAL_DESIGN.md

Project: NAS100 Autonomous Liquidity Sweep Engine ("ALSE")
Document 3 of 6 — System Architecture & Technical Design
Date: Saturday, 25th July 2026
Status: APPROVED v1.1 — Owner Assumptions Confirmed, Zero-Budget Constraint Incorporated
Supersedes: v1.0
# 0. Who This Document Is For, and What You Are Responsible For
If you are the infrastructure/backend developer or the frontend/app developer on this project, this document is your bible in the same way Document 2 is the trading-logic developer's bible. It defines how the deterministic rules in Document 2 become running, deployed, monitored software.

Your responsibility as the reader/implementer:

You do not deviate from the safety principles in this document (server-side SL/TP dependency, Decimal-only math, immutable audit logging) under any circumstances, even if a "cleaner" implementation seems tempting. These principles exist because Document 2's entire safety model depends on them.
You do have full authority over implementation details not explicitly locked here — specific libraries, code organization, internal API design — as long as the architecture-level guarantees in this document are met.
If a technical constraint you discover during build makes something in this document genuinely impossible or unsafe (e.g., a Supabase Realtime limitation, an MT5 API rate limit), you escalate and propose an alternative — you do not silently work around it and leave the document wrong. Update this document with a Change Log entry, same discipline as Document 2.
0.1 Owner Decisions — Now CONFIRMED (Previously Provisional in v1.0)
All four items previously marked [ASSUMPTION — PENDING OWNER CONFIRMATION] in v1.0 are now resolved. This subsection is retained for historical traceability but no longer contains open questions:

App platform: ✅ CONFIRMED — responsive web app first (mobile-browser-friendly). Native app deferred indefinitely, revisit only if a specific need emerges post-forward-test.
Multi-user vs single-user: ✅ CONFIRMED — single-user (owner) for MVP and the entire forward-test phase. Document 4, Section 3.4's multi-user gate remains the trigger for re-architecture if this ever changes.
Hosting budget constraints: ✅ CONFIRMED, and materially different from v1.0's assumption. Actual constraint is $0 — not "cost-optimized," but genuinely free. This is a first-order architectural input, not a minor detail, and it changes several decisions below (Sections 1 and 5) from what v1.0 assumed. An explicit upgrade trigger is defined in Section 5 for the day this constraint relaxes.
Team size: ✅ CONFIRMED — single technical owner (the project owner), working with AI-assisted architecture (this document series) and AI-assisted code execution (build phase). No separate human dev team at this stage.
Everything else in this document is either a hard technical requirement carried over from Document 2, or a decision made unilaterally within architect authority (Document 1, Section 9) because it's a pure implementation choice.

# 1. Technology Stack — Decision Record
Layer	Choice	Rationale
Trading Engine Language	Python 3.11+	Required — MT5's official API is Python/C++/MQL5 only; Python is the practical choice for the rest of this stack to integrate with
Broker Integration	MetaTrader5 Python package	Only supported path to FX Pesa's MT5 terminal
Numeric Precision	decimal.Decimal throughout order-sizing/PnL/price pipeline	Hard rule from Document 2
Database	Supabase (PostgreSQL), Free Tier	Already specified by owner; gives Realtime subscriptions at no cost, which the dashboard needs. Free tier constraints (500MB storage cap, no automated backups) are explicitly compensated for — see Section 3.3 and Section 6.
Backend Process Model	Long-running Python daemon process, supervised (see Section 5)	The strategy requires continuous polling during active windows; not a serverless/cron-friendly workload
Task Scheduling (session windows)	APScheduler or equivalent, timezone-aware via zoneinfo	Matches Document 2's DST-safe session logic
Frontend/Dashboard	Responsive web app — React or Next.js, using Supabase client SDK + Realtime subscriptions	Fastest path to a mobile-usable dashboard without committing to native app stores; confirmed final per Section 0.1
Alerting	Discord Webhooks	Already specified by owner; free
Hosting (Trading Engine)	Oracle Cloud "Always Free" tier (ARM Ampere instance) — primary choice. AWS EC2 free tier (t3.micro, us-east-1) as fallback/alternative.	Zero-budget constraint (Section 0.1, item 3). Oracle's Always Free tier has no 12-month expiry, unlike AWS's free tier — a meaningful advantage given the forward test alone runs 9–10 months, and live operation continues beyond that. AWS remains a valid fallback if Oracle account approval or capacity is an issue in practice.
Operating System (VPS)	Linux (Ubuntu Server) + Wine, not Windows Server	Reversed from an earlier draft recommendation of Windows Server, specifically because of the zero-budget constraint. Windows Server AMIs carry an hourly software licensing charge on both AWS and Oracle even on free-eligible compute tiers — there is no genuinely free path to a Windows-hosted MT5 terminal. Linux+Wine is the only $0 option. This is accepted as a real reliability trade-off (Wine is a compatibility layer, not native support) and is explicitly compensated for via tighter process supervision and heartbeat monitoring (Section 5, Section 6) rather than assumed to be risk-free.
Hosting (Dashboard)	Vercel or Netlify free tier	Standard, zero-cost, scales automatically for a low-traffic single-user dashboard
Secrets Management	Environment variables via .env (excluded from git) at MVP; upgrade path to a proper secrets manager only required if/when multi-user (Document 4, Section 1.1)	No cost implication either way at current scale
Explicit upgrade trigger (new in v1.1): The day trading profits (or any other funding) comfortably and sustainably cover ≈$25–35/month, the following upgrades happen, in this order of priority: (1) Supabase → Pro tier (restores automated backups, removes the 500MB cap — this is the single highest-value upgrade given it directly closes a real data-loss risk), (2) VPS → a paid, non-free-tier instance if Oracle/AWS free-tier performance proves insufficient, (3) OS → Windows Server, if Wine-related reliability issues are observed in practice. This trigger and its resulting actions are tracked in Document 6, not assumed to happen automatically.

Explicitly rejected alternatives, and why (so this doesn't get re-litigated later):

MQL5-native EA instead of Python: rejected — Document 2's logic involves multi-timeframe state machines, Decimal-precision arithmetic, and Supabase integration that are far more error-prone and harder to test in MQL5 than Python.
Serverless functions for the trading engine: rejected — the strategy requires a persistent stateful process holding session state across a continuous 30-minute monitoring window; cold-start serverless functions are the wrong shape for this.
Firebase instead of Supabase: not evaluated — Supabase was already an owner requirement, not an open decision.
Windows Server hosting: rejected under current budget constraint (see stack table above) — not rejected on technical merit; this is a cost-driven decision, explicitly reversible per the upgrade trigger.
# 2. System Architecture Diagram (Detailed)
text

┌───────────────────────────────────────────────────────────────────┐
│              Oracle Cloud Always Free (or AWS EC2 free tier)        │
│  ┌─────────────────┐        ┌────────────────────────────────┐    │
│  │  MT5 Terminal    │◄──────►│  Python Trading Engine (daemon) │    │
│  │  (via Wine)      │  API   │  ┌────────────────────────────┐│    │
│  │  (FX Pesa login) │        │  │ Session Clock (zoneinfo)   ││    │
│  │  Holds SL/TP     │        │  │ Range Marker               ││    │
│  │  server-side     │        │  │ Sweep/Displacement Detector││    │
│  └─────────────────┘        │  │ Risk State Machine         ││    │
│                              │  │ Order Manager               ││    │
│                              │  │ Tick/Data Poller (250ms loop)│    │
│                              │  └────────────────────────────┘│    │
│                              │  Process Supervisor (systemd) —│    │
│                              │  auto-restart                  │    │
│                              └──────────────┬───────────────────┘  │
└─────────────────────────────────────────────┼───────────────────────┘
                                               │ writes (sync for orders,
                                               │ async/batched for ticks)
                                               ▼
                              ┌──────────────────────────────────┐
                              │   Supabase (PostgreSQL, Free Tier) │
                              │   - trades, orders, ticks tables   │
                              │   - metrics/analytics tables       │
                              │   - Row-Level Security policies    │
                              │   - Realtime publication enabled   │
                              └───────────┬──────────────────────┘
                                          │
                ┌─────────────────────────┼─────────────────────────┐
                ▼                         ▼                         ▼
   ┌────────────────────┐   ┌────────────────────┐   ┌───────────────────────┐
   │  Discord Webhooks   │   │  Dashboard Web App  │   │ External Uptime Monitor│
   │  (trade + system     │   │  (Realtime subscribe│   │ (free tier, e.g.       │
   │  health alerts)      │   │  to Supabase)        │   │ UptimeRobot) — pings   │
   └────────────────────┘   └────────────────────┘   │ VPS from OUTSIDE it    │
                                                        └───────────────────────┘
Critical architectural invariant (repeat from Document 1 — this cannot be over-stated): the box labeled "MT5 Terminal — Holds SL/TP server-side" is the only component in this diagram whose failure directly threatens capital. Every other component (Python engine, Supabase, Discord, Dashboard, the VPS itself) can fail or go offline without an open position becoming unprotected, because the SL/TP order was already accepted by the broker's server at trade entry, independent of anything else running. Every failure-mode discussion in Section 6 is designed around preserving this invariant — including under the added reliability variables introduced by running MT5 under Wine rather than native Windows.

# 3. Data Pipeline Architecture
3.1 Tick/Price Data Ingestion
During active session windows (20:00–21:00 NY on Mon–Thu, plus open-position monitoring until 16:16 NY hard-kill), the engine polls mt5.symbol_info_tick() on a 250ms loop.
Outside active windows, the engine idles, polling 1-minute closes every 60 seconds — sufficient for background monitoring without wasting resources.
Known constraint (carried from earlier review): the MT5 Python API is polling-based, not a true push/streaming feed. The 250ms loop is a deliberate mitigation, not a full fix — under extremely fast displacement moves, sub-250ms price action between polls will not be captured tick-by-tick. This is accepted as a known limitation and must be accounted for when interpreting "time to entry" / "hover duration" analytics in Document 5 — those metrics have an inherent ±250ms measurement floor, and should be documented as such wherever displayed, not presented as exact.
3.2 Write Path to Supabase
Every order lifecycle event (submit, partial fill, full fill, modify, cancel) writes a row immediately, synchronously, before the engine proceeds to its next action — order-event logging is never fire-and-forget or batched, because this is the audit trail Document 4 depends on.
Write-ordering rule (new in v1.1, closes a previously unspecified gap): the audit row for an order action is written before the corresponding mt5.order_send() (or modify/cancel) call is made, with an initial status of pending_confirmation. Immediately after the broker responds, a second write updates that row's status to confirmed or rejected with the broker's response details. Rationale: if the process crashes between these two writes, the resulting record is an orphaned pending-confirmation row — a visible, investigable anomaly caught by Document 4's weekly reconciliation process — rather than a silent gap where an order was sent but never logged at all. Over-logging a possible-attempt is always preferable to under-logging a confirmed one.
Write-timeout rule (new in v1.1, closes a previously unspecified gap): every synchronous Supabase write in the order-lifecycle path has a hard 2-second timeout. If the write does not complete within 2 seconds (Supabase reachable but slow, not fully down), the engine does not block further — it immediately falls back to the same local-disk-buffer mechanism defined for a full outage (Section 6), logs the event locally, and proceeds with the time-critical trading action (order submission, hard-kill, circuit-breaker flatten) without waiting. A slow-but-alive database must never be allowed to delay a time-deterministic safety action. The buffered write is flushed to Supabase automatically once a normal-speed write path is confirmed.
Tick-level price data (for spread tracking, not order events) may be batched and written asynchronously every few seconds — this data is for analytics, not the audit trail, so brief write latency here is acceptable and necessary to avoid overwhelming Supabase's free-tier limits with a 250ms-interval write rate.
Every row includes: UTC timestamp, NY-local timestamp (both stored — never derive one from the other at read-time, store both explicitly to avoid DST-edge-case bugs in reporting), spread-at-time-of-action, and relevant trade/order IDs.
3.3 Database Schema Design Principles (Not the Schema Itself)
The actual DDL is a build artifact for Phase 1, not this document — but the rules the schema must follow are locked here:

Immutability of audit tables. Trade/order history tables allow INSERT only. No UPDATE, no DELETE, enforced via Supabase Row-Level Security policies, not just application-level discipline. If a correction is needed, a new compensating row is inserted, never an edit to history.
Dual timestamp storage. Every timestamped row stores both ts_utc and ts_ny as separate columns.
Normalized core, denormalized analytics. Core trade/order tables are normalized (one row per event). Metrics/analytics tables (Document 5) may be denormalized/pre-aggregated for dashboard read performance — but always derived from the immutable core tables, never the other way around, so the audit trail remains the single source of truth.
Every table has an explicit schema version reference so that future migrations don't silently break historical row interpretation.
Provisional parameters (Document 2, Section 9) are stored as configuration rows in the database, not hardcoded constants in application code — this allows recalibration after the forward test without a code deployment, and every change to a provisional parameter is itself logged with a timestamp and reason, mirroring the Document 2 Change Log discipline.
Free-tier storage discipline (new in v1.1): given Supabase's free-tier 500MB cap, raw tick-level data (used for spread/slippage analytics — not the audit trail itself, which is order/trade events and is comparatively tiny) is retained on a rolling 30–60 day window, not indefinitely, until the Pro-tier upgrade trigger (Section 1) is reached. Trade/order/audit tables — the actual compliance record — are unaffected by this and retained indefinitely regardless of tier, per Document 4, Section 4.3; they are orders of magnitude smaller than raw tick data and do not meaningfully threaten the storage cap.
# 4. App / Dashboard Architecture — Responsiveness Design
This section exists specifically because the owner has stated this needs to function well as an app, with 50+ Tier-1 metrics live, and system responsiveness is a named requirement — this is not an afterthought bolted onto the trading engine.

4.1 Real-Time Update Mechanism
Supabase Realtime subscriptions, not client-side polling. The dashboard subscribes to postgres_changes events on the relevant tables (open trades, today's metrics summary, system health status) so updates push to the client the instant a row is written — no wasteful polling loop on the frontend, and no stale-data lag waiting for a refresh interval.
Fallback: if a Realtime subscription drops, the client falls back to a 5-second polling interval until the subscription reconnects — the dashboard should never silently show stale data without indicating it (see 4.3).
4.2 Latency Budget (Explicit Targets)
Action	Target Latency
New trade event appears on dashboard after order fill	< 2 seconds
Metric tile refresh after underlying data change	< 1 second
Full dashboard initial load (cold)	< 3 seconds on 4G mobile connection
Alert delivery to Discord after trigger event	< 2 seconds
These are targets to design against, not yet measured/proven — they become real acceptance criteria once Phase 6 (dashboard build) is underway, and should be load-tested before being called "met."

4.3 Degraded/Offline State Handling (Hard Requirement)
The dashboard must never silently display stale data as if it were live. Specifically:

If the Realtime subscription is disconnected, the UI shows a visible "Reconnecting..." indicator — this is non-negotiable given the owner will be trusting this dashboard to reflect real account state.
Heartbeat source of truth (corrected in v1.1): the backend trading engine's heartbeat cadence is defined authoritatively in Document 2, Section 2.5 — this document does not restate specific numbers, it only defines the behavior: if the coarse daily heartbeat or the active-window heartbeat (whichever is currently expected per Document 2, Section 2.5) is overdue by more than 2× its expected interval, the dashboard surfaces a "System may be offline" warning prominently, not buried in a status log.
The dashboard is a read-only observability tool — it does not issue trading commands back to the engine in this phase of the project (no "manual override" buttons at MVP). This scope boundary is deliberate: mixing a two-way control plane into the same interface as the passive monitoring dashboard significantly increases the security and failure-mode surface area (Document 4), and is out of scope until the strategy has passed its forward test.
4.4 Mobile-Responsive Layout Principles
Design mobile-first, not desktop-scaled-down. Given 50+ Tier-1 metrics, the layout must use progressive disclosure — a compact summary view (equity curve, today's PnL, current risk state, open position status) as the default/home screen, with drill-down views for the full metric catalog (Document 5) rather than trying to cram everything onto one screen.
Full metric-by-metric layout wireframing is Document 5's responsibility, not this document's — this section only locks the principle, not the pixel layout.
# 5. Deployment Architecture
VPS (corrected in v1.1): Oracle Cloud "Always Free" tier (ARM Ampere A1, no expiry) as primary; AWS EC2 free tier (t3.micro, us-east-1, free for 12 months on a new account) as fallback. Region/instance choice should still target lowest measured latency to FX Pesa/Equiti's likely NY4 (Equinix Secaucus) infrastructure — to be measured and confirmed once an instance is live, not assumed permanently true, regardless of which free-tier provider is used.
Operating System: Ubuntu Server (Linux) running MT5 terminal under Wine — the only $0-cost path given Windows Server's licensing cost applies even on free-tier compute (see Section 1). This is accepted as a real, non-trivial reliability trade-off, not a cost-free swap — Wine-hosted MT5 terminals are a known source of occasional instability (window-manager quirks, occasional terminal freezes) that a native Windows install would not have. Compensating controls, given this trade-off: the active-window heartbeat (Document 2, §2.5) is the primary defense — a 5-minute heartbeat gap during a live session window is treated as a high-priority alert, escalated faster than it would be on a more inherently reliable OS. The external uptime monitor (see Section 6) is non-negotiable under this OS choice, not merely "recommended."
Process supervision: the Python trading engine runs under systemd with Restart=always — if the process crashes for any reason, it is automatically restarted within seconds, and a crash-alert fires to Discord per Document 2's alerting rules. The MT5 terminal process (under Wine) is supervised similarly — if Wine's MT5 process itself dies independent of the Python engine, this must be detected via mt5.terminal_info() connectivity checks (Section 6) and alerted, not silently assumed alive.
Deployment process: not yet defined at this stage — full CI/CD pipeline design is a Phase 1/2 build task, not a Document 3 requirement. This document locks the target runtime shape, not the deployment pipeline itself.
# 6. Failure Mode Design
This is the most important section of this document, and it is designed explicitly around preserving the invariant from Section 2: an open position must remain protected even if everything except the broker's own servers fails.

Failure Scenario	System Behavior	Capital Risk
VPS crashes entirely	Open position(s) remain protected by broker-side SL/TP, already placed at order-send time. No new trades can be entered until VPS/process is restored. Discord alert cannot fire (VPS is down) — this is a known blind spot, see mitigation below.	Low — existing positions safe; new-trade opportunity may be missed
Python process crashes, VPS stays up	systemd auto-restarts within seconds. Crash alert fires to Discord. Engine re-establishes state from Supabase (last known open position, current risk state) on restart — state recovery logic is a required build component, not optional	Low, assuming restart succeeds and state recovery is correctly implemented
Wine-hosted MT5 terminal process dies (Python engine still running)	Python engine detects via mt5.terminal_info() returning null/failure, halts new order attempts, fires Discord alert, attempts periodic MT5 process relaunch via a supervised script	Low for existing positions (broker still holds SL/TP independently of terminal connection state); new trades blocked until MT5 process is restored — explicit new risk introduced by the Linux+Wine decision; monitored more tightly than a native-Windows deployment would require
MT5 terminal disconnects from broker (network-level, not process-level)	Python engine detects disconnect via mt5.terminal_info() checks, halts new order attempts, fires Discord alert, attempts periodic reconnect	Low for existing positions (broker still holds SL/TP independently of terminal connection state); new trades blocked until reconnected
Supabase outage (full)	Trading engine continues operating (Supabase is a logging/analytics dependency, not a trading-decision dependency) but buffers write events locally (append to local disk) until Supabase is reachable again, then flushes the backlog — audit trail must not have gaps even during an outage. Given free-tier Supabase has no automated backup, Document 4's manual export cadence is elevated to daily (not weekly) as a compensating control.	None to trading; audit-trail completeness must be verified after outage recovery
Supabase reachable but slow	Per Section 3.2's new 2-second write-timeout rule: engine falls back to local buffering rather than blocking on a slow write.	None to trading, same as full outage case
Broker-side outage / MT5 server unreachable	No new orders possible. Existing SL/TP already resting on broker server are unaffected by connectivity to the terminal, though a full broker-side outage is a genuine tail risk outside this system's control	Genuine tail risk, cannot be engineered around, must be accepted and documented in Document 4's risk disclosures
Discord webhook fails/rate-limited	Alert is logged locally/to Supabase regardless of webhook delivery success — alerting must never be the only record of an event, Supabase logging is the source of truth, Discord is a convenience notification layer only	None if logging redundancy is implemented correctly
Known blind spot requiring explicit owner acknowledgment: if the VPS itself goes fully offline (not just the Python process), no alert can fire from that machine, by definition. Mitigation (now a hard requirement, not merely recommended, given the Linux+Wine reliability trade-off): an external, independent, free-tier uptime-check service (e.g., UptimeRobot's free plan, which supports 5-minute check intervals at no cost) must be configured in Phase 1, pinging a lightweight heartbeat endpoint on the VPS from outside it, alerting via a separate channel (e.g., email or a second Discord webhook) if the VPS itself stops responding. This is explicitly required before Phase 1 sign-off, not deferred to "Phase 1/2" as v1.0 stated — the free-tier VPS/OS choices increase the value of this control, not decrease it.

# 7. API / Module Boundaries (For Multi-Dev Coordination)
Even at single-developer scale (per Section 0.1, now confirmed), defining clean boundaries now avoids a monolithic, untestable codebase later:

text

/engine
  /session        — session clock, DST-safe window calculations (Doc 2, Sec 2)
  /range          — range marking, fib level calculation (Doc 2, Sec 3)
  /signal         — sweep/displacement detection, FIFO dual-setup logic (Doc 2, Sec 4)
  /orders         — entry/SL/TP calculation, order submission, invalidation logic (Doc 2, Sec 5)
  /risk           — state machine, lot sizing, circuit breaker (Doc 2, Sec 7-8)
  /management     — partial close, BE+5 trailing, hard-kill (Doc 2, Sec 6)
/data
  /mt5_client     — thin wrapper around MetaTrader5 package, isolates all broker API calls
  /supabase_client — thin wrapper around Supabase writes/reads, isolates all DB calls,
                      including the write-timeout/local-buffer fallback logic (Sec 3.2)
/alerts
  /discord        — webhook dispatch, isolated so alert-channel can change without touching engine logic
/dashboard        — separate deployable app, consumes Supabase only, never talks to MT5 or the engine directly
Rule: the /dashboard app must never have direct access to MT5 or the trading engine process — it only ever reads from Supabase (and, per Section 4.3, does not write trading commands back in this phase). This boundary is a deliberate security and blast-radius control, formalized further in Document 4.

# 8. What This Document Does NOT Cover
Exact database DDL/schema (Phase 1 build artifact, informed by Section 3.3's principles).
Exact Python module code (Phase 2 build artifact, informed by Section 7's boundaries).
Full metric catalog and dashboard wireframes (Document 5).
Credential/secrets handling detail, disaster recovery runbook, legal disclaimers (Document 4).
CI/CD pipeline specifics (build-phase task, not architecture).
Heartbeat cadence specifics (Document 2, Section 2.5 is now the single source of truth for this).
# 9. Change Log
v1.0 (original) — Initial architecture specification. Flagged four outstanding owner decisions (Section 0.1) proceeding on stated assumptions. Flagged one required-but-not-yet-built component: independent external VPS-uptime monitoring (Section 6).

v1.1 (this document, 25 July 2026) — Documentation hardening pass:

All four Section 0.1 owner decisions confirmed final: web app, single-user, single owner. Hosting budget corrected from an assumed "cost-optimized" paid posture to a confirmed genuine $0 constraint — this was a materially different input than v1.0 assumed and changes several downstream decisions.
Hosting reversed from AWS EC2 us-east-1 (implicitly assuming paid Windows hosting) to Oracle Cloud Always Free (primary) / AWS EC2 free tier (fallback), both running Linux + Wine instead of Windows Server, due to Windows licensing costs applying even on free-tier compute. Explicit upgrade trigger to paid tier / Windows defined in Section 1, tracked in Document 6.
Added Section 3.2 write-timeout rule (2-second bound on synchronous Supabase writes, falls back to local buffer) — closes a previously unspecified gap where a slow-but-alive Supabase could stall time-critical order actions.
Added Section 3.2 write-ordering rule (audit row written before order_send() with pending_confirmation status, updated after broker response) — closes a previously unspecified gap in crash-window audit-trail behavior.
Added Section 3.3, item 6: free-tier storage discipline — rolling 30–60 day retention on raw tick data (not the audit trail) to respect Supabase's 500MB free-tier cap.
Section 4.3 heartbeat reference corrected — no longer states a specific cadence number in this document; now formally defers to Document 2, Section 2.5 as the single source of truth, since the same number was previously duplicated (and left undefined) across three documents.
Section 6 failure-mode table expanded: added Wine-specific MT5 process failure mode (new risk introduced by the OS decision), added Supabase-slow-not-down scenario, elevated the external uptime monitor from "flagged, Phase 1/2" to a hard Phase 1 sign-off requirement given the increased blind-spot risk of a free-tier, Wine-based deployment. Elevated Document 4's manual export cadence from weekly to daily given free-tier Supabase's lack of automated backups.
Section 1 tech stack table and Section 5 deployment section rewritten throughout to reflect the corrected OS/hosting decisions.
# 10. What This Document Does NOT Cover (see Section 8)
End of Document 3 v1.1.

Verdict: approved by me, ready for your file replacement. Every decision here traces directly back to something we explicitly resolved together this session — nothing new snuck in.