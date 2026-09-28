# 03_RISK_SECURITY_LEGAL_COMPLIANCE.md

Project: NAS100 Autonomous Liquidity Sweep Engine ("ALSE")
Document 4 of 6 — Risk, Security, Legal & Compliance Framework
Date: 25th July 2026
Status: APPROVED v1.1 — Jurisdiction Confirmed, Broker Regulatory Status Verified
Supersedes: v1.0
# 0. Who This Document Is For, and What You Are Responsible For
This document has zero tolerance for "we'll get to it later." Everything else in this project (strategy logic, architecture) can be iterated on safely because bad trading logic loses money slowly and visibly. The failure modes covered in this document — a leaked API key, an unencrypted credential, a missing disclaimer, an unlogged manual override — tend to fail silently and catastrophically, either as a security breach, a legal liability, or an un-auditable gap that makes it impossible to prove what the system actually did after the fact.

Your responsibility as the reader/implementer:

If you are the infra developer: you implement the security controls in Section 1 exactly as specified, before any credential touches a live broker account. This is not a "phase 2 cleanup" item — it is a precondition for Phase 1 going anywhere near real capital.
If you are the project owner: Sections 3 and 4 (Legal, Data Privacy) require decisions and inputs only you can provide — jurisdiction, entity structure, and risk tolerance for legal exposure cannot be fabricated. Section 3.1 is now resolved (see below); treat any remaining unresolved item as a placeholder, not an answer.
Nobody on this project — regardless of role — has authority to skip an audit-log requirement, disable a security control, or bypass the incident response runbook "just this once" to move faster. If a control in this document is genuinely blocking legitimate work, the fix is to raise it and amend the document, not quietly work around it.
This document assumes single-user, personal-capital operation for the current phase, confirmed final in Document 3, Section 0.1. Every section below is written for that scope. The moment this system is used by anyone other than you, or with anyone else's capital, this entire document must be re-reviewed before that happens — the legal and compliance surface changes completely at that point (Section 3.4 explains why). This is flagged once here and will be flagged again in Document 6's phase gates.
1. Security
1.1 Credential & Secrets Management
Hard rules:

No credential (MT5 login/password, Supabase service keys, Discord webhook URLs) is ever committed to source control, in any form, at any point — not in a config file, not in a comment, not in a "temporary" test script. Enforce this with a .gitignore covering all env/secret files from the very first commit, and ideally a pre-commit hook that scans for accidental secret patterns before allowing a commit.
All credentials are stored in environment variables (.env file, excluded from git) at MVP/single-user scale. This is acceptable for a single-user system on a single VPS you control. This is explicitly not acceptable once the system is multi-user — at that point, credentials move to a proper secrets manager (a paid cloud provider's secrets manager, HashiCorp Vault, or Supabase Vault), which becomes a hard requirement in the phase-gate before any multi-user launch (Document 6).
MT5 account credentials are used only by the trading engine process on the VPS. They are never exposed to, or accessible from, the dashboard application, per the module boundary locked in Document 3, Section 7.
Supabase access is split by role: the trading engine uses a service role key with write access to core tables; the dashboard uses a restricted anon/public key governed entirely by Row-Level Security policies (Section 1.2) with read-only access. The dashboard must never hold a credential capable of writing to trade/order tables.
1.2 Database Access Control
Row-Level Security (RLS) is enabled on every Supabase table from day one, not added later. Default-deny, explicit-allow.
Audit/trade history tables: INSERT-only policy for the engine's service role, no UPDATE/DELETE policy exists for any role, including the owner's personal Supabase dashboard login, at the database level. If a correction is ever needed, it happens via a new compensating row (Document 3, Section 3.3), never a manual edit — this is enforced structurally, not just as a promise.
(Clarified, v1.1) This same INSERT-only, no-UPDATE/DELETE structural enforcement applies equally to provisional-parameter-change logs and manual-intervention logs (Section 4.1) — not only to trade/order tables. A human-performed action is logged with the same immutability discipline as a machine-performed one; nothing in this system's audit trail is editable after the fact, regardless of who or what generated the row.
Dashboard's read-only key can SELECT from analytics/summary tables and current-state tables (open positions, today's metrics) only — it has no access to any table capable of exposing raw credentials or system configuration.
1.3 Network & Access Security
VPS access restricted via SSH key-based authentication only — no password login enabled at any point.
(Updated, v1.1) VPS firewall (cloud provider's security-group/network-security-list equivalent — Oracle Cloud's primary, AWS's fallback per Document 3, Section 1) restricted to only the ports genuinely required (SSH from your known IP only, plus whatever MT5/outbound connections require) — no open inbound ports beyond what's functionally necessary. This requirement is provider-agnostic and applies identically regardless of which free-tier host is ultimately used.
Discord webhook URLs treated as secrets (Section 1.1) — a leaked webhook URL allows an outside party to spam your alert channel, which is low severity but should still not be careless.
1.4 Application-Level Security
No trading command execution path exists from the dashboard in this phase (Document 3, Section 4.3) — this eliminates an entire class of attack surface (a compromised dashboard session cannot place or modify trades) at the cost of the dashboard being observation-only for now. Deliberate tradeoff, already agreed.
All Supabase writes from the trading engine are parameterized/typed through the client SDK — no raw string-concatenated SQL anywhere, eliminating SQL injection as a risk category entirely by construction.
# 2. Operational Risk & Disaster Recovery
2.1 Backup Policy
(Updated, v1.1 — reflects confirmed $0-budget, Supabase Free Tier decision, Document 3 Section 0.1)

Supabase Free Tier is the confirmed starting point (Document 3, Section 1) and carries no automated backup guarantee. This is a real, accepted gap — not an oversight — compensated for entirely by the manual export policy below until the Pro-tier upgrade trigger (Document 3, Section 1) is reached.
Manual export cadence elevated from weekly to daily, given the absence of automated backups: a full export of the trade/order history tables to a separate, owner-controlled storage location (a local encrypted file, or a separate free-tier cloud bucket) must run daily, not weekly, as originally scoped under a paid-tier assumption. This is a second, independent copy outside Supabase's own infrastructure, in case of an account-level Supabase incident.
Upgrade trigger: the day Supabase moves to Pro tier (Document 3, Section 1's trigger), automated daily backups become active and the manual export cadence may be relaxed back to weekly, logged as a Document 6 phase-gate event when it happens.
2.2 Incident Response Runbook
This is the step-by-step "what do I actually do" reference for the failure scenarios Document 3, Section 6 described at the architecture level. This section makes it operational.

If the Daily Circuit Breaker trips:

System has already auto-flattened positions and halted new entries (Document 2, Section 7) — no immediate action required to protect capital.
Owner reviews the Discord alert and the corresponding Supabase log entry to confirm the flatten executed cleanly (check actual fill prices vs. expected).
No trading resumes until the next valid trading day automatically — no manual re-enable action is needed or should be taken same-day.
If a system disconnect/crash alert fires:

Check whether systemd already auto-restarted the process (Document 3, Section 6) — the crash alert should be followed shortly by a "process restarted" log entry if auto-recovery worked.
If no restart confirmation follows within a few minutes, manually SSH into the VPS and check process status. (v1.1 note) Given the Linux+Wine deployment (Document 3, Section 5), also independently verify the MT5 terminal process itself is running under Wine — a Wine-hosted terminal can fail separately from the Python engine process.
Before manually restarting anything, check MT5 account history directly (via the MT5 terminal itself, not just Supabase) to confirm whether any position is currently open and what its actual SL/TP state is at the broker level — the broker's own record is the ground truth, not the local Supabase log, in a recovery scenario.
Only after confirming actual broker-side state should the engine be restarted, and it must load and reconcile against that real state before resuming any new order logic.
If the VPS itself is fully unreachable:

This is the blind spot flagged in Document 3, Section 6 — no internal alert can fire. This is precisely why the external independent uptime monitor exists — (updated, v1.1) this is now a hard Phase 1 sign-off requirement, not a deferred "Phase 1/2" nice-to-have, given the increased blind-spot risk of a free-tier, Wine-based deployment (Document 3, Section 6).
Open positions remain protected by broker-side SL/TP regardless (Document 3's core invariant) — this is not a capital emergency, it is an availability emergency.
Owner's action: access broker account directly (MT5 mobile app or web terminal, independent of the VPS) to visually confirm position/SL/TP state while VPS access is restored.
If a reconciliation discrepancy is found (Section 4 below) between Supabase logs and actual MT5 account history:

Treat this as a P0 issue — halt new automated trading manually until resolved, even though nothing in Document 2's logic requires this; a logging/reality mismatch means you can no longer trust the system's own risk-state calculations (equity, win-streak counters) since they're derived from potentially-corrupted data.
Root-cause the discrepancy before resuming — do not simply "fix the number and move on."
2.3 Manual Override Policy
There is no built-in manual override/kill-switch UI at MVP (per Document 3, Section 4.3's scope decision). If the owner needs to manually intervene (e.g., force-close everything outside the system's own logic), this happens directly through the MT5 terminal or mobile app, not through this system's dashboard.
Any manual intervention taken outside the system must be manually logged by the owner (a simple note in session-handover.md or a dedicated manual_interventions table) — an untracked manual override is exactly the kind of silent state-drift this entire project has been designed to eliminate elsewhere. The same discipline applies to human actions, not just code. Per Section 1.2 (updated), this log is also structurally append-only.
# 3. Legal & Regulatory
3.1 Jurisdiction, Entity & Tax Treatment (Resolved, v1.1)
(Previously an open placeholder — now confirmed by the project owner, 25 July 2026):

text

JURISDICTION: Kenya
ENTITY STRUCTURE: Individual (not a registered entity)
TAX TREATMENT NOTES: Owner currently files NIL returns with the Kenya Revenue
Authority (KRA), reflecting no current taxable income. This status will need
reassessment once the system generates realized trading gains — the tax
treatment of CFD/forex trading gains for an individual KRA filer is a
jurisdiction-specific question this document cannot resolve on its own.
Recommended action (non-blocking for Phase 1–4, required before Phase 5 live capital): a brief consultation with a Kenyan tax professional regarding how realized CFD trading gains should be declared, given the owner's current NIL-filer status. This is cheap, prudent insurance and should happen well before the forward test produces its first taxable gain — not retroactively.

Broker access legality — de-risked, not eliminated as a question: FXPesa operates in Kenya specifically as a CMA-licensed broker (see Section 3.3), meaning retail CFD/forex access through this specific channel is an explicitly regulated, sanctioned activity for Kenyan residents — not a grey-market or restricted-access situation. This materially reduces the jurisdictional risk this section originally flagged as a potential blocker.

3.2 Risk Disclaimer (Applies Regardless of Jurisdiction — Baseline Language)
Any documentation, dashboard footer, or onboarding material associated with this system should carry, at minimum, language substantively equivalent to:

This system trades leveraged CFD instruments and carries substantial risk of loss, potentially exceeding deposited capital depending on broker margin terms. Past or backtested performance does not guarantee future results. This system is provided for the operator's own use in managing their own trading account and does not constitute financial advice.

This is a baseline placeholder, not a substitute for actual legal review — CFD trading is restricted or banned outright in some jurisdictions (notably the US, for retail traders, on many CFD products). (Updated, v1.1) For Kenya specifically, this question is now substantially answered: CFD trading via a CMA-licensed broker is an explicitly regulated, accessible activity for the owner as a Kenyan resident (Section 3.1). This baseline disclaimer language remains appropriate regardless and should still be treated as a placeholder pending the tax-consultation recommendation above before Phase 5.

3.3 Broker Regulatory Status (Resolved, v1.1)
(Previously an open, unverified item — now confirmed from the broker's own published disclosures, reviewed 25 July 2026):

The FXPesa/Equiti ecosystem involves three distinct regulatory relationships. All three are recorded here for completeness — the specific entity that legally holds the owner's actual trading account is an outstanding sub-item (see action item below), since the applicable investor-protection scheme depends on which one applies:

Entity	Regulator	License / Reference	Relevance
EGM Securities Limited (trading as FXPesa)	Capital Markets Authority (CMA), Kenya	License No. 107 — non-dealing online forex broker	The Kenya-facing, locally regulated entity; first licensed non-dealing online forex broker in Kenya; subject to CMA client-fund-segregation rules
Equiti Brokerage (Seychelles) Limited	Financial Services Authority (FSA), Seychelles	License No. SD064 — Securities Dealers Broker	The entity named in FXPesa's website legal footer as the trademark holder/execution entity
Equiti Capital Limited (UK), parent group entity	Financial Conduct Authority (FCA), UK	Reference No. 528328	Group-level regulation; UK FCA oversight of the broader Equiti Group, referenced in deposit/withdrawal facilitation
Action item (non-blocking for Phase 1–4, tracked in Document 6): confirm from the owner's actual account-opening documentation or statements which specific entity (most likely EGM Securities Ltd, given the CMA-Kenya/M-Pesa-integration context) legally holds the trading account — that is the entity whose investor-protection scheme and recourse mechanisms actually apply to deposited funds. A 5-minute check of onboarding paperwork resolves this.

Practical significance: this determines what recourse exists if the broker itself has an operational failure, and what protections (e.g., CMA's client-fund-segregation requirement) apply to funds held with them. The CMA-Kenya licensing in particular is a meaningfully positive finding — it means the owner's specific broker relationship sits within a locally-enforceable regulatory framework, not an offshore-only one.

3.4 Multi-User / Scaling Trigger (Explicit Gate)
Multi-user design remains explicitly deferred. This document draws a hard line so it isn't forgotten: the moment this system is used by any person other than the owner, or with any capital not solely owned by the owner, the following become mandatory and must be resolved before that happens, not after:

Terms of Use / Client Agreement, legally reviewed
KYC/AML consideration depending on jurisdiction and whether this constitutes a regulated activity (e.g., managing funds on behalf of others may require licensing in many jurisdictions — this is a real regulatory tripwire, not a formality)
Data protection compliance (GDPR or local equivalent) for any personal data collected from additional users
Re-architecture of Section 1's security model (multi-tenant data isolation, no more single shared credential set)
This is written down explicitly so that if this project ever grows past single-user informally — someone asks "can you just trade my account too" — there's a documented gate that has to stop that conversation until this section is actually resolved, rather than it happening informally over a chat message.

# 4. Compliance & Audit
4.1 Audit Trail Requirements (Restating and Formalizing Document 3's Principles)
Every order lifecycle event is logged immutably, synchronously, at time of action (Document 3, Section 3.2) — this is the audit trail, and it is the primary artifact that would be examined in any dispute, tax reporting exercise, or post-mortem.
Every provisional parameter change (Document 2, Section 9 values) is logged with timestamp, old value, new value, and stated reason — mirroring the Document 2 Change Log discipline at the data layer, not just the document layer. (Clarified, v1.1) This log is structurally append-only, per Section 1.2.
Every manual intervention (Section 2.3) is logged by the human who performed it. (Clarified, v1.1) This log is structurally append-only, per Section 1.2.
4.2 Reconciliation Process
Weekly reconciliation (minimum cadence): compare Supabase's trade/order log against MT5's own account history report for the same period. Any discrepancy (missing trade, mismatched fill price, mismatched lot size) is investigated per the Section 2.2 runbook, not dismissed as a rounding artifact without verification.
This reconciliation is the practical check that catches silent logging bugs — e.g., a missed write during a brief Supabase outage — before they compound into a wrong equity-curve or wrong risk-state calculation weeks later.
4.3 Data Retention
Full trade/order history: retained indefinitely — this is both the performance record and the compliance record for the life of the project. (Confirmed, v1.1) This is unaffected by the Free Tier storage cap (Document 3, Section 3.3) — audit tables are orders of magnitude smaller than raw tick data and do not meaningfully threaten the 500MB limit.
Raw tick-level data (used for spread/slippage analytics, not the audit trail itself): (Resolved, v1.1) retention set at a rolling 30–60 day window per Document 3, Section 3.3, specifically to respect the Supabase Free Tier storage cap. This is a storage-economics decision, not a compliance/legal requirement, and does not affect audit obligations.
# 5. Data Privacy
At current single-user scope, this section is minimal by design:

The only personal data in the system is the owner's own broker credentials, trading history, and account equity — all of which the owner already has full access to and ownership of. No third-party personal data is collected, stored, or processed at this phase.
This section must be substantially rewritten the moment Section 3.4's multi-user trigger is crossed — at that point this becomes a real data protection compliance section (what's collected, where stored, retention, right-to-deletion, etc.), not a two-bullet placeholder.
# 6. What This Document Does NOT Cover
Full legal contract drafting (Terms of Use, disclaimers as formal legal documents) — this document defines what must exist, not the final legal-reviewed text itself, which requires actual legal counsel.
Metric definitions and dashboard content — Document 5.
Build phase sequencing and current status — Document 6.
# 7. Change Log
v1.0 (original) — Initial security/legal/compliance framework, written for single-user/personal-capital scope. Flagged three required-but-unresolved items: (1) jurisdiction/entity/tax details, (2) FX Pesa/Equiti regulatory status verification, (3) Supabase backup tier confirmation. All three tracked forward into Document 6.

v1.1 (this document, 25 July 2026) — Documentation hardening pass:

Section 3.1 resolved: jurisdiction confirmed as Kenya, individual filer, currently NIL with KRA. Tax-consultation recommendation added ahead of Phase 5, non-blocking for earlier phases.
Section 3.3 resolved: broker regulatory structure confirmed and recorded — EGM Securities Ltd (CMA Kenya, License 107), Equiti Brokerage Seychelles Ltd (FSA, License SD064), Equiti Capital Ltd UK (FCA, Ref 528328). One residual sub-item flagged: confirming which specific entity holds the owner's actual account.
Corrected broken cross-reference: "Document 1, Section 'Part 2'" (a section that does not exist) corrected to Document 1, Section 2 (Business Context).
Removed stray header line referencing a "Section 0.1" — this document has no Section 0.1; that line was a copy-paste artifact from Document 3's header structure.
Section 2.1 (Backup Policy) updated to reflect the confirmed $0-budget decision (Document 3, Section 0.1 and Section 1): Supabase Free Tier has no automated backups, so manual export cadence is elevated from weekly to daily, with an explicit upgrade trigger back to weekly once Pro tier is reached.
Section 2.2 updated: external uptime monitor requirement elevated from a deferred "Phase 1/2" item to a hard Phase 1 sign-off requirement, matching Document 3, Section 6's corresponding update, given the increased blind-spot risk of the confirmed Linux+Wine, free-tier deployment.
Section 1.2 and Section 4.1 clarified: structural append-only enforcement (INSERT-only, no UPDATE/DELETE at the database level) explicitly extended to provisional-parameter-change logs and manual-intervention logs, not only trade/order tables — closes a gap where this was implied for audit tables but not explicitly stated for the other two log types.
Section 1.3 generalized from AWS-specific firewall language to provider-agnostic language, reflecting Document 3's Oracle-Cloud-primary/AWS-fallback hosting decision.
Section 4.3 raw tick-data retention period resolved (30–60 day rolling window) per Document 3, Section 3.3 — previously an open Phase 1 decision, now settled.
End of Document 4 v1.1.

text


---

**Verdict: approved — every change traces to a decision we made explicitly this session.** No new assumptions introduced.