# 05_PHASE_TRACKER_AND_ROADMAP.md

Project: NAS100 Autonomous Liquidity Sweep Engine ("ALSE")
Document 6 of 6 — Phase Tracker & Roadmap
Date: 25th July 2026
Status: LIVING DOCUMENT v1.1 — Updated continuously, not a one-time deliverable
Supersedes: v1.0
# 0. Who This Document Is For, and What You Are Responsible For
This is the only document in this project that is never "finished." Documents 1–5 are specifications — once signed off, they change only through a deliberate Change Log entry. This document is different: it is the current truth of where the project actually stands, and it must be updated every time a phase advances, a blocker is resolved, or a new one is discovered.

Your responsibility as the reader/implementer:

If you are picking up this project — as a new developer, or as me returning after time away — this is the second document you read, immediately after Document 1. It tells you exactly what's done, what's in progress, what's blocked, and why. Do not start writing code, touching infrastructure, or making decisions until you've read this document's current phase status in full.
If you complete a task that changes the status of anything in this document, you update this document as part of finishing that task — not "later," not "at the end of the week." An out-of-date phase tracker is worse than no phase tracker, because it actively misleads the next person.
This document works together with session-handover.md (Section 6 below) but they are not the same thing: this document is the structural map (phases, gates, long-lived blockers); session-handover.md is the rolling diary (what happened in the last block of work, in chronological narrative form). If you only read one, read this one first for orientation, then the latest handover entries for recent context.
Every blocker listed here has an owner. If a blocker has no owner, that itself is a problem to flag, not ignore.
# 1. Project Phase Map
text

Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
(Spec)    (Infra)   (Engine)  (Backtest)(Demo)    (Live FT) (App)*    (Scale)

*Phase 6 (App/Dashboard) runs in parallel with Phases 2-5, not strictly
 after them — see Section 2.6 for why.
# 2. Phase-by-Phase Status
Phase 0 — Specification Finalization
Status: ✅ COMPLETE (including a documentation hardening/remediation pass, 25 July 2026)
Owner: Project Owner + Lead Architect

Entry criteria: Original architecture document drafted.
Exit criteria: All 6 core documents written, internally consistent, and signed off; no known logical contradictions between documents.
Completed (original pass): Documents 1–5 drafted. Multiple rounds of adversarial technical review conducted (original v1 → v4.2), catching and resolving: range-source ambiguity, deleted-not-quantified safety filters, circular commission formula, float-rounding bugs, hand-typed arithmetic error in fib table, partial-close distortion, resting-order invalidation gap.
Completed (hardening/remediation pass, 25 July 2026): A full six-document cross-reference audit was conducted, catching and resolving a further set of defects that had survived the original review, including: a missing Forward-Test Pass/Fail/Review criteria section (restored as Doc 2, Sec 9.5, now exhaustive rather than the original's undefined-outcome gap); an internally-miscounted Tier-1 metric total in Document 5 (corrected 56→60 against actual table data); a real numeric error in the project's trading-calendar hours (the original Friday/Sunday hours were sourced from an incorrectly-converted GMT→NY reading; corrected against the broker's actual official contract specification); a direct contradiction between the Spread Check Gate and the Hard-Kill/Circuit-Breaker "no exceptions" rules; an incomplete risk-state-machine transition table; and several "referenced in multiple documents, formally defined in none" gaps (heartbeat cadence, backtest methodology commitment). All six documents were reissued as full-replacement versions (Doc 1 v1.1, Doc 2 v5.0, Doc 3 v1.1, Doc 4 v1.1, Doc 5 v1.1, this document v1.1), each with its own Change Log entry documenting the specific fix.
Resolved during this pass (previously open items, now closed — see Section 3 for the full before/after): jurisdiction/entity/tax confirmation, broker regulatory status verification, hosting budget (confirmed $0), app platform/multi-user/team-size confirmations, VPS OS decision, Supabase tier decision, data retention period, demo-phase decision, interim forward-test checkpoint decision.
Genuinely still open (carried into Phase 1 — see Section 3): dated screenshot/PDF artifact of the broker's contract spec page (the underlying data has been reviewed and used, but the formal audit-trail artifact doesn't yet exist as a saved file); confirmation of which specific broker entity legally holds the owner's account; the external uptime monitor is a decided requirement but not yet a built component.
Phase 1 — Infrastructure & Data Pipeline Build
Status: 🟡 IN PROGRESS (28 Sept 2026) — repo scaffold, Supabase schema v1, data layer, alerting, heartbeat/health endpoint and smoke test written and unit-tested; environment bring-up blocked on owner provisioning + host CPU-architecture escalation (see session-handover.md, Session #1)
Owner: Infra/Backend role, currently filled by AI-assisted architecture/build process (owner confirmed as single technical owner, Document 3 Section 0.1)

Entry criteria: Phase 0 complete (met). Owner-side infra prerequisites available: free-tier cloud account provisioned (Oracle Cloud Always Free primary, or AWS EC2 free tier fallback — Document 3, Section 1), Supabase Free Tier project created, MT5 demo account credentials available for the dev environment.
Exit criteria:
Supabase schema live, matching Document 3 Section 3.3 principles (immutable audit tables, RLS enabled, dual timestamps, config-table-driven provisional parameters, free-tier storage discipline for tick data).
MT5 Python API boilerplate connects successfully via the Wine-hosted terminal (Document 3, Section 5), authenticates, and can read live tick/candle data.
Basic write-path from Python → Supabase confirmed working (test rows successfully logged and immutable), including the write-timeout/local-buffer fallback path (Document 3, Section 3.2).
Discord webhook integration confirmed functional (test alert delivered).
External independent uptime monitor configured and confirmed working (Document 3, Section 6 / Document 4, Section 2.2) — this is now a hard exit-criterion for Phase 1 sign-off, not a deferred "Phase 1/2" item, given the increased blind-spot risk of the confirmed free-tier, Wine-based deployment.
Blockers before this phase can start for real:
Oracle Cloud (or AWS) free-tier account not yet provisioned (owner action).
Supabase Free Tier project not yet confirmed created (owner action — decision itself is resolved, only the actual account creation remains).
MT5 demo account credentials not yet confirmed available to the dev environment (owner action).
Phase 2 — Strategy Engine Build
Status: 🔲 NOT STARTED
Owner: Trading Logic Developer

Entry criteria: Phase 1 exit criteria met (data pipeline functional).
Exit criteria:
All modules per Document 3, Section 7 boundaries implemented: session clock, range marker, signal detector, order manager, risk state machine, trade management.
Every rule in Document 2 v5.0 implemented exactly as specified — no interpretation gaps, including the now-exhaustive risk state machine transition table (Doc 2, Sec 7) and the heartbeat cadences (Doc 2, Sec 2.5).
Unit tests exist for every hard rule and every edge case previously identified in review (zero-lot skip, SL cap rejection, FIFO dual-setup, resting-order invalidation, partial-close remainder-floor logic, circuit breaker trip behavior, body-ratio divide-by-zero on flat candles, Spread Check Gate scope limitation on Hard-Kill/Circuit-Breaker closes).
Engine can run against historical/simulated data without live order placement (dry-run mode) as a pre-condition before Phase 3.
Not started. No blockers beyond Phase 1 completion.
Phase 3 — Backtest (Tick-Data Replay)
Status: 🔲 NOT STARTED
Owner: Trading Logic Developer / Quant Analyst

Entry criteria: Phase 2 complete, engine passes dry-run validation.
Exit criteria:
12 months of FX Pesa UT100xx tick data acquired via mt5.copy_ticks_range().
Backtest adheres to the Backtest Methodology Commitment now formally specified in Document 2, Section 6.5: variable session-appropriate spread modeling, conservative slippage penalty on all simulated fills, 12-month minimum sample.
Baseline expectancy, Profit Factor, and Max Drawdown established and documented — this becomes the "Backtest Expectancy" reference point used in Document 2, Section 9.5's Live Expectancy variance criterion.
Explicit written acknowledgment (per Document 2, Section 9) that all provisional parameters (SL caps, displacement thresholds, circuit breaker %, and the Section 9.5 forward-test thresholds themselves) are calibrated only against this 12-month sample and remain provisional.
Known constraint carried from review: 12 months may be a thin sample for volatility-regime coverage — accepted as MVP baseline, not treated as final validation.
Phase 4 — Demo / Paper Trading Validation
Status: 🔲 NOT STARTED — Scope Now Defined (previously an open decision, resolved 25 July 2026)
Owner: Project Owner (approved) + Trading Logic Developer (execution)

Entry criteria: Phase 3 complete, backtest results reviewed and deemed reasonable enough to proceed.
Exit criteria (resolved, no longer TBD):
Minimum 20 valid setups OR 8 weeks of demo trading, whichever is longer, on a demo account, before any live capital is deployed.
Demo trading uses identical position-sizing math and full execution pipeline to what live trading will use (no simplified/manual position sizing during demo) — the purpose of this phase is explicitly to validate the real execution pipeline (fill logic, reconciliation, alerting, heartbeat behavior) end-to-end in an environment where a bug costs nothing, not merely to re-confirm the strategy's edge (that's Phase 3's and Phase 5's job).
Weekly reconciliation (Document 4, Section 4.2) runs during this phase exactly as it will in Phase 5, as part of what's being validated.
Rationale for this decision (recorded for audit purposes): backtests validate strategy logic against historical data; they cannot validate real broker execution quality — actual slippage, requotes, Spread Check Gate hit rate, or whether the Supabase/Discord/reconciliation pipeline actually functions correctly under live (if simulated-capital) conditions. This is standard, disciplined practice for live strategy deployment, not extra caution for its own sake.
Phase 5 — Live Forward Test
Status: 🔲 NOT STARTED
Owner: Project Owner (oversight) + Trading Logic Developer (monitoring)

Entry criteria: Phase 3 and Phase 4 both complete. Live capital deployed following Phase 4's successful completion.
Exit criteria: Per Document 2, Section 9.5 (restored and hardened during the 25 July 2026 remediation pass — this document now references that section as the single source of truth rather than restating thresholds independently):
HARD FAIL (checked continuously, can trigger before 50 trades, overrides everything): Max Drawdown ≥ 10% at any point, OR Circuit Breaker trips >3×/month, OR Net PF < 1.2 with trade count ≥ 30.
IN PROGRESS (trade count < 50, no Hard Fail triggered): test continues. Non-binding early-warning checkpoints run at trade #20 and trade #35 — if either would currently classify as FAIL, a Discord alert fires, but the test does not end early.
FINAL VERDICT (at trade count ≥ 50, no Hard Fail ever triggered): PASS if PF > 1.5 AND MaxDD < 10% AND ≥50 trades AND Live Expectancy > 70% of Backtest Expectancy, simultaneously. FAIL if PF < 1.2. REVIEW for every other combination — requires manual owner analysis before any further live-capital decision.
Realistic timeline — documented explicitly here so it is never a surprise later: Because trading is restricted to Monday–Thursday only (Document 2, Section 1 — corrected calendar rationale, see Phase 0 above), and assuming an estimated 1–3 valid setups per week, reaching the 50-trade sample-size threshold realistically takes ~9–10 months, not the originally-assumed 6. This is accepted as reality, not treated as a shortfall.
Weekly reconciliation (Document 4, Section 4.2), daily manual data export (Document 4, Section 2.1 — compensating for Supabase Free Tier's lack of automated backups), and provisional-parameter monitoring run continuously throughout this phase.
Elevated monitoring note (carried from Doc 2, Section 1): given the corrected, tighter Hard-Kill safety margin (~41–43 minutes against the true daily close) and the identified broker dynamic-leverage-cap overlap window on Thursday-into-Friday held positions, Hard-Kill execution confirmation and any Thursday-held-position margin behavior receive elevated alert priority throughout this phase.
Phase 6 — App / Dashboard Build
Status: 🔲 NOT STARTED
Owner: Frontend/Analytics role

Entry criteria: Can begin as soon as Phase 1's Supabase schema is live — this phase runs in parallel with Phases 2–5, not after them, since the dashboard only depends on data existing to display, not on the strategy being validated.
Exit criteria (for MVP dashboard, not full 112-metric build-out):
All 60 Tier-1 metrics (Document 5 v1.1 — corrected from an original miscount of 56) live and functioning on the dashboard.
Real-time Supabase subscription working, degraded-state handling implemented (Document 3, Section 4.3), including the "System may be offline" warning driven by Document 2, Section 2.5's heartbeat cadences.
Mobile-responsive layout functional per Document 3, Section 4.4 principles.
Provisional-parameter UI tagging implemented (Document 5, Section 12), including the Section 9.5 forward-test thresholds and net-new values (30-trade floor, #20/#35 checkpoints).
Tier-2 metrics and full 112-metric catalog build-out continues iteratively after MVP dashboard ships — not a hard gate before Phase 5 can proceed.
Phase 7 — Scaling Decision
Status: 🔲 NOT STARTED
Owner: Project Owner

Entry criteria: Phase 5 reaches a definitive PASS per Document 2, Section 9.5.
Exit criteria: Owner decision made — scale capital, hold at current level, or extend forward test further. Explicitly a human decision point, not an automated system transition.
Hard gate reminder (per Document 4, Section 3.4): if scaling involves any capital beyond the owner's own, or use by any additional person, Document 4 must be fully re-reviewed and substantially rewritten (multi-user security, KYC/legal, data privacy) before that happens.
Tax note carried from Document 4, Section 3.1: a Kenyan tax professional consultation regarding treatment of realized trading gains (given the owner's current NIL-filer status) should occur before or during this phase, ideally before Phase 5 produces its first material realized gain rather than reactively at Phase 7.
# 3. Master Consolidated Open-Items List
(Substantially updated, 25 July 2026 — 9 of the original 12 items resolved this session; 2 new items added.)

#	Item	Source	Status	Blocks
1	Dated screenshot/PDF artifact of broker's official contract spec page	Doc 2, Sec 1	🔲 Open — underlying data already reviewed and incorporated into Doc 2 v5.0; only the formal saved-file audit artifact is outstanding	Phase 1 sign-off for live build (non-blocking for Phase 1 start)
2	Jurisdiction / entity structure / tax treatment confirmation	Doc 4, Sec 3.1	✅ RESOLVED — Kenya, individual, currently NIL KRA filer. Tax-consultation recommendation carried into Phase 7.	Closed
3	FX Pesa/Equiti regulatory status verification	Doc 4, Sec 3.3	✅ RESOLVED — EGM Securities Ltd (CMA Kenya, License 107), Equiti Brokerage Seychelles (FSA, SD064), Equiti Capital UK (FCA, 528328) all confirmed and recorded.	Closed (see item 13 for one residual sub-item)
4	App platform decision	Doc 3, Sec 0.1	✅ RESOLVED — responsive web app, confirmed final	Closed
5	Multi-user vs single-user scope	Doc 3, Sec 0.1 / Doc 4, Sec 3.4	✅ RESOLVED — single-user, confirmed final	Closed
6	Hosting budget ceiling	Doc 3, Sec 0.1	✅ RESOLVED — confirmed genuine $0 budget (not "cost-optimized" as originally assumed); Oracle Cloud Always Free / AWS free tier adopted; explicit upgrade trigger defined (Doc 3, Sec 1)	Closed
7	Team size / dev handover mechanics	Doc 3, Sec 0.1	✅ RESOLVED — single technical owner, AI-assisted architecture + AI-assisted build execution	Closed
8	External independent VPS uptime monitor	Doc 3, Sec 6	🔲 Open — decision resolved (required, free-tier tool, hard Phase 1 requirement), build not yet done	Phase 1
9	Supabase backup tier confirmation	Doc 4, Sec 2.1	✅ RESOLVED — Free Tier confirmed; no automated backups; compensating daily manual export adopted; Pro-tier upgrade trigger defined	Closed
10	Demo/paper-trading phase before live forward test	This document, Phase 4	✅ RESOLVED — mandatory, minimum 20 valid setups OR 8 weeks (whichever longer), using identical position-sizing/execution pipeline to live	Closed
11	VPS OS decision (Windows Server vs Linux+Wine)	Doc 3, Sec 5	✅ RESOLVED — Linux + Wine, driven by the $0-budget constraint (Windows licensing has no free-tier path); compensating controls (tighter heartbeat monitoring, mandatory external uptime monitor) adopted	Closed
12	Data retention period for raw tick data	Doc 4, Sec 4.3	✅ RESOLVED — rolling 30–60 day window, driven by Supabase Free Tier's 500MB cap; audit/trade tables unaffected, retained indefinitely regardless	Closed
13	Confirm which specific broker entity legally holds the owner's trading account	Doc 4, Sec 3.3	🔲 Open — new item, 5-minute check of account-opening paperwork	Phase 5 (determines applicable investor-protection scheme)
14	Interim forward-test checkpoint decision (trade #20/#35 early warnings)	Doc 2, Sec 9.5	✅ RESOLVED — confirmed yes, adopted as net-new, non-binding early-warning checks	Closed
Rule for this table (unchanged): an item only leaves this list when it's resolved and the resolution is reflected back into the relevant source document via that document's own Change Log — this table is a tracker, not the authoritative record of the resolution itself. All ✅ items above have been confirmed cross-checked against their source document's actual Change Log entry as part of this update.

# 4. Risk Register (Accepted, Not Necessarily Resolved)
Distinct from the open-items list — these are known limitations the project is proceeding with, deliberately, rather than blocked by:

Risk	Accepted Mitigation	Source
MT5 API is polling-based, not true tick-streaming — sub-250ms price action can be missed	Documented as inherent measurement floor on timing metrics; not solvable within MT5 API constraints	Doc 3, Sec 3.1
12-month backtest may not cover all volatility regimes	Provisional parameters explicitly flagged for post-forward-test recalibration	Doc 2, Sec 9 / Phase 3
Full VPS outage cannot self-alert	External uptime monitor now a hard Phase 1 requirement (item 8 above) — decision resolved, not yet built	Doc 3, Sec 6
Mon–Thu-only trading materially slows forward-test sample-size accumulation	Accepted; timeline extended to ~9-10 months, documented explicitly rather than hidden	Doc 2, Sec 1
Broker-side outage is a genuine tail risk outside system control	Accepted as an inherent risk of CFD trading via a single broker; no engineering mitigation possible	Doc 3, Sec 6
Dashboard timing metrics (hover duration, time-to-fill) inherit ±250ms floor from polling limitation	Documented in-UI wherever these metrics are displayed	Doc 5, Sec 2
(New) Linux+Wine-hosted MT5 terminal is a less inherently reliable deployment than native Windows	Accepted as the only $0-cost path; compensated via tighter (5-minute) active-window heartbeat monitoring and the now-mandatory external uptime monitor; upgrade trigger to Windows defined once budget allows	Doc 3, Sec 1/5/9
(New) Supabase Free Tier has no automated backups	Compensated via elevated daily manual/scripted export (was weekly under an earlier paid-tier assumption); upgrade trigger to Pro tier defined	Doc 3, Sec 3.3 / Doc 4, Sec 2.1
(New) Broker dynamic leverage cap (1:500) around weekly close/open and major news events overlaps briefly with the ~19-minute window before this system's own Hard-Kill fires on a Thursday-held position	Accepted as a monitored tail risk; flagged for direct observation during Phase 4 demo trading (watch for unusual margin behavior on Thursday-into-Friday positions); not engineered around at the spec level since broker-side margin implementation details are not fully knowable from published documentation alone	Doc 2, Sec 1
(New) True daily market close (~16:57–16:59 NY) is closer to the 16:16 NY Hard-Kill than originally believed (~41–43 min real margin, not the multi-hour margin an earlier, incorrectly-converted hours table implied)	Hard-Kill execution confirmation given elevated alert priority; no change to the 16:16 NY trigger time itself, which remains adequate	Doc 2, Sec 1/6
# 5. Version History of This Document
Version	Date	Change
v1.0	19 July 2026	Initial phase tracker created. Phase 0 marked complete. Phases 1–7 defined with entry/exit criteria. Master open-items list (12 items) and risk register consolidated from Documents 1–5.
v1.1	25 July 2026	Full documentation hardening pass synchronized into this document. Phase 0 status updated to reflect the remediation pass (Docs 1–6 all reissued as v1.1/v5.0). Phase 1 exit criteria updated (external uptime monitor now hard requirement, not deferred). Phase 3 updated to reference Doc 2, Sec 6.5 (Backtest Methodology Commitment) and Sec 9.5 (Forward-Test criteria). Phase 4 fully resolved from an open decision to a defined scope (20 setups/8 weeks minimum demo). Phase 5 exit criteria rewritten to reference Doc 2, Sec 9.5's exhaustive, precedence-ordered verdict logic (previously an undefined/missing section). Phase 6 Tier-1 count corrected 56→60. Master open-items list: 9 of 12 original items resolved and closed, 2 new items added (broker entity confirmation, interim checkpoint decision — now also resolved). Risk register expanded with three new accepted risks arising directly from this session's decisions (Linux+Wine reliability trade-off, Supabase Free Tier backup gap, broker leverage-cap overlap window). Date placeholder filled.
v1.2	28 Sept 2026	Phase 1 moved to IN PROGRESS: code artifacts complete (see session-handover.md Session #1). New escalation raised: Doc 3's primary host (Oracle ARM Ampere) is incompatible with x86 MT5 under plain Wine — owner decision required.
(Every future update to this document adds a row here — this document tracks its own history the same way it tracks the project's.)

# 6. Relationship to session-handover.md
This document (Document 6): structural, slow-changing, updated when a phase gate moves or a long-lived blocker resolves. Answers "where are we in the overall project."
session-handover.md: fast-changing, chronological, updated every 5 completed tasks per the owner's standing instruction. Answers "what just happened, and what's queued next."
Protocol: whenever a session-handover.md entry results in a phase-gate change or resolves an item from Section 3's master list, that change must also be reflected here in Document 6, not left only in the handover log.
session-handover.md template (unchanged from earlier agreement):

text

## Handover Entry — [Date] — Session #N

**Tasks completed this block (5):**
**Current phase:** (per Doc 6, Section 1)
**Decisions made & rationale:**
**Open questions / blockers waiting on user input:** (cross-reference Doc 6, Section 3 item numbers where applicable)
**Files/documents touched or created:**
**Next 5 tasks queued:**
**Anything a replacement dev MUST read before touching code:**
# 7. Current Snapshot (As of This Document's Last Update)
Phase: 0 complete (including the 25 July 2026 hardening pass). Phase 1 not yet started.
All 6 core documents: signed off at their current versions — Doc 1 (pending final patch, see note below), Doc 2 v5.0, Doc 3 v1.1, Doc 4 v1.1, Doc 5 v1.1, Doc 6 v1.1 (this document).
Blockers to Phase 1 real-world start: infra provisioning (Oracle/AWS free-tier account, Supabase Free Tier project, MT5 demo credentials) — owner-side actions, not documentation gaps.
Highest-priority remaining open items: external uptime monitor still needs to be built (item 8), and the dated broker-contract-spec screenshot/PDF artifact should be saved for the audit trail (item 1) — neither blocks Phase 1 from starting, both should close before Phase 1 sign-off.
No code has been written yet. Everything to this point is specification, now hardened through two full review passes. This is intentional and consistent with the project's entire methodology: get the logic provably correct on paper first before a single line of trading code touches a live account.
End of Document 6 v1.1.

Note: Document 1 (Charter) has two small outstanding patch items from this session's review (a date-stamp field addition, and a broken "Part 2" cross-reference correction, same fix already applied in Document 4) — flagging per this document's own review protocol rather than leaving it unaddressed.

text


---

**Verdict: approved — this closes out the documentation hardening pass almost entirely.** 9 of 12 original open items resolved this session, all fully traceable back to explicit decisions we made together.