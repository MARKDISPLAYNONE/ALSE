# 01_STRATEGY_AND_EXECUTION_LOGIC_SPEC.md

Project: NAS100 Autonomous Liquidity Sweep Engine ("ALSE")
Document 2 of 6 — Strategy & Execution Logic Specification
Date: 25th July 2026
Status: APPROVED v5.0 — Final Deterministic Spec, Restored & Hardened
Supersedes: v4.2
## 0. Who This Document Is For, and What You Are Responsible For
If you are coding the trading engine, this is your bible. Every rule in this document is final, numeric, and deterministic — there is no subjective judgment left in this specification. If you encounter a decision point while coding that requires you to guess, interpret, or use "trader intuition," stop and escalate immediately. That is a specification defect, not a normal coding decision, and it must be logged and resolved before you proceed. This project has already been through multiple rounds of catching exactly this failure mode (subjective language like "aggressive candle" or "chosen level" that couldn't be coded) — do not reintroduce it.

Your responsibility as the reader/implementer:

You implement exactly what is written here. You do not "improve," soften, or reinterpret a rule based on what you think would trade better. If you believe a rule is wrong, you escalate to the project owner and it gets changed in this document first, with a Change Log entry — never silently in code.
Every numeric constant in this document (10 points, 15pt floor, 100pt cap, 60% body ratio, etc.) is either a hard rule or a provisional parameter. Provisional parameters are explicitly marked as such (Section 9) and are expected to be recalibrated after forward-test data accumulates — do not treat them as sacred, but do not change them without an owner-approved Change Log entry either.
All monetary and price arithmetic described here must be implemented using Python's Decimal type. If you write float anywhere in the order-sizing, PnL, or price-level calculation pipeline, you have violated this specification, full stop.
Before writing a single line of trading logic code, read Section 10 (Full Change Log) in this document. It exists so you understand why the rules are what they are, not just what they are — several of these rules exist specifically because an earlier, more "obvious" version of the logic was proven broken during review.
# 1. Instrument & Broker Environment
Parameter	Value
Broker	FX Pesa — trading name of EGM Securities Limited (CMA Kenya License No. 107), operating under the Equiti Group; underlying execution entity Equiti Brokerage (Seychelles) Ltd (FSA license SD064)
Symbol	UT100xx (NAS100 Future CFD)
Point Value	$20 USD per 1.0 point move per 1.0 lot
Minimum Lot Size	0.01
Maximum Lot Size	25.00 (broker-stated hard cap — confirmed from official contract specification, previously referenced only generically as "broker max lot"; see Change Log v5.0)
Lot Step	0.01
Commission	$10 USD per lot, round-turn
Margin Type	Fixed, 0.5% — UT100xx is confirmed not subject to the broker's tiered-margin schedule (that schedule applies only to specific other index symbols, e.g., UK100Roll); margin/max-lot validation (Section 8) is unaffected either way since it queries the broker's live API at runtime rather than hardcoding a rate
Typical Spread	~2.0 points (informational, broker-stated) — confirms the 5-point Spread Check Gate threshold (Section 4) is a sensible ~2.5x-normal ceiling, not an arbitrarily chosen number
Base Capital (initial)	$10,000 USD
Trading Calendar (Hard Rule):

Trading days: Monday, Tuesday, Wednesday, Thursday only.
Corrected calendar rationale (v5.0 — see Change Log for full detail of the correction): The broker's official contract specification states trading hours in GMT, not NY time as an earlier draft of this document assumed. Converted correctly against NY time (UTC−4 under EDT, applicable during current forward-test season):
Market opens Sunday 18:00 NY (22:00 GMT).
Market closes daily (Mon–Thu) at 16:59 NY (20:59 GMT), reopening ~17:00–18:00 NY after the daily rollover gap.
Market closes for the week Friday 16:57 NY (20:57 GMT).
No Friday trading, confirmed as a structural impossibility, not a preference: the strategy's 20:00 NY range-marking window cannot occur on a calendar Friday because the market has already been closed for over 3 hours by that point (last close 16:57 NY, does not reopen until Sunday 18:00 NY). What was previously informally called "Thursday's overnight session" already fully covers this: the GMT-labeled "Friday" trading block (00:00–20:57 GMT) corresponds, in NY time, to the continuous session running from Thursday 20:00 NY through Friday 16:57 NY — i.e., it is the same session already being traded, not a separate Friday opportunity being missed.
No Sunday trading — rationale corrected, this is now an explicit risk-management decision, not a market-closure fact: under the corrected hours, the market reopens at 18:00 NY Sunday, meaning it is technically open by the 20:00 NY range-marking start. Sunday is excluded anyway, by deliberate choice, because the 20:00–21:00 NY window falls only ~2–3 hours after the weekly reopen — a well-documented thin-liquidity, gap-risk period in FX/CFD markets generally. The strategy's edge assumes reasonably normal liquidity dynamics during range-marking; trading it against a potentially gap-distorted post-reopen Sunday range introduces avoidable risk for an as-yet-unquantified benefit. This decision was explicitly reviewed and confirmed by the project owner on 25 July 2026.
Tightened Hard-Kill safety margin (v5.0 finding — operational note, not a rule change): because the true daily close (Mon–Thu, and the Friday-week-close) is 16:57–16:59 NY, the 16:16 NY Hard-Kill (Section 2) now has a confirmed real buffer of approximately 41–43 minutes, not the multi-hour buffer implied by the earlier, incorrect hours. The Hard-Kill time itself is unchanged and remains adequate — but given the tighter real margin, Hard-Kill execution confirmation is elevated to a high-priority alert (Document 3, Section 5), especially for any Thursday-opened position still open into Friday.
Known Risk Factor — broker dynamic leverage cap (v5.0, new finding, accepted risk): the broker's published policy caps account-wide leverage to 1:500 beginning 1 hour before weekly market close (≈15:57 NY Friday) through 1 hour after weekly reopen (≈19:00 NY Sunday), and similarly around major NFP/CPI/Fed/ECB/BoE releases. The Friday leverage-cap window (starting ≈15:57 NY) begins before the 16:16 NY Hard-Kill fires on any Thursday-opened position still open into Friday — meaning such a position could briefly be subject to broker-reduced leverage in the ~19 minutes before this system's own Hard-Kill executes. Whether this affects maintenance margin on an already-open position (vs. only new orders) is broker-implementation-dependent and cannot be fully resolved from published documentation alone. Accepted as a monitored tail risk, not engineered around at the spec level — explicitly flagged for observation during Phase 4 demo trading (watch for any unusual margin behavior on Thursday-into-Friday held positions), and tracked in Document 6's risk register. NFP/CPI/Fed/ECB/BoE release timing was checked against the 20:00–21:00 NY execution window directly: NFP always falls on an already-excluded Friday; CPI and central bank rate decisions release during NY morning/early afternoon, with no overlap. No additional exclusion is required.
Standard US bank holidays and FOMC dates: hardcoded exclusion list, maintained as a static array, checked before range-marking begins each day.
Official source status (updated, v5.0): the broker's official UT100 contract specification text (hours, margin, lot limits, leverage policy) has now been directly captured and reviewed as part of this Change Log entry (25 July 2026), resolving the substance of the previously outstanding action item. Residual, non-blocking action: a dated screenshot/PDF of the source page should still be saved as the formal audit-trail artifact per Document 4's evidentiary standard — tracked in Document 6, does not block Phase 1.
# 2. Time & Session Management
Timezone handling:

All database timestamps stored in UTC.
All session/execution logic calculated dynamically against America/New_York using Python's zoneinfo library, so DST transitions are handled automatically without manual offset logic.
Session Windows (NY Local Time):

Window	Time (NY)	Purpose
Range Definition Phase	20:00:00 – 20:29:59	Mark Range_High / Range_Low from 1m data
Execution Window	20:30:00 – 21:00:00	Monitor for sweep + displacement, place entry
Pending Order Expiry	21:00:00	Cancel any unfilled resting limit orders
Daily Hard Kill	16:16:00 (next NY trading day)	Force-close all open positions, cancel all pending orders, regardless of PnL
Daily Rollover/Swap: Confirmed at approximately 17:00 NY, now independently cross-verified against the broker's official GMT-stated hours (20:59–22:00 GMT ≈ 16:59–18:00 NY, see Section 1) rather than resting on a single unverified figure. Execution window (20:30 NY) is well clear of this. A Spread_Check_Gate remains active regardless as a backstop (Section 4).

2.5 System Heartbeat (Hard Rule)
(New in v5.0 — this section is the single source of truth for heartbeat cadence; Documents 3 and 5 reference this section rather than independently restating specific numbers, closing a gap where this figure was previously cited in three places but formally defined in none.)

The trading engine must write a heartbeat signal on two cadences:

Coarse daily ping: one heartbeat row written at 09:00:00 NY every calendar day, regardless of whether it is a trading day. This confirms basic process/VPS liveness independent of trading activity.
Active-window heartbeat: one heartbeat row written every 5 minutes, continuously, from 20:00:00 NY (range-marking start) through the Daily Hard Kill (16:16:00 NY the following trading day) or until all positions/orders for that day are closed/cancelled, whichever is later.
The dashboard (Document 5) surfaces a "System may be offline" warning if either heartbeat is overdue by more than 2× its expected interval.

# 3. Range & Fibonacci Math
Range Marking (20:00–20:29:59 NY):

text

Range_High = MAX(high) of 1-minute candles in window
Range_Low = MIN(low) of 1-minute candles in window
Range_Size = Range_High - Range_Low
All values calculated and stored as Decimal. All levels below computed programmatically at runtime via:

text

Level(ratio) = Range_Low + (Range_Size * Decimal(ratio))
Required levels (only these — no unused extension levels in execution logic):

Level	Ratio	Formula
Bullish SL	-1.0	Range_Low - Range_Size
Bullish Entry	0.25	Range_Low + (Range_Size * 0.25)
(Range Low)	0.0	Range_Low
(Range High)	1.0	Range_High
Bearish Entry	0.75	Range_Low + (Range_Size * 0.75)
Bearish SL	2.0	Range_High + Range_Size
Worked example (verified programmatic output, not hand-typed — do not retype these by hand elsewhere):

Given Range_Low = 28534.1, Range_High = 28684.7, Range_Size = 150.6:

text

-1.0 = 28383.5
0.0  = 28534.1
0.25 = 28571.75
0.75 = 28647.05
1.0  = 28684.7
2.0  = 28835.3   ← corrected value; see Change Log v4.2
The fib table values in the worked example above have been independently re-verified during two separate specification reviews (v4.2 sign-off and v5.0 sign-off) and are confirmed programmatically correct.

Rule: Extension levels beyond -1.0/2.0 (e.g. -2.0, 1.5, 3.0) may be computed and stored for dashboard/chart visualization purposes only (Document 5). They are not referenced anywhere in execution logic.

# 4. Sweep & Displacement Detection Logic (20:30–21:00 NY)
Bullish Setup Sequence:

Price trades below 0.0 (Range_Low) — sweep confirmed.
A 5-minute candle closes back above 0.0, and satisfies both:
Minimum Penetration: close is at least 10 points above 0.0.
Body Ratio: abs(Close - Open) / (High - Low) >= 0.60. If High == Low on the evaluated candle (a flat/no-tick candle), the Body Ratio check automatically fails (treated as non-displacement); continue monitoring the next 5m close within the remaining window.
If both conditions met → Bullish setup validated.
Bearish Setup Sequence:

Price trades above 1.0 (Range_High) — sweep confirmed.
A 5-minute candle closes back below 1.0, satisfying:
Minimum Penetration: close is at least 10 points below 1.0.
Body Ratio: abs(Close - Open) / (High - Low) >= 0.60. If High == Low on the evaluated candle (a flat/no-tick candle), the Body Ratio check automatically fails (treated as non-displacement); continue monitoring the next 5m close within the remaining window.
If both conditions met → Bearish setup validated.
If a 5m candle closes beyond the level but fails either numeric check: ignore it, continue monitoring the next 5m close within the remaining window.

Whipsaw / Dual-Setup Handling (FIFO, Hard Rule):

If High is swept first with no valid displacement close, and Low is subsequently swept with a valid displacement close → take the Bullish setup only.
If both a valid Bullish and valid Bearish displacement close occur in the same window: whichever side's 5m candle closes and validates first (by timestamp) is the setup taken.
The instant an entry order is placed for the winning side, the opposite side is permanently suppressed for the remainder of that day's window. No dual-directional orders ever exist simultaneously.
Resting Order Invalidation Rule: If a resting limit order exists from an already-validated setup, and the opposite-direction sweep+displacement sequence subsequently validates before the resting order fills, the engine immediately sends an order_cancel (TRADE_ACTION_REMOVE) request for the resting order before processing the newly validated opposite setup. A stale order is never allowed to fill after being invalidated by contrary market structure.
If neither side validates by 21:00 NY → setup aborted for the day, no trade taken, engine resumes monitoring the next valid trading day.
Spread Check Gate (Hard Rule):

Scope limitation (Hard Rule, added v5.0): This gate applies exclusively to NEW ENTRY order submissions (the initial BUY_LIMIT/SELL_LIMIT placement). It does not apply to, and never blocks, Hard-Kill closing orders (Section 6) or Circuit-Breaker flatten orders (Section 7), which are always sent as unconditional market orders regardless of prevailing spread. (This closes a direct contradiction identified during v5.0 review — the original unscoped wording could have been read to block the system's own "no exceptions" force-close guarantees.)

Query mt5.symbol_info_tick().ask - mt5.symbol_info_tick().bid immediately before new entry order placement.
If spread > 5 points → reject the order, log Rollover/Spread Widen Rejection, do not retry within the same setup instance.
# 5. Entry, Stop Loss & Take Profit Logic
Bullish Setup:

Entry: Limit Buy at 0.25
Stop Loss: -1.0
SL Distance = Entry - SL (in points) = 1.25 × Range_Size
TP Distance = 3 × SL Distance
TP Price = Entry + TP Distance
Bearish Setup:

Entry: Limit Sell at 0.75
Stop Loss: 2.0
SL Distance = SL - Entry (in points) = 1.25 × Range_Size
TP Distance = 3 × SL Distance
TP Price = Entry - TP Distance
Order Type (Hard Rule): ORDER_TYPE_BUY_LIMIT / ORDER_TYPE_SELL_LIMIT, with sl and tp parameters passed in the same order_send() request — SL/TP are held server-side by the broker from the instant the order is placed, never managed only in application logic.

Hard SL Caps (Auto-Reject, Provisional — see Section 9):

If SL Distance < 15 points → reject setup, log SL Too Shallow.
If SL Distance > 100 points → reject setup, log SL Exceeds 100pt Cap.
Order Expiry (Hard Rule):

Any resting limit order unfilled by 21:00:00 NY is cancelled automatically. No exceptions, no extension.
# 6. Trade Management
1.5R Partial Close Trigger:

If a 5-minute candle closes beyond 1.5R in the trade's favor (i.e., 50% of the 3:1 TP distance) → execute partial close per the formula below, then move Stop Loss to Entry Price + 5 points (longs) / Entry Price − 5 points (shorts) on the remaining position.
Partial Close Math (Decimal, Proportional with Remainder Floor — Hard Rule):

text

Let L = total open position lot size (Decimal)
Target_Close = floor(L * Decimal("0.75"), step=0.01)  # round DOWN only

If (L - Target_Close) < 0.01:
    Target_Close = L   # close 100%, runner too small to manage
    # SL move to BE+5 is skipped since position is fully closed

If Target_Close == 0:
    Skip partial close entirely. Move SL to BE+5 on the full remaining position instead.

Otherwise:
    Execute partial close of Target_Close lots.
    Move SL to BE+5 on the remainder (L - Target_Close).
Rounding rule (Hard Rule): All lot-size rounding in this system rounds down, never to nearest, never up. This applies to entry sizing and partial-close sizing without exception.

Hard Kill (16:16 NY, Hard Rule):

All open positions force-closed via market order.
All pending/resting orders cancelled.
Commissions absorbed as a cost of the system, not optimized around.
This fires regardless of current PnL, regardless of risk state, regardless of anything else in this document.
(v5.0 note) The Spread Check Gate never applies to this action (Section 4). The real confirmed safety margin against the broker's actual daily close is ~41–43 minutes (Section 1) — Hard-Kill execution confirmation carries elevated alert priority (Document 3, Section 5) given this tighter, now-corrected margin.
6.5 Backtest Methodology Commitment (Hard Rule for Phase 3)
(New in v5.0 — restores content previously referenced by Document 6's Phase 3 description but never formally written here.)

The Phase 3 backtest (Document 6) must adhere to the following methodology to be considered valid input for calibrating the Provisional Parameters in Section 9 and the Backtest Expectancy baseline used in Section 9.5:

Backtest uses variable, session-appropriate spread modeling — not a flat/optimistic spread assumption. Spreads during the 20:00–21:00 NY window (thin relative to peak US-session liquidity in NAS100 terms) must be modeled realistically, not assumed equal to peak-liquidity conditions.
A conservative slippage penalty is applied to all simulated fills (entry, SL, TP, partial close, hard-kill) — backtest fills are never assumed to occur at the exact theoretical price.
Minimum 12 months of tick-level data required as the baseline sample.
All results from this backtest are explicitly labeled as the calibration basis for Section 9's Provisional Parameters and as the "Backtest Expectancy" baseline referenced in Section 9.5 — not as a standalone performance claim.
# 7. Risk Model & Position Sizing State Machine
Base Parameters:

Base Capital: $10,000 USD (initial)
Risk is calculated against start-of-day equity, not live/floating equity, to prevent intraday compounding drift.
States:

State	Risk % of Start-of-Day Equity
A — Aggressive (default)	2.0%
B — Throttle	0.5%
Win Definition (Hard Rule): A trade is a "Win" if net realized PnL (including all partials + runner, net of commission) is > $0.01.

Full State Transition Table (Hard Rule, Exhaustive — replaces prior partial description, v5.0):

Current State	Event	New State	Win-Streak Counter	Notes
A (Aggressive)	Win (streak was < 4 before this win)	A	Increments by 1	Continues toward 5-win trigger
A	Win (5th consecutive)	B	Resets to 0	Transition fires immediately
A	Loss	A	Resets to 0	Any loss breaks the consecutive-win streak — previously left to inference from the word "consecutive," now explicit
A	No-Trade Day (setup aborted, spread-rejected, margin-rejected, or min-lot-skipped — no position was opened)	A	Unchanged (frozen)	A no-trade day is neither a win nor a loss; does not reset or advance the streak
B (Throttle)	Win	A	Resets to 0	Transition fires immediately regardless of how many losses preceded it in State B. The winning trade does not count toward State A's next streak — the new streak starts at 0
B	Loss	B	N/A (State B has no win-streak counter; unlimited loss absorption)	Remains in State B, no limit, provided Daily Circuit Breaker is not tripped
B	No-Trade Day	B	N/A	No change to state
Daily Circuit Breaker (Hard Rule):

Track Realized_PnL_Today + Floating_PnL continuously.
If this value drops below −4% of Start-of-Day Equity: immediately flatten all open positions (market close), cancel all pending orders, halt all new trade entries for the remainder of the calendar day.
Log event as Daily Circuit Breaker Tripped.
This check overrides the Risk State Machine entirely — it does not matter what state (A or B) the system is in when it trips.
# 8. Lot Sizing Formula
Pre-Trade Validation Checklist (executed before every order submission, in order):

Risk Budget:
text

Risk_Budget_Initial = StartOfDay_Equity * Risk_Percentage (Decimal)
Closed-Form Lot Size (commission-inclusive, non-circular):
text

Lot_Size = Risk_Budget_Initial / (SL_Points * Decimal("20") + Decimal("10"))
Lot_Size = floor(Lot_Size, step=0.01)  # round DOWN only
Minimum Lot Floor Check:
If Lot_Size < 0.01 → SKIP TRADE. Log Insufficient Equity for Min Lot. Do not force a trade at 0.01 lots — that would silently exceed the intended risk percentage.
Margin/Max Lot Check:
Query mt5.account_info() for margin_free.
Calculate required margin via mt5.order_calc_margin().
If required margin > free margin, OR Lot_Size > 25.00 (confirmed broker max lot for UT100xx, Section 1) → SKIP TRADE. Log Margin/Max Lot Exceeded.
TP is strictly 3× SL point distance in all cases (Section 5). No independent TP override exists anywhere in this system.

# 9. Provisional Parameters (Explicit Flag — Do Not Treat as Permanent)
The following numeric values are accepted for MVP / initial forward test, based on limited (≤12 months) backtest data. They are not final and are expected to be recalibrated once live forward-test data accumulates. Any recalibration is a Change Log event, not a silent edit.

Parameter	Current Value	Basis
Minimum SL Distance	15 points	Provisional, spread-choke protection
Maximum SL Distance	100 points	Provisional, bounds TP/lot-size blowup on wide-range days
Displacement Minimum Penetration	10 points	Provisional, noise filter
Displacement Body Ratio	60%	Provisional, noise filter
Circuit Breaker Threshold	4% daily drawdown	Provisional
Aggressive/Throttle Risk %	2.0% / 0.5%	Provisional
Win-streak throttle trigger	5 consecutive wins	Provisional
Forward-Test PASS/FAIL/REVIEW thresholds (Section 9.5)	See Section 9.5	Provisional — recalibrated only via explicit owner-approved Change Log entry, same discipline as all other provisional values
9.5 Forward-Test Pass/Fail/Review Criteria (Hard Rule)
(New in v5.0 — restores content previously referenced by Documents 1, 5, and 6 but absent from this document's actual text. See Change Log for the full account of this defect and its resolution. This section is the single source of truth for Phase 5 evaluation; Documents 5 and 6 reference it rather than restating thresholds independently.)

Evaluated continuously throughout the forward test, in strict precedence order — first matching condition wins:

# 1. HARD FAIL (checked at all times, can trigger before 50 trades, overrides all other states)

Triggered if ANY of the following become true at any point:

Max Drawdown (from forward-test peak equity) reaches or exceeds 10%, OR
Daily Circuit Breaker trips more than 3 times within any single calendar month, OR
Net Profit Factor falls below 1.2 AND total trade count has reached at least 30 (the 30-trade floor exists because Profit Factor on a smaller sample is statistically unstable and not a reliable fail signal — added during the v5.0 hardening pass, flagged explicitly as net-new, not a restoration of prior content).
If HARD FAIL triggers: halt all live trading immediately, flatten any open positions, do not resume without explicit project owner review and a documented post-mortem.

# 2. IN PROGRESS (if HARD FAIL has not triggered, and total trade count < 50)

No PASS/FAIL/REVIEW verdict is rendered yet. Trading and monitoring continue normally.

Two informational, non-binding checkpoints occur during this phase (net-new in v5.0):

At trade #20: run the full verdict logic (below) as an early-warning check. If it would currently classify as FAIL, fire a Discord alert. This does not end the test.
At trade #35: repeat the same early-warning check.
# 3. FINAL VERDICT (evaluated once total trade count reaches 50, and HARD FAIL has never triggered)

PASS if ALL of the following are true simultaneously: Net Profit Factor > 1.5, AND Max Drawdown < 10%, AND total trades ≥ 50, AND Live Expectancy per trade > 70% of Backtest Expectancy per trade (Section 6.5 baseline).
FAIL if Net Profit Factor < 1.2 (also covered by the continuous Hard Fail check above; restated here for completeness of the final-verdict table).
REVIEW for every other combination not captured by PASS or FAIL above (e.g., Profit Factor between 1.2–1.5 regardless of other metrics; or Profit Factor > 1.5 but Expectancy variance ≤ 70% of backtest). REVIEW requires manual owner analysis of the full trade distribution before any further live-capital decision — no automatic action is taken by the system itself.
Explicit non-trigger clarification: trade count below 50 is never itself a FAIL or REVIEW condition — it is only ever the reason the verdict is "IN PROGRESS."

# 10. Full Change Log — Evolution of This Specification
This section exists so that no future developer mistakes the current logic for "the original idea untouched." Every material change from the original architecture document through final sign-off is recorded here, dated by review cycle, with rationale. This is not optional reading — Section 0 requires you to read this before coding.

v1.0 (Original Architecture Document)

Range source: prior closed 1H candle (liquidity swept was from a fully completed session).
Entry: 50% retracement of the LTF displacement move itself.
Displacement confirmation: subjective — "aggressive full-bodied candles" + required Fair Value Gap (FVG).
SL: dual logic (Structural SL vs Fibonacci SL) with no tie-break rule defined.
Risk throttle reset logic: "a loss (or two) is absorbed... on the very next win, resets" — ambiguous, non-codeable.
Partial close: flat "75% of position," breaks at micro lot sizes.
No margin check, no DST handling, no Friday/Sunday exclusion considered.
v2.0 (First Deterministic Pass)

Range source changed to first half of current 1H candle (20:00–20:29 NY) — a deliberate departure from v1.0's prior-candle concept, confirmed as intentional by project owner after direct challenge.
FVG requirement dropped; displacement defined only qualitatively at this stage (still a defect, caught in review).
Structural SL dropped entirely in favor of deterministic Fib-only SL — resolved the v1.0 tie-break ambiguity.
Risk state machine formalized: exact 5-win trigger, exact 1-win reset, unlimited-loss absorption in Throttle state — resolved the "or two" ambiguity.
Margin/max-lot check and min-lot skip-not-force logic introduced.
Banded partial-close logic introduced (0.10/0.04 thresholds) — later found to distort actual close percentage across the band.
Commission-inclusive lot sizing formula introduced but written in circular form (Lot_Size referenced before it was calculated) — defect not caught until later review.
v3.0 (Simplification Pass)

Displacement filter and hard SL caps both deleted rather than quantified — flagged as a regression, not a fix, since the review request was to make thresholds numeric, not remove them.
This version also silently carried forward the range-source change from v2.0 without acknowledging it as a departure from v1.0 when directly challenged — flagged as a documentation-discipline failure.
v4.0 (Full Remediation Pass)

Range source: explicitly confirmed as intentional (first-half-of-current-candle) with rationale recorded.
Hard SL caps reinstated: 15pt min / 100pt max, explicitly marked provisional.
Displacement filter reinstated as fully numeric: 10pt minimum penetration + 60% body ratio.
Commission formula corrected to closed-form, non-circular: Lot_Size = Risk_Budget / (SL_points × 20 + 10).
Partial-close logic corrected to proportional-with-remainder-floor model, replacing the distortion-prone banded logic.
Resting order invalidation rule added (opposite-side confirmation cancels stale resting orders).
FIFO dual-setup handling formalized.
Order type corrected: BUY_LIMIT/SELL_LIMIT (was incorrectly specified as BUY_STOP in an earlier infra note).
Decimal-only math mandated for all lot/price/money calculations; float banned from this pipeline after tracing a rounding failure mode in the partial-close logic.
Alerting expanded to include system-health events (disconnects, crashes, heartbeat, order rejections), not just trade-lifecycle events.
v4.1 (Broker Calendar Verification — Superseded by v5.0, see below)

FX Pesa UT100 schedule believed obtained: Sunday open 22:00 NY, Friday main close 20:15 NY, Friday late session 20:30–20:57 NY, daily rollover 17:00 NY.
Friday trading excluded entirely; Mon–Thu only adopted as a hard rule.
Sunday trading excluded on the stated basis that the market was closed during the range-marking window.
This entry's underlying hours were later found to be incorrect — see v5.0. The Mon–Thu-only conclusion happened to be directionally correct, but for reasons this entry did not accurately state.
v4.2 (Final Arithmetic Verification)

Bearish SL fib level (2.0) corrected from an erroneously hand-verified 29835.3 to the correct programmatic value 28835.3 (Range_High + Range_Size, verified: 28684.7 + 150.6 = 28835.3). This was caught during final sign-off review and reinforced the standing rule that no derived numeric value enters a spec document without being direct script output — never manually retyped or "double-checked by hand."
v5.0 (Documentation Hardening & Broker-Data Restoration Pass — this document)

Trading calendar correction (root-cause: v4.1's hours were taken from an unverified/incorrectly-converted source):

Obtained and reviewed the broker's actual official contract specification (hours stated in GMT). Correctly converted to NY time for the first time: Sunday open 18:00 NY (was incorrectly stated as 22:00 NY), weekly close Friday 16:57 NY (was incorrectly stated as 20:15 NY with a fictitious fragmented late session), daily Mon–Thu close/rollover ~16:59–18:00 NY (this one was already approximately correct).
Mon–Thu-only trading days unchanged as a hard rule — but the rationale is now correctly stated: Friday trading is a structural impossibility (the GMT-labeled "Friday" session is, in NY time, the same Thursday-evening-through-Friday-afternoon session already traded), not a session-fragmentation workaround.
Sunday exclusion rationale corrected from "market is closed" (factually incorrect under real hours) to an explicit, owner-confirmed risk-management decision regarding post-reopen liquidity thinness.
Hard-Kill safety margin corrected from an assumed multi-hour buffer to the true ~41–43 minute buffer; elevated monitoring priority added as a compensating control.
New Known Risk Factor documented: broker dynamic leverage caps (1:500) around weekly close/open and major economic releases, with a specific identified overlap window on Thursday-into-Friday held positions, prior to this system's own Hard-Kill. Accepted as a monitored tail risk, tracked for observation in Phase 4.
Confirmed broker Max Lot Size (25.00), previously referenced only generically, now explicit in Sections 1 and 8.
Confirmed broker regulatory structure (EGM Securities Ltd, CMA Kenya License 107; Equiti Brokerage Seychelles, FSA license SD064) for Document 4's audit trail.
Logic restoration and hardening:

Restored the Forward-Test Pass/Fail/Review criteria (new Section 9.5), previously referenced by Document 1 and Document 5 but absent from this document's actual text — root cause: content loss during an earlier drafting pass, caught during a full six-document cross-reference audit. The restored criteria are not a simple re-paste: the original three-line form had at least one undefined outcome (e.g., PF > 1.5 with Expectancy variance failing the 70% bar); Section 9.5 is now an exhaustive, precedence-ordered decision table with no undefined states.
Added a 30-trade minimum floor before Profit Factor alone can trigger a FAIL (Section 9.5) — flagged explicitly as a net-new rule, not a restoration, subject to owner veto (confirmed accepted).
Added two non-binding early-warning checkpoints at trade #20 and #35 (Section 9.5) — net-new, confirmed accepted.
Spread Check Gate (Section 4) scope explicitly limited to new entry orders only — closes a direct contradiction with the Hard-Kill and Circuit-Breaker "no exceptions" rules.
Risk State Machine (Section 7) given a complete, exhaustive transition table covering loss-resets-streak and no-trade-day-freezes-streak behavior, previously left to inference from the word "consecutive."
Body Ratio displacement check (Section 4) given explicit divide-by-zero handling for flat (High==Low) candles.
New Section 2.5 formalizes System Heartbeat cadence (09:00 NY daily ping + 5-minute active-window heartbeat) as a single source of truth, previously referenced with specific numbers in Documents 3 and 5 without ever being defined here.
New Section 6.5 formalizes the Backtest Methodology Commitment (variable spread modeling, slippage penalty, 12-month minimum), previously referenced by Document 6 but not written here.
All existing v1.0–v4.2 logic, numeric values, and Change Log history preserved unchanged and in full above this entry.

v5.1 (28 September 2026 — decisions delegated by the project owner to the lead developer, logged per Doc 1 §0)

Calendar defect correction: hold-window rule. Doc 2 §1's check of NFP/CPI/Fed timing compared release times only against the 20:00–21:00 NY ENTRY window. Positions are held until the 16:16 NY Hard-Kill on the next weekday, so the hold window was never checked. The official BLS schedules also contradict the claim that "NFP always falls on an already-excluded Friday": NFP released Tue 16 Dec 2025, Wed 11 Feb 2026 and Thu 2 Jul 2026, and CPI regularly lands Tue–Thu. Every Thursday session was being held through Friday's 08:30 NFP, and every CPI-eve session through CPI. That exposed open positions to gap-through-SL risk (breaking the per-trade risk-% guarantee that metric C14 validates) and to the broker's 1:500 leverage cap around NFP/CPI/Fed releases, which §1 had flagged as an unresolved tail risk.
New exclusion rules (hard rules). Session D (range 20:00 D → Hard-Kill 16:16 on next weekday K) is excluded if:
  (a) D is an FOMC decision day: post-statement repricing regime, same rationale as the Sunday exclusion.
  (b) K has an FOMC statement (14:00), CPI (08:30) or Employment Situation/NFP (08:30) release.
  (c) K is a US market holiday or index-futures early-close day (bank holidays, Good Friday, day after Thanksgiving, 24 Dec, 3 Jul), so the 16:16 Hard-Kill could fall after the market closes (resolves the holiday-adjacent Hard-Kill question).
  This replaces the earlier "exclude FOMC dates" wording. Day 1 of an FOMC meeting is excluded by (b), decision day by (a).
  Fail-closed: the event calendar (engine/session/events.py, from federalreserve.gov + bls.gov) has an explicit horizon. Past it, no trading until it is updated; the engine alerts 30 days ahead.
  Measured impact (script output, 2026): 155 of 208 Mon–Thu sessions tradeable (74.5%) vs ~184 before, about 16% fewer. The forward-test estimate moves from ~9–10 to ~11 months. Accepted: the project's methodology puts provable risk control ahead of sample speed.
Resting-order invalidation vs opposite-side suppression (§4 internal contradiction). The suppression rule's stated purpose is "No dual-directional orders ever exist simultaneously"; the later and more specific v4.0 invalidation rule says to cancel the stale order "before processing the newly validated opposite setup". Resolved as: cancel, and only after the broker confirms the cancel, place the opposite setup. If the cancel fails because the order already filled, it is treated as a fill and no reversal happens. At most one reversal per day (≤2 entry orders/day), and at most one filled trade per day.
Setup-level rejections (spread gate, margin/max-lot, min-lot, SL caps): "do not retry within the same setup instance" means that side is finished for the day; the opposite side may still validate as a separate setup instance.
Price-tick rounding: entry/SL are rounded to the symbol tick in the conservative direction; SL points and TP are derived from the rounded prices (TP = exactly 3× the real SL distance).
A 5m candle closing at exactly 21:00:00 NY is not acted on, because its order would expire in the same instant (§5).
# 11. What This Document Does NOT Cover
To keep document boundaries clean (per Document 1, Section 6):

Database schema — Document 3 (Architecture).
Python boilerplate/code — build artifact, downstream of Document 3.
Security/credential handling — Document 4.
Metric definitions and dashboard behavior — Document 5.
Current build phase and timeline status — Document 6.
End of Document 2 v5.0.

text


---

**Verdict: approved by me — every fix traces back to something we explicitly resolved this session, nothing new snuck in silently.** This was the heaviest document in the whole set; it's done.