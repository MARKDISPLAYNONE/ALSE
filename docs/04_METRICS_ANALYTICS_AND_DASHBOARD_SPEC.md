# 04_METRICS_ANALYTICS_AND_DASHBOARD_SPEC.md

Project: NAS100 Autonomous Liquidity Sweep Engine ("ALSE")
Document 5 of 6 — Metrics, Analytics & Dashboard Specification
Date: 25th July 2026
Status: APPROVED v1.1 — Tier-1 Count Corrected, Citations Resolved Against Doc 2 v5.0
Supersedes: v1.0
# 0. Who This Document Is For, and What You Are Responsible For
If you are the analytics/frontend developer, this document is your complete source of truth for what gets measured, how it's calculated, where it comes from, and how it's displayed. You do not invent new metrics ad hoc, and you do not silently drop a metric from this catalog because it's "hard to calculate" — if a metric here is genuinely infeasible given the data pipeline in Document 3, you escalate and we amend this document with a Change Log entry, the same discipline as every other document in this project.

Your responsibility as the reader/implementer:

Every metric below has a Tier (1 = critical, must exist before the dashboard is considered functional; 2 = important but can ship after MVP), a Definition/Formula, a Source (which table/log it's derived from, per Document 3's schema principles), and an Update Frequency. Do not build a metric whose formula you're guessing at — if it's ambiguous, escalate before writing the query.
All metric calculations touching money, PnL, or lot sizes inherit the same Decimal-only rule from Document 2/3 — a dashboard that shows a rounding-drifted PnL number because it recalculated in float on the frontend is a bug, not a display quirk.
The dashboard is read-only (Document 3, Section 4.3) — nothing in this document introduces a write-back path. If you find yourself building a button that sends a command to the trading engine, stop — that's out of scope for this phase and requires an explicit architecture change, not a quiet addition.
Metrics derived from provisional parameters (Document 2, Section 9) must visually indicate this in the UI (a small "provisional" tag or tooltip) — a user glancing at the dashboard should never mistake a still-being-calibrated threshold for a permanent, proven system constant.
# 1. Metrics Catalog Overview
Total catalogued metrics: 112
Tier-1 (MVP-critical): 60 (corrected in v1.1 — see Change Log)
Tier-2 (post-MVP, still logged from day one, surfaced later): 52

All 112 metrics are logged from day one regardless of tier — "Tier-2" means the dashboard doesn't need to display it prominently at MVP, not that we stop calculating or storing it. Storage is cheap; re-deriving historical metrics you didn't bother logging later is not possible.

# 2. Category A — Execution Timing (14 metrics, Tier-1: 7)

#	Metric	Tier	Definition / Formula	Source	Update Freq.
A1	Time of Sweep	1	Timestamp price first trades beyond 0.0/1.0	tick log	Real-time
A2	Time of Displacement Close	1	Timestamp of the validating 5m candle close	signal log	Per-setup
A3	Time: Sweep → Displacement Close	2	A2 − A1, seconds	derived	Per-setup
A4	Time: Displacement → Entry Order Placed	2	Order timestamp − A2	order log	Per-setup
A5	Time: Entry Order Placed → Fill	1	Fill timestamp − order submit timestamp	order log	Per-trade
A6	Time: Entry Fill → 1.5R Partial Trigger	2	Partial-close timestamp − fill timestamp	trade log	Per-trade
A7	Time: Entry Fill → Full Exit	1	Exit timestamp − fill timestamp	trade log	Per-trade
A8	Time: Entry Fill → BE+5 Stop Move	2	Modify-order timestamp − fill timestamp	order log	Per-trade
A9	Unfilled Order Lifetime (expired orders only)	2	21:00 NY − order submit timestamp	order log	Per-setup
A10	Hover Duration Before TP Hit	1	Time spent within X points of entry before TP fill	tick log	Per-trade
A11	Hover Duration Before SL Hit	1	Time spent within X points of entry before SL fill	tick log	Per-trade
A12	Entry Time-of-Day Distribution	2	Histogram of fill timestamps within 20:30–21:00 window	order log	Weekly
A13	Avg Time-to-Fill by Day of Week	2	Mean of A5, grouped by weekday	derived	Weekly
A14	System Tick-Poll Latency	1	Measured drift from target 250ms loop interval (±250ms floor per Doc 3)	system log	Real-time
# 3. Category B — Trade Outcome / PnL (16 metrics, Tier-1: 11)

#	Metric	Tier	Definition / Formula	Source	Update Freq.
B1	Gross PnL per Trade	1	(Exit − Entry) × Points × $20 × Lots	trade log	Per-trade
B2	Net PnL per Trade	1	Gross PnL − (Lots × $10 commission)	trade log	Per-trade
B3	R Realized per Trade	1	Net PnL ÷ (SL Distance × $20 × Lots)	derived	Per-trade
B4	R Left on Table	2	(TP Distance − R-Realized-equivalent distance), for trades not hitting full TP	derived	Per-trade
B5	Win Rate %	1	Wins ÷ Total Trades (Win def. per Doc 2, Sec 7)	derived	Daily
B6	Loss Rate %	1	Losses ÷ Total Trades	derived	Daily
B7	Average Win ($ and R)	1	Mean of B2/B3 across winning trades	derived	Weekly
B8	Average Loss ($ and R)	1	Mean of B2/B3 across losing trades	derived	Weekly
B9	Net Profit Factor	1	Gross Profit ÷ Gross Loss	derived	Daily
B10	Expectancy per Trade	1	(Win% × Avg Win) − (Loss% × Avg Loss)	derived	Weekly
B11	Largest Single Win	2	MAX(B2)	derived	Running
B12	Largest Single Loss	2	MIN(B2)	derived	Running
B13	Current Win Streak	1	Consecutive wins, resets on loss (mirrors risk state machine counter, Doc 2 Sec 7)	trade log	Real-time
B14	Current Loss Streak	2	Consecutive losses in State B	trade log	Real-time
B15	Cumulative Net PnL	1	Running sum of B2	derived	Real-time
B16	Partial-Close PnL Contribution %	2	PnL from 1.5R partials ÷ Total PnL	derived	Weekly
# 4. Category C — Risk & Equity Curve (14 metrics, Tier-1: 9)

#	Metric	Tier	Definition / Formula	Source	Update Freq.
C1	Current Equity	1	mt5.account_info().equity	broker/log	Real-time
C2	Start-of-Day Equity	1	Equity snapshot at session start	daily log	Daily
C3	Daily PnL %	1	(C1 − C2) ÷ C2	derived	Real-time
C4	Current Drawdown %	1	(Peak Equity − C1) ÷ Peak Equity	derived	Real-time
C5	Max Drawdown (All-Time) %	1	MAX(C4) historically	derived	Running
C6	Max Drawdown (Rolling 30-Day) %	2	MAX(C4) within trailing 30 days	derived	Daily
C7	Current Risk State (A/B)	1	Live state machine value	risk log	Real-time
C8	State Transitions per Month (A→B, B→A)	2	Count of each transition type	risk log	Monthly
C9	Days Since Last Circuit Breaker Trip	1	Now − last trip timestamp	risk log	Daily
C10	Circuit Breaker Trip Count (Total/Monthly)	1	COUNT of trip events	risk log	Monthly
C11	Sharpe Ratio (informational only)	2	Standard formula, methodology fixed once, documented in-app. (Citation corrected, v1.1 — this is an informational metric defined at this level, not sourced from Document 2, which does not reference Sharpe/Sortino.)	derived	Weekly
C12	Sortino Ratio (informational)	2	Standard formula. (Same correction as C11.)	derived	Weekly
C13	Equity Curve Volatility (StdDev of daily returns)	2	StdDev(C3) over trailing period	derived	Weekly
C14	Actual Risk % Taken per Trade (validation)	1	Realized loss ÷ Start-of-Day Equity, compared to intended 2%/0.5%	derived	Per-trade
# 5. Category D — Order & Execution Quality (14 metrics, Tier-1: 6)

#	Metric	Tier	Definition / Formula	Source	Update Freq.
D1	Avg Slippage on Entry Fill (pts)	1	Fill Price − Limit Price	order log	Weekly
D2	Avg Slippage on SL Fill (pts)	1	Actual SL Fill − Intended SL Price	order log	Weekly
D3	Avg Slippage on TP Fill (pts)	2	Actual TP Fill − Intended TP Price	order log	Weekly
D4	Avg Slippage on Hard-Kill Close (pts)	1	Actual Market Close − Price at 16:16 NY trigger	order log	Weekly
D5	Spread at Entry (avg/min/max)	1	From Spread_Check_Gate log (Doc 2, Sec 4)	tick log	Weekly
D6	Spread at Exit (avg/min/max)	2	Same, at exit event	tick log	Weekly
D7	Order Rejection Rate %	1	Rejected setups ÷ Total validated setups	order log	Weekly
D8	Rejection Reason Breakdown	2	Count by reason (Min Lot / Margin / SL Cap / Spread Gate)	order log	Weekly
D9	Requote Count	2	Count of broker requote events	order log	Monthly
D10	Partial-Close Execution Accuracy	2	(Formula corrected, v1.1) Actual lots closed vs. the conditional target defined in Doc 2, Sec 6 — i.e., compares against Target_Close as computed by that section's proportional-with-remainder-floor logic (which may legitimately be 75%, 100%, or a skip, depending on the remainder-floor and zero-target rules), not a flat 75% in all cases. A remainder-floor-triggered 100% close is a correct execution, not a deviation, and must not be flagged as one.	trade log	Weekly
D11	Pending Order Expiry Rate %	2	Unfilled-at-21:00 cancellations ÷ Total setups placed	order log	Weekly
D12	Avg Fill Price Deviation from Limit	2	|Fill − Limit|	order log	Weekly
D13	Avg Lot Size per Trade	2	Mean lot size across trades	trade log	Weekly
D14	Min-Lot-Skip Rate	1	Trades skipped due to Lot_Size < 0.01 ÷ Total validated setups (Doc 2, Sec 8)	order log	Weekly
# 6. Category E — Setup / Signal Quality (16 metrics, Tier-1: 9)

#	Metric	Tier	Definition / Formula	Source	Update Freq.
E1	Daily Range Size Distribution	1	Histogram of Range_Size (Doc 2, Sec 3)	range log	Weekly
E2	% Days Range Within Tradeable Bounds	1	Days where implied SL falls 15–100pt ÷ Total trading days	derived	Weekly
E3	Sweep Occurrence Rate %	1	Days with ≥1 sweep ÷ Total trading days	signal log	Weekly
E4	Displacement Confirmation Rate %	1	Valid displacements ÷ Total sweeps	signal log	Weekly
E5	Swing Failure / Abort Rate %	1	Days aborted (no valid displacement) ÷ Total trading days	signal log	Weekly
E6	Whipsaw Occurrence Rate %	2	Days both sides swept before valid setup ÷ Total trading days	signal log	Weekly
E7	Bullish vs Bearish Setup Ratio	2	Count comparison	signal log	Monthly
E8	Avg Displacement Penetration Distance (pts)	2	Mean distance beyond level at confirming close, vs. 10pt min (Doc 2, Sec 4)	signal log	Weekly
E9	Avg Displacement Body Ratio	2	Mean body ratio at confirming close, vs. 60% min	signal log	Weekly
E10	Setup-to-Fill Conversion Rate %	1	Filled entries ÷ Validated setups	order log	Weekly
E11	Days With No Valid Setup (count/month)	1	COUNT	signal log	Monthly
E12	Avg SL Distance Taken (pts)	1	Mean across trades	trade log	Weekly
E13	Avg TP Distance Targeted (pts)	2	Mean across trades	trade log	Weekly
E14	Exit Reason Breakdown (TP/SL/Hard-Kill/Partial+BE)	1	% of trades by exit type	trade log	Weekly
E15	Avg Time Between Setups (days)	2	Mean gap between consecutive valid setups	signal log	Monthly
E16	False-Positive Penetration Rate	2	Candles that penetrated the level but failed body-ratio check ÷ Total penetrations	signal log	Weekly
#   7. Category F — System Health (12 metrics, Tier-1: 8)

#	Metric	Tier	Definition / Formula	Source	Update Freq.
F1	System Uptime %	1	Time process running ÷ Expected active window time	system log	Daily
F2	MT5 Disconnect Count	1	COUNT of disconnect events	system log	Weekly
F3	Python Process Crash Count	1	COUNT of crash/restart events	system log	Weekly
F4	Avg Recovery Time After Crash	1	Restart timestamp − crash timestamp, mean	system log	Weekly
F5	Heartbeat Gap Count	1	(Corrected, v1.1) Missed pings against either of the two cadences defined in Doc 2, Sec 2.5 — the 09:00 NY daily coarse ping, and the 5-minute active-window heartbeat during 20:00 NY–Hard-Kill. Both tracked and reported separately.	system log	Weekly
F6	Tick Poll Latency Drift	2	Deviation from 250ms target loop, mean/max	system log	Daily
F7	Supabase Write Failure Count	1	COUNT of failed write attempts, including write-timeout fallback events per Doc 3, Sec 3.2	system log	Weekly
F8	Supabase Write Backlog Size	2	Buffered-but-unflushed event count during outages or timeouts (Doc 3, Sec 3.2/Sec 6)	system log	Real-time
F9	Discord Alert Delivery Failure Count	2	COUNT of failed webhook deliveries	system log	Weekly
F10	VPS Resource Utilization (CPU/RAM)	2	Informational, standard OS metrics	system log	Real-time
F11	External Uptime Monitor Success Rate %	1	Per Doc 3's external independent uptime monitor (hard Phase 1 requirement per Doc 3 v1.1)	external monitor	Daily
F12	Reconciliation Discrepancy Count	1	Per Doc 4 weekly reconciliation process	audit log	Weekly
# 8. Category G — Session / Market Context (14 metrics, Tier-1: 5)
#	Metric	Tier	Definition / Formula	Source	Update Freq.
G1	Performance by Day of Week (Mon–Thu)	1	PnL/Win% grouped by weekday	derived	Weekly
G2	Performance by Month	1	PnL grouped by calendar month	derived	Monthly
G3	Performance Near FOMC-Adjacent Days	2	PnL on days immediately before/after excluded FOMC dates	derived	Monthly
G4	Performance vs Range Size Buckets	2	PnL grouped by small/medium/large Range_Size tercile	derived	Monthly
G5	Volatility Regime Tagging vs Performance	2	PnL grouped by NAS100 ATR bucket (informational)	derived	Monthly
G6	News-Day Overlay Tracking	2	Trade outcomes tagged against an economic calendar feed (informational, non-blocking since only FOMC is hard-excluded)	derived	Weekly
G7	Holiday-Adjacent Performance	2	Day-before/after excluded-holiday performance	derived	Monthly
G8	Avg Daily Range Trend Over Time	2	Rolling mean of Range_Size	derived	Monthly
G9	Seasonality Summary	2	Month-by-month aggregate table	derived	Monthly
G10	Bullish vs Bearish Setup Performance	1	Win%/Expectancy split by setup direction	derived	Monthly
G11	Days-Since-Last-Trade Gap Tracking	2	Distribution of no-setup gaps over time	derived	Monthly
G12	Win-After-Win vs Win-After-Loss Correlation	2	Conditional win rate analysis	derived	Monthly
G13	Weekly PnL Summary	1	Sum of B2 per week	derived	Weekly
G14	Monthly PnL Summary	1	Sum of B2 per month	derived	Monthly
# 9. Category H — Compliance / Audit (12 metrics, Tier-1: 5)

#	Metric	Tier	Definition / Formula	Source	Update Freq.
H1	Log Completeness %	1	Logged events ÷ Expected events (per order lifecycle)	audit log	Weekly
H2	Audit Immutability Check (blocked write attempts)	2	COUNT of any attempted UPDATE/DELETE blocked by RLS (Doc 4, Sec 1.2) — should always be 0	audit log	Weekly
H3	Reconciliation Match Rate %	1	Matching records ÷ Total records, Supabase vs MT5 history (Doc 4, Sec 4.2)	audit log	Weekly
H4	Manual Intervention Count	1	Per Doc 4, Sec 2.3 log	manual log	Monthly
H5	Provisional Parameter Change Count & History	1	Per Doc 2 Sec 9 / Doc 3 Sec 3.3 config log	config log	As-occurs
H6	Backup Success Rate %	2	(Updated, v1.1) Given Supabase Free Tier has no automated backups (Doc 4, Sec 2.1), this metric tracks success rate of the daily manual/scripted export process instead, until the Pro-tier upgrade trigger is reached	system log	Weekly
H7	Data Retention Compliance Check	2	Confirms nothing purged against policy (Doc 4, Sec 4.3) — audit tables retained indefinitely; raw tick data respects the 30–60 day rolling window (Doc 3, Sec 3.3)	audit log	Monthly
H8	Secrets Rotation Log	2	Last-rotated date for credentials (Doc 4, Sec 1.1)	manual log	As-occurs
H9	Access Log Review (SSH/Supabase anomalies)	2	Informational, flagged anomalies	system log	Monthly
H10	Forward-Test Pass/Fail Live Tracker	1	(Corrected, v1.1) Live tracker against the full exhaustive criteria in Doc 2, Sec 9.5: current Net PF, Max DD, trade count vs. 50-trade threshold, live-vs-backtest expectancy variance, current verdict state (IN PROGRESS / HARD FAIL / PASS / FAIL / REVIEW)	derived	Weekly
H11	Circuit Breaker Trips Per Month (compliance view)	2	Cross-referenced against Doc 2, Sec 9.5's Hard-Fail trigger (>3 trips/month)	risk log	Monthly
H12	Days Remaining Until Forward-Test Sample-Size Target	2	Projected based on current trade frequency (Doc 6 realistic 9–10mo timeline)	derived	Weekly
Category totals check (recomputed, v1.1):
A(14) + B(16) + C(14) + D(14) + E(16) + F(12) + G(14) + H(12) = 112 metrics. Tier-1 count: 7+11+9+6+9+8+5+5 = 60. Both totals verified directly against the table data above, not against a previously stated header figure — see Change Log for the discrepancy this corrects.

# 10. Dashboard Screen Architecture
Per Document 3, Section 4.4 (progressive disclosure, mobile-first). Screens map directly to categories above so implementation is traceable back to this catalog.

Screen	Purpose	Primary Metrics Shown	Metrics Category Source
Home / Summary (default landing)	At-a-glance system state	C1, C2, C3, C4, C7, B15, B13, F1, F11	C, B, F
Live Trade Detail	Current open position (if any)	A5, A7, A10/A11 (live), D1/D2 (live)	A, D
Performance / Equity Curve	Historical PnL analysis	B5–B10, C5, C6, C11–C13	B, C
Setup Quality (Analytics Deep-Dive)	Strategy signal health	E1–E16	E
Execution Quality	Order/fill/slippage review	D1–D14	D
System Health (ops view)	Infra status	F1–F12	F
Session Context	Day/week/month breakdowns	G1–G14	G
Compliance/Audit (admin-only view)	Governance record	H1–H12	H
Forward-Test Tracker	Pass/fail progress	H10, H12, B9, C5	H, B, C
Access note: Compliance/Audit screen may warrant a simple access gate (even at single-user scale, a "confirm to view" step) since it's the least frequently needed and most sensitive from an audit-integrity perspective — not a security requirement at MVP, just a UX separation from daily-use screens.

# 11. Alert-to-Metric Mapping
Cross-referencing Document 2/3's alerting requirements to the specific metrics that trigger them:

Alert	Triggering Metric / Threshold	Source Doc
Setup Validated → Order Placed → Filled → Partial → Exit	Trade lifecycle events (A-series timestamps)	Doc 2
Daily Circuit Breaker Tripped	C3 crosses −4%	Doc 2, Sec 7
MT5 Disconnect/Reconnect	F2 event	Doc 3, Sec 6
Process Crash	F3 event	Doc 3, Sec 6
Daily Heartbeat Gap	F5 (absence of expected ping, either cadence)	Doc 2, Sec 2.5 (corrected, v1.1)
Order Rejection (Margin/Max-Lot/Min-Lot/SL-Cap/Spread)	D7/D8/D14 events	Doc 2, Sec 8; Doc 2, Sec 5
Reconciliation Discrepancy	H3 falls below 100% match	Doc 4, Sec 4.2
External VPS Uptime Failure	F11 failure	Doc 3, Sec 6
Forward-Test Early-Warning Checkpoint	H10 verdict logic run at trade #20 and #35; fires only if currently classifying as HARD FAIL	Doc 2, Sec 9.5 (corrected, v1.1 — was a vague "nearing" threshold; now references the actual checkpoint mechanism)
Forward-Test HARD FAIL Triggered	H10 crosses any Doc 2 §9.5 Hard-Fail condition (MaxDD≥10%, CB>3/month, or PF<1.2 with ≥30 trades)	Doc 2, Sec 9.5 (new, v1.1)
# 12. Provisional Parameter Tagging in UI (Hard Rule)
Any displayed metric whose calculation depends on a Document 2, Section 9 provisional parameter (SL caps, displacement thresholds, circuit breaker %, risk state percentages, win-streak trigger) must carry a visible "Provisional — subject to recalibration post forward-test" indicator wherever shown. This is a hard UI requirement, not a nice-to-have — it exists to prevent anyone (including the owner, months from now) from mistaking an early-stage calibration guess for a proven constant. (Extended, v1.1) This same tagging applies to the Forward-Test PASS/FAIL/REVIEW thresholds in Doc 2, Sec 9.5, and to the net-new 30-trade Hard-Fail floor and the trade #20/#35 checkpoints — all are provisional/newly-introduced values subject to the same recalibration discipline.

# 13. What This Document Does NOT Cover
Exact SQL views/materialized views implementing each metric (Phase build artifact).
Visual design system (colors, fonts, exact wireframes) — functional layout only is specified here (Section 10); pixel-level design is a build-phase task.
Real-time subscription implementation code (Document 3, Section 4.1 already sets the architectural approach).
# 14. Change Log
v1.0 (original) — Initial full metrics catalog: 112 metrics across 8 categories, stated as 56 Tier-1. Dashboard screen architecture mapped to categories. Alert-to-metric cross-reference established. Provisional-parameter UI tagging rule locked.

v1.1 (this document, 25 July 2026) — Documentation hardening pass:

Tier-1 count corrected from 56 to 60. The original document's Section 9 "totals check" summed 6+10+9+6+8+7+5+5=56 and appeared internally consistent, but four of those eight per-category inputs did not match the actual Tier-1 tags present in the tables above them (Category A was actually 7 not 6; B was 11 not 10; E was 9 not 8; F was 8 not 7). Root cause: the verification arithmetic was checked against itself, not against the underlying table data. Resolved by recounting every row directly and keeping all four previously-uncounted Tier-1 tags (A14 tick-poll latency, B13 win streak, E12 avg SL distance, F12 reconciliation discrepancy count) — each maps to something another document already treats as critical (A14 underlies every timing metric's validity; B13 explains the live risk-state; E12 monitors proximity to the SL cap; F12 is explicitly called a P0 issue in Document 4). Category headers, Section 1 totals, and the Section 9 totals-check line all updated to reflect 60/52.
D10 (Partial-Close Execution Accuracy) formula corrected to reference the actual conditional partial-close logic in Doc 2, Sec 6 (proportional-with-remainder-floor, which may legitimately yield 75%, 100%, or a skip) rather than a flat 75% target — the prior wording would have flagged correct remainder-floor 100% closes as false execution deviations.
H10, H11, and the alert-mapping table's forward-test rows updated to cite Doc 2, Sec 9.5 (the restored, exhaustive Forward-Test Pass/Fail/Review criteria) rather than the previously nonexistent "Doc 2, Sec 6." New Hard-Fail-triggered alert row added; early-warning checkpoint alert row corrected to reflect the actual trade #20/#35 mechanism rather than a vague "nearing" threshold.
F5 (Heartbeat Gap Count) and the corresponding alert-table row corrected to reference the actual dual-cadence heartbeat spec now formalized in Doc 2, Sec 2.5 (09:00 NY daily + 5-minute active-window), rather than an undefined "09:00 NY ping" that had no numeric source anywhere in Document 2 as it previously existed.
C11/C12 (Sharpe/Sortino) citation corrected — these metrics are not referenced anywhere in Document 2; citation removed rather than left pointing at a nonexistent source.
H6 updated to reflect Supabase Free Tier's lack of automated backups (Doc 4, Sec 2.1 v1.1) — now tracks the daily manual export process instead.
F7 updated to include write-timeout fallback events per Document 3, Sec 3.2's new 2-second write-timeout rule.
F11 citation updated to reflect the external uptime monitor's elevated status (hard Phase 1 requirement, not deferred) per Document 3 v1.1.
Section 12 (Provisional Tagging) extended to cover the new Doc 2 §9.5 thresholds and net-new values (30-trade floor, #20/#35 checkpoints).
Date placeholder filled.
End of Document 5 v1.1.

text


---

**Verdict: approved — the Tier-1 recount and every citation now resolve cleanly against Doc 2 v5.0 and Doc 3 v1.1.** No new assumptions introduced; the only judgment call (keeping all 4 extra Tier-1 tags rather than downgrading them) was made explicitly and justified in the Change Log per your earlier sign-off.