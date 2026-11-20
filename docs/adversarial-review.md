# Adversarial Security Review: PatentPriorArtOracle

## 1. State Machine & Fund Transition Table

| State | Callable Methods | Caller | Pre-conditions | Next State | Custody & Fund Effects |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **UNINITIALIZED** | `__init__` | Deployer (Alice) | `min_novelty_bond_wei > 0` | `INITIALIZED` | All balances set to 0 wei. |
| **INITIALIZED** | `register_patent_claim_payable` | Any Inventor | `val >= min_bond`, valid URL & window | `REGISTERED` | `active_claim_bonds += bond`; surplus credited to `refundable_balances[inventor]`. |
| **INITIALIZED** | `register_patent_claim_payable` | Anyone | Invalid params or underpaid | `INITIALIZED` | Soft-fail: 100% of sent value credited to `refundable_balances[caller]`. |
| **REGISTERED** | `submit_prior_art_challenge_payable` | Any Challenger (not inventor) | `current_ts <= deadline`, `val >= bond` | `CHALLENGED` | `active_challenge_bonds += bond`; surplus credited to `refundable_balances[challenger]`. |
| **REGISTERED** | `submit_prior_art_challenge_payable` | Anyone | Late, self-challenge, underpaid | `REGISTERED` | Soft-fail: 100% of sent value credited to `refundable_balances[caller]`. |
| **REGISTERED** | `adjudicate_patent_novelty` | Anyone | `current_ts > challenge_deadline` | `ADJUDICATED` | Uncontested: 100% bond returned to `refundable_balances[inventor]`. |
| **CHALLENGED** | `adjudicate_patent_novelty` | Anyone | `current_ts > challenge_deadline` | `ADJUDICATED` | Consensus on 250-bps grid: bond pool routed to winner or refunded proportionally. |
| **REGISTERED / CHALLENGED** | `claim_expired_patent_refund` | Anyone | `current_ts >= adjudication_deadline` | `EXPIRED_REFUNDED` | 100% refund of active bonds to inventor and challenger. |
| **ANY** | `deposit_payable` | Anyone | Any value > 0 | Unchanged | 100% credited to `refundable_balances[caller]`. |
| **ANY** | `withdraw_refundable_balance` | Balance Owner | `refundable_balances[caller] > 0` | Unchanged | Debited and delivered via `IEoaRecipient(caller).emit_transfer`. Preserved if failed. |
| **ANY** | `withdraw` | Balance Owner | `amount <= balance` | Unchanged | Partial debit and delivery via `IEoaRecipient(caller).emit_transfer`. Preserved if failed. |

---

## 2. Liveness: Zero Stuck Funds Analysis

- **Inventor Bond Recovery:**
  - If no challenger submits a counter-citation, the inventor (or any caller) triggers `adjudicate_patent_novelty` after `challenge_deadline` to verify the filing and reclaim 100% of the bond.
  - If validators fail to finalize adjudication within `ADJUDICATION_TIMEOUT` (48 hours), anyone can trigger `claim_expired_patent_refund(claim_id)`, returning 100% of the novelty bond to the inventor's refundable balance.
- **Challenger Bond Recovery:**
  - If a challenge is filed, funds are adjudicated via validator consensus. If the citation is verified or partially overlaps, payouts are credited to `refundable_balances[challenger]`.
  - If adjudication times out, `claim_expired_patent_refund(claim_id)` returns 100% of the challenge bond to the challenger.
- **Abandoned States:**
  - Unfunded calls soft-fail and refund immediately.
  - Expired claims can never remain locked; any user can permissionlessly trigger `claim_expired_patent_refund`.

---

## 3. Race Conditions Between Competing Transitions

- **Challenge vs Adjudication:**
  - Challenge window guard: `current_ts <= claim.challenge_deadline_timestamp`.
  - Adjudication window guard: `state != "CHALLENGE_WINDOW_OPEN"` (requires `current_ts > claim.challenge_deadline_timestamp`).
  - The guards are mutually exclusive by timestamp comparison (`<=` vs `>`). A challenge cannot be submitted after adjudication becomes eligible, and adjudication cannot preempt a valid open challenge.
- **Adjudication vs Expired Refund:**
  - Adjudication requires `current_ts < claim.adjudication_deadline_timestamp`.
  - Expired refund requires `current_ts >= claim.adjudication_deadline_timestamp`.
  - Mutually exclusive. A late adjudication cannot overwrite an expired claim refund.
- **Withdrawal vs Delivery Failure:**
  - State is tentatively debited before transfer. If `IEoaRecipient.emit_transfer` raises an exception, state changes are cleanly reverted in the exception handler, preserving user funds intact.

---

## 4. Accounting Invariants

- **Custody Conservation Equation:**
  `native_custody_balance == active_claim_bonds + active_challenge_bonds + total_refundable_balances`
- **Zero Stranded Residue:**
  `stranded_residue_wei == 0` at all times.
- **Discrete Conservation:**
  Across all four verdicts (`NOVEL_CLAIM_CLEARED`, `PARTIAL_OVERLAP_AMEND`, `PRIOR_ART_INVALIDATED`, `EVIDENCE_UNAVAILABLE_FAIL_CLOSED`), the sum of inventor payout and challenger payout strictly equals `novelty_bond + challenge_bond`.

---

## 5. Input Validation

- Claim title: 3 to 120 characters, stripped.
- Claim fingerprint: 16 to 128 characters, stripped.
- URLs: 10 to 512 characters, strictly `http://` or `https://` prefix.
- Citation notes: 3 to 1000 characters.
- Challenge duration: Floor of 30 seconds, ceiling of 2,592,000 seconds (30 days).
- Adjudication timeout: 172,800 seconds (48 hours).
- Non-trapping soft-fail refund: Any validation failure returns 0 / False and credits 100% of incoming value to sender.

---

## 6. Consensus Safety & Equivalence Principle

- **Discrete 250-bps Grid:** Overlap similarity quantized to integer multiples of 250 bps (0, 250, 500, ..., 10000).
- **Deterministic Verdict Binding:**
  - `overlap_bps <= 2000`: `NOVEL_CLAIM_CLEARED`
  - `2000 < overlap_bps < 7000`: `PARTIAL_OVERLAP_AMEND`
  - `overlap_bps >= 7000`: `PRIOR_ART_INVALIDATED`
- **Fail-Closed Live Web Consensus:**
  - Live URLs fetched via `gl.nondet.web.render`.
  - If any required URL fails or returns under 32 characters, verdict is forced to `EVIDENCE_UNAVAILABLE_FAIL_CLOSED` with 100% bond refunds.
- **Prompt Injection Defense:** External text wrapped inside explicit data tags; clear system boundary instructions to ignore prompt instructions in external data.

---

## 7. Findings & Verification Matrix

| ID | Vulnerability / Requirement | Status | Verification Proof |
| :--- | :--- | :--- | :--- |
| SEC-01 | Trapping payable reverts | FIXED | `test_register_patent_claim_soft_fail_*` (10 tests) |
| SEC-02 | EOA transfer failure lockup | FIXED | `test_withdraw_delivery_failure_preserves_balance` |
| SEC-03 | Race between challenge and adjudication | FIXED | `test_adjudicate_reverts_if_challenge_window_still_open` |
| SEC-04 | Stuck funds on abandoned adjudication | FIXED | `test_claim_expired_patent_refund_*` (2 tests) |
| SEC-05 | Non-deterministic float similarity | FIXED | Quantized 250-bps integer grid in `adjudicate_patent_novelty` |
| SEC-06 | Web fetch failure desync | FIXED | Strict fail-closed logic tested in tests 27, 28, 29, 30 |
| SEC-07 | Stranded custody residue | FIXED | `test_comprehensive_multi_claim_zero_wei_conservation` |
