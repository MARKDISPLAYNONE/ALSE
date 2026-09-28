# 00_PROJECT_CHARTER_AND_SYSTEM_OVERVIEW.md

**Project: NAS100 Autonomous Liquidity Sweep Engine ("ALSE")**
**Document 1 of 6 — Project Charter & System Overview**
**Date: 25th July 2026**
**Status: APPROVED v1.1 — Synchronized Against Hardened Document Set**
**Supersedes: v1.0**
# 0. Who This Document Is For, and What You Are Responsible For
If you are reading this document, you are either the lead developer taking over this project, a new senior engineer joining it, or the project owner returning to it after time away. This document exists so that any one of those people can read this single file and understand the entire system's purpose, shape, and rules — without reading a line of code.

Your responsibility as the reader:

You are expected to understand the full strategy logic, architecture, and risk framework described here before touching Documents 2–6 or any codebase.
You do not have unilateral authority to change strategy logic, risk parameters, or hard safety caps (SL bounds, circuit breaker thresholds, kill-switch timing) described in this document or Document 2. Any such change requires explicit sign-off from the project owner and must be logged in the Document 2 Change Log — silent changes are treated as defects, not features, on this project. This rule exists because of hard-won experience: this exact system went through multiple review cycles where undocumented logic changes nearly went into production undetected.
You do have unilateral authority over implementation details — code structure, refactors, library choices, internal module boundaries — as long as the observable behavior matches Document 2 exactly.
If you inherit this project mid-build, your first two actions are: (1) read this document fully, (2) read the most recent entry in session-handover.md to understand exactly where the project stood when you took over. Do not begin writing code before both are done.
If anything in this document contradicts anything in Documents 2–6, stop and flag it — do not guess which one is correct. Contradictions are architecture defects and get resolved explicitly, not silently picked by whoever notices first. (This exact rule caught four stale cross-references in this document during the 25 July 2026 hardening pass — see Section 11 Change Log.)
# 1. Executive Summary
ALSE is a fully autonomous algorithmic trading system that trades a single instrument — NAS100 (via FX Pesa's UT100 CFD) — using a deterministic liquidity-sweep strategy on a fixed daily time window, with autonomous position sizing, a self-adjusting risk state machine, hard safety caps at every layer, and a full audit-trail/analytics pipeline feeding a mobile-responsive dashboard app.

The system is designed to run with zero manual intervention during live trading hours. The only human inputs are: (1) setting the base risk-ratio parameter, (2) responding to alerts (circuit breaker trips, system errors, disconnects), and (3) periodic review of forward-test performance against defined pass/fail criteria.

This is not a discretionary trading tool with automation bolted on. Every decision point that would normally require human judgment (which swing counts, what SL to use, when to throttle risk, what happens when a broker rejects an order) has been converted into an explicit, deterministic, numerically-defined rule through multiple rounds of adversarial technical review. If you find a decision point in the code that still requires human judgment, that is a bug in the specification and must be escalated, not silently resolved by whoever is coding it that day.

# 2. Business Context — Why This Exists
Problem being solved: Manual/discretionary execution of a liquidity-sweep strategy is inconsistent, emotionally biased, and cannot enforce strict risk discipline (position sizing, throttling after win streaks, hard time-based exits) at the speed and consistency required for a leveraged, time-boxed setup.
Target outcome: A system that trades a narrow, well-defined daily setup with strict, provable risk controls, produces a fully auditable trade history, and can be objectively evaluated against hard pass/fail criteria over a live forward-test period — rather than relying on subjective "it felt like a good system" assessments.
Current phase: Specification hardening is complete, including a full six-document cross-reference audit and remediation pass (25 July 2026) that closed the majority of previously open items — see Document 6, Section 3. No code has been written yet. This document marks the transition from "architecture debate" to "build execution."
What "success" looks like at the ~9–10 month mark (timeline corrected — see Section 3 below): A completed forward test (Document 2, Section 9.5 criteria — corrected citation, was previously misstated as "Section 6") with either a clear PASS (scale to larger capital), a clear FAIL (shut down, post-mortem, no further capital risked), or a REVIEW status requiring human analysis of the trade distribution before any further decision.
# 3. The Strategy Thesis — In Plain English
This section explains why the system trades the way it does, in narrative form. The exact numeric rules live in Document 2 — this is the "why," not the "how."

The strategy is built on a simple market-behavior premise: at the start of a specific daily session window, price often makes an aggressive move to "sweep" (take out) a recent high or low — triggering stop-losses and drawing in breakout traders — before reversing hard in the opposite direction. The system watches for exactly this pattern inside a fixed 30-minute execution window each trading day:

Mark a range. In the first half of the session window, the system watches price for 30 minutes and records the highest and lowest price reached — this becomes the reference range for the day.
Wait for a sweep. In the second half of the window, the system watches for price to break beyond that range's high or low.
Wait for confirmation. A sweep alone isn't enough — the system requires a specific, numerically-defined candle close back inside the range (with a minimum penetration distance and a minimum "body strength") before treating the sweep as a genuine reversal signal rather than noise.
Enter on a retracement. Once confirmed, the system places a limit order at a fixed proportion of the original range (not the sweep move itself) and waits for price to trade back to that level.
Manage the trade mechanically. Stop-loss and take-profit are placed at fixed, formula-derived levels the instant the order is placed — enforced by the broker's own servers, not by the Python code, so a VPS crash cannot leave a position unprotected. Partial profit-taking and stop adjustments happen automatically at defined milestones.
Force-close, no exceptions. Every trade is closed at a fixed time each day regardless of profit or loss — the system does not hold positions indefinitely hoping for a better outcome.
Layered on top of this trade logic is a risk state machine: the system risks a higher percentage of capital per trade by default, but automatically cuts risk to a much smaller fraction after a streak of wins (protecting accumulated gains), and automatically restores full risk after the first subsequent win — without any manual lot-size adjustment ever required from the user. A hard daily loss limit halts all trading (and flattens open positions) if breached, regardless of what the risk state machine is doing.

Trading calendar rationale (corrected, v1.1 — see Document 2, Section 1 for the full account): The strategy trades only Monday through Thursday. This is not, as an earlier draft of this document stated, a workaround for a fragmented Friday session — it is a structural fact of the broker's actual trading hours: the market closes for the week on Friday afternoon, hours before this strategy's daily window even opens, meaning what might be assumed to be "Friday trading" is already part of the Thursday-evening-through-Friday-afternoon session already being traded. Sunday is excluded by deliberate risk-management choice, not because the market is closed — the market is technically open a few hours before this strategy's window starts on a Sunday, but the post-weekend-reopen period is a well-documented thin-liquidity window, and Sunday exclusion avoids trading the strategy's edge against potentially distorted post-reopen conditions.

# 4. High-Level System Architecture
text

┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   MT5 Terminal   │◄────►│   Python Trading      │◄────►│    Supabase      │
│  (FX Pesa Login) │     │   Engine (VPS)        │     │   (PostgreSQL)   │
│  - Executes      │     │   - Strategy logic     │     │   - Trade log    │
│    orders        │     │   - Risk state machine │     │   - Tick/order log│
│  - Holds SL/TP   │     │   - Session clock      │     │   - Analytics data│
│    server-side   │     │     (NY tz, DST-safe)  │     │   - Metrics tables│
└─────────────────┘     └──────────────────────┘     └─────────────────┘
        │                                                      │
        ▼                                                      ▼
┌──────────────────┐                                 ┌─────────────────────┐
│  Discord Alerts   │                                 │   App / Dashboard    │
│  - Trade lifecycle │                                 │   - Real-time metrics│
│  - System health   │                                 │   - Mobile-responsive│
│  - Rejections      │                                 │   - 60+ Tier-1 metrics│
└──────────────────┘                                 └─────────────────────┘
(Note, v1.1: "VPS" here refers to whichever free-tier or paid compute the project is currently running on — Document 3 specifies the current concrete choice, Linux + Wine on a free-tier host, driven by the project's current $0 infrastructure budget. This diagram intentionally stays generic at the charter level; Document 3 is the authoritative source for the specific hosting decision.)

Design principle driving this shape: the trading engine's safety does not depend on any other component staying alive. SL/TP live on the broker's server the instant an order is placed — if the VPS, the Python process, or the Supabase connection all fail simultaneously, the open position is still protected. Everything else in the diagram (logging, alerting, dashboard) is observability and control — not a dependency of trade safety.

# 5. Roles & Responsibilities Matrix
Area	Owns	Cannot Unilaterally Decide
Strategy Logic (Doc 2)	Lead Quant Dev	Any change to sweep/displacement/entry/risk rules — requires owner sign-off + Change Log entry
Infra/App (Doc 3)	Backend/Infra Dev	Choice of hosting region if it affects latency assumptions already documented
Security/Legal/Compliance (Doc 4)	Project Owner + Infra Dev jointly	Nothing here is ever "just decided" by a dev alone — legal/compliance items always route through the owner
Metrics/Dashboard (Doc 5)	Frontend/Analytics Dev	Which metrics are Tier-1 vs Tier-2 (owner decides priority, dev implements)
Phase Tracking (Doc 6)	Project Owner (with dev input)	N/A — this is a status document, always current
session-handover.md	Whoever closes out a 5-task block	N/A — mandatory after every 5 tasks, no exceptions
# 6. Document Map — How the 6 Documents Fit Together
00_PROJECT_CHARTER_AND_SYSTEM_OVERVIEW.md (this document) — start here, always.
01_STRATEGY_AND_EXECUTION_LOGIC_SPEC.md — the exact, deterministic trading logic. The trading engine is built from this line by line. Includes the versioned Change Log and the Forward-Test Pass/Fail/Review criteria (Section 9.5).
02_SYSTEM_ARCHITECTURE_AND_TECHNICAL_DESIGN.md — how Document 2's logic becomes running software: data pipeline, database design principles, app responsiveness architecture, failure-mode handling.
03_RISK_SECURITY_LEGAL_COMPLIANCE.md — credential/security handling, disaster recovery, legal disclaimers, audit-trail requirements, data privacy.
04_METRICS_ANALYTICS_AND_DASHBOARD_SPEC.md — full 112-metric catalog (60 marked Tier-1 — corrected, v1.1), dashboard UI spec, alert-to-metric mapping.
05_PHASE_TRACKER_AND_ROADMAP.md — living status document: what phase we're in, what's done, what's blocked, realistic timelines (including the extended forward-test window driven by Mon–Thu-only trading frequency).
Plus: session-handover.md — not numbered, not static, updated every 5 completed tasks, kept outside the core 6 so it can be freely appended without disturbing the finalized specs.

# 7. Glossary
Term	Meaning
Sweep	Price breaking beyond the marked range's high or low
Displacement / Shift	The confirming candle close back inside the range, meeting the numeric penetration + body-ratio threshold
MSS	Market Structure Shift — used loosely in early drafts; formally replaced by the numeric displacement filter in Document 2
Fib Range	The proportional level system (0.0/0.25/0.5/0.75/1.0 and extensions) drawn from the marked range, used for entry/SL/TP
R	One unit of risk (the SL distance in points, expressed as a multiple for profit targets, e.g. "1.5R")
Throttle Phase	The reduced-risk (0.5%) state entered after 5 consecutive wins
Aggressive Phase	The default 2%-risk state
Circuit Breaker	The daily hard stop triggered at 4% drawdown from start-of-day equity — flattens all positions, halts new trades for the day
Hard Kill (16:16 NY)	Time-based forced close of all open positions, regardless of PnL
Provisional Parameter	A numeric threshold (e.g., 10pt displacement, 15-100pt SL caps, and the Section 9.5 forward-test thresholds) accepted for MVP but explicitly flagged for recalibration once forward-test data accumulates
Hard Fail / Review / Pass	(New, v1.1) The three possible forward-test verdicts defined exhaustively in Document 2, Section 9.5 — see that section for the full precedence-ordered decision logic
# 8. Non-Negotiable System Principles
These are locked. Any code, document, or discussion that contradicts these should be treated as an error, not a valid alternative:

All price, lot-size, and money math uses Decimal, never raw float.
Lot sizes always round down, never up.
SL/TP are always placed server-side, at order-send time, never managed only in application logic.
No strategy logic change is ever made silently — every change is dated, justified, and logged in Document 2's Change Log.
No hand-typed/manually-verified numeric table ever enters a specification document — all derived values come from executed script output only.
Trading occurs Monday–Thursday only. No Friday, no Sunday. (Rationale corrected, v1.1 — see Section 3 and Document 2, Section 1: this is a structural fact of broker hours for Friday, and a deliberate risk-management choice for Sunday, not a market-closure fact for the latter.)
All timestamps stored in UTC in the database; all session logic calculated against America/New_York via zoneinfo for automatic DST handling.
Every order action (submit, fill, partial, modify, cancel) is immutably logged — no update/delete permissions on trade history tables.
Any numeric threshold currently based on 12 months of backtest data is provisional until confirmed by forward-test results — this must be explicitly labeled everywhere it appears.
# 9. Escalation Authority — What Requires Sign-Off vs What Doesn't
Never decide alone, always escalate to project owner:

Any change to risk percentages, SL/TP caps, or circuit breaker thresholds
Any change to trading days/hours
Deployment of real capital at any new stage (demo → live, or scaling live capital)
Any legal/compliance-adjacent decision
Decide independently, document the decision:

Code structure, internal architecture, library/tooling choices within the stack defined in Document 3
Bug fixes that restore documented behavior (not ones that quietly change it)
Dashboard visual design choices within the UX principles set in Document 5
# 10. Current Project Status (Summary — full detail lives in Document 6)
Phase: Specification finalization — complete, including a full documentation hardening pass conducted 25 July 2026 across all six documents.
Outstanding blocker: None blocking Phase 1 start. Two minor, non-blocking items remain tracked in Document 6, Section 3: (1) saving a dated screenshot/PDF artifact of the broker's official contract specification for the formal audit trail (the underlying hours/data have already been reviewed and incorporated into Document 2), and (2) confirming which specific broker entity legally holds the owner's account (a 5-minute paperwork check).
Known, accepted timeline impact: Mon–Thu-only trading materially reduces trade frequency; the 6-month/50-trade forward-test target realistically extends to ~9–10 months. This is documented, not hidden.
Next step: Phase 1 (Infrastructure & Data Pipeline Build) — see Document 6 for entry criteria and current blockers (owner-side infra provisioning).
# 11. Change Log
v1.0 (original) — Initial project charter and system overview.

v1.1 (this document, 25 July 2026) — Documentation hardening pass: synchronized this document against the corrected/restored content in Documents 2–6 following a full six-document cross-reference audit. Specific corrections:

Section 2: citation corrected from "Document 2, Section 6" (a section that did not exist as written) to Document 2, Section 9.5 (the restored, exhaustive Forward-Test Pass/Fail/Review criteria).
Section 3: trading-calendar rationale corrected. The original text attributed Friday's exclusion to "early close, fragmented late session" — this was based on incorrectly-converted broker hours. The corrected rationale (Document 2, Section 1) is that Friday trading is a structural impossibility under the broker's actual hours, not a session-fragmentation workaround. Sunday's exclusion rationale corrected from "market is closed" (factually incorrect under the real, corrected hours) to an explicit, owner-confirmed risk-management decision.
Section 4: added a clarifying note that the architecture diagram's "VPS" label is intentionally generic; Document 3 is the authoritative source for the current concrete hosting decision (free-tier, Linux+Wine).
Section 6 and Section 4 diagram: Tier-1 metric count corrected from "50+"/"110+" to the confirmed, recounted 112 total / 60 Tier-1 (Document 5, Section 1).
Section 7 (Glossary): added a new entry for the Hard Fail / Review / Pass verdict terminology introduced in Document 2, Section 9.5.
Section 8, Principle 6: added a clarifying cross-reference to the corrected trading-calendar rationale.
Section 10: status updated to reflect that specification finalization (including the hardening pass) is complete, the Phase 1 blocker list narrowed to two genuinely non-blocking items, and "next document to be written" replaced with "next step: Phase 1," since all six documents now exist and are current.
Added this Section 11 (Change Log), bringing Document 1 in line with the versioning discipline already practiced by Documents 2–5.
Note on the "Document 1, Section 'Part 2'" citation error: this defect was found and corrected in Document 4, Section 3.1 (which cited this document incorrectly) — no corresponding internal error existed in Document 1 itself, so no fix was required here beyond noting it for the record.
End of Document 1 v1.1.

text


---

**Verdict: approved.** This closes out the documentation hardening pass — all six documents are now internally consistent, cross-referenced correctly, and versioned with full Change Log traceability.