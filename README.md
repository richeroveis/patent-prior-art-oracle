# PatentPriorArtOracle

PatentPriorArtOracle is an Intelligent Contract on GenLayer that implements a decentralized, staked patent claim novelty and public prior-art audit registry. Inventors register patent specifications and novelty bonds alongside public filing URLs, while public challengers can submit counter-citations. Decentralized validators independently render external evidence, evaluate novelty overlap on a discrete 250-bps grid, and resolve bond distributions with zero stranded residue.

---

## Key Capabilities

1. **Staked Patent Claim Registration:**
   Inventors stake native GEN novelty collateral while recording patent claim titles, cryptographic specification fingerprints, and public filing reference URLs (e.g., USPTO, EPO, Google Patents, W3C).

2. **Public Prior-Art Challenges:**
   Third-party challengers can contest registered patent claims by staking matching novelty bonds and submitting documented prior-art citations within a deterministic challenge window.

3. **Fail-Closed Live Web Consensus:**
   Validators fetch external documentation independently via `gl.nondet.web.render`. If external evidence is unreachable, returns fewer than 32 characters, or fails to resolve, validators deterministically fail closed (`EVIDENCE_UNAVAILABLE_FAIL_CLOSED`), protecting all user funds by triggering full bond refunds.

4. **Discrete 250-bps Grid & Deterministic Payouts:**
   Prior-art overlap similarity is quantized to integer multiples of 250 basis points (0, 250, 500, ..., 10000 bps) inside `gl.nondet`, ensuring exact multi-validator consensus under the Equivalence Principle. Payouts are computed deterministically without floating-point drift.

5. **Strict Native GEN Custody Conservation:**
   Every wei deposited is strictly tracked. The contract enforces the invariant:
   `native_custody_balance == active_claim_bonds + active_challenge_bonds + total_refundable_balances`
   with zero wei stranded residue at all times.

6. **Non-Trapping Soft-Fail Payable Refunds:**
   To prevent unrecoverable reverts on payable calls, validation failures credit 100% of incoming value to the sender refundable balance for permissionless EOA withdrawal.

---

## 12 Steward Rules Compliance

| Rule | Requirement | Implementation in PatentPriorArtOracle |
| :--- | :--- | :--- |
| **Rule 1** | Pinned header & classic SDK | Pinned Line 1 header: `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`, imports `from genlayer import *`. LF file size under 24 KB (limit 37,500 bytes). |
| **Rule 2** | Zero backdoors | No admin roles, no privileged `_deterministic` bypasses, and zero `advance_clock` mock functions. |
| **Rule 3** | Custody balance conservation | `native_custody_balance` tracked on all deposits, payouts, refunds, and withdrawals. Exact invariant checked via `get_accounting_invariants()`. |
| **Rule 4** | Equivalence Principle consensus | Comparative consensus via `gl.eq_principle.prompt_comparative` matching exact structured validator outputs. |
| **Rule 5** | Unified state helper | Single `_compute_claim_state` helper used across views, writes, and adjudication. |
| **Rule 6** | Strict fail-closed web fetch | Validates external web pages via `gl.nondet.web.render`; fails closed if page length < 32 characters. |
| **Rule 7** | Non-reverting payable methods | Payable methods never trap unrecoverably; invalid calls credit value to sender refundable balance. |
| **Rule 8** | Real native GEN payouts | Claimant payouts executed via `IEoaRecipient.emit_transfer`, with rollback on transfer failure to protect balances. |
| **Rule 9** | Discrete quantized grid | Novelty similarity scores quantized onto a discrete 250-bps grid (0 to 10000 bps). |
| **Rule 10** | Liveness & expiry recovery | `claim_expired_patent_refund` allows 100% refund of inventor and challenger bonds after 48-hour timeout. |
| **Rule 11** | Bounded input validation | Strict character limits on titles, fingerprints, and URLs; floors and ceilings on challenge windows (30s to 30d). |
| **Rule 12** | Complete documentation & audit | Full adversarial review in `docs/adversarial-review.md` and live multi-signer evidence in `docs/deployment.md`. |

---

## Contract State Machine

```
              [ register_patent_claim_payable ]
                             │
                             ▼
                     ┌───────────────┐
                     │  REGISTERED   │
                     └───────┬───────┘
                             │
        ┌────────────────────┴────────────────────┐
        │ [submit_prior_art_challenge_payable]    │ [adjudicate_patent_novelty]
        ▼                                         │ (uncontested after deadline)
┌───────────────┐                                 ▼
│  CHALLENGED   │                         ┌───────────────┐
└───────┬───────┘                         │  ADJUDICATED  │
        │                                 └───────────────┘
        ├─────────────────────────────────────────▲
        │ [adjudicate_patent_novelty]             │
        │ (consensus on 250-bps grid)             │
        ▼                                         │
┌────────────────────────────────┐                │
│   claim_expired_patent_refund  │────────────────┘
│   (after 48-hour timeout)      │ (via EXPIRED_REFUNDED)
└────────────────────────────────┘
```

---

## On-Chain Deployment & Live Studionet Evidence

- **Contract Address:** `0xBe0BeaBE22e12Fc7C218026002d930A73cB7Dc43`
- **Deploy Transaction Hash:** `0x162450ca25394b22b4bf02600c6c05bbc1a2671a9482b9fbdb40130e2ea5771f`
- **Network:** GenLayer Studionet (Chain ID: `61999`, RPC: `https://studio.genlayer.com/api`)
- **Deployer (Alice):** `0x154a452b0755EE812014C1405B15D905BA06f9c7`
- **Challenger (Bob):** `0x1A2C7dF16f7800d0493959461edE7bEff385b7cd`
- **Source LF SHA-256:** `c28f16d17cb4a2420d7f17da0d98a3c467fb2078fd1cbbc61019b1add422f760`

### Multi-Signer Lifecycle Summary

1. **Deploy:** Contract initialized with 0.001 GEN minimum novelty bond (Tx: `0x162450ca25394b22b4bf02600c6c05bbc1a2671a9482b9fbdb40130e2ea5771f`, FINALIZED).
2. **Soft-fail Refund:** Payable deposit with invalid input credited 100 wei to refundable balance (Tx: `0x1f10d5a6d766751fe47b497c50cf0822987630eda73d5b0ec8491d1538c14253`, FINALIZED).
3. **EOA Withdrawal:** Refundable balance safely transferred to caller EOA (Tx: `0x452567215f94568ed19673f6ceac4658cc684dac7d70d94588607265afc7d3a7`, FINALIZED).
4. **Patent Registration:** Alice registered Claim 1 with 0.001 GEN bond (Tx: `0x2f9f2f9977ac305f41a0f751eaff79c7f8e146ec233cceb79c6599630f8768ed`, FINALIZED).
5. **Prior-Art Challenge:** Bob submitted prior-art challenge with 0.001 GEN bond (Tx: `0x61ec45a767ff7777293dc1524aab98c6b87505f4db9826913de5105d245d44d4`, FINALIZED).
6. **Consensus Adjudication:** Multi-validator consensus finalized novelty adjudication (Tx: `0xeb936c92940236fe352849a6fd00892447eda966c2e6d4bc55c459db0f890cf7`, FINALIZED).
7. **Conservation Verified:** `is_conserved = True`, `stranded_residue_wei = 0`.

For full transaction logs and consensus breakdown, see [docs/deployment.md](docs/deployment.md).
For the adversarial security audit, see [docs/adversarial-review.md](docs/adversarial-review.md).

---

## Testing & Quality Gates

### GenVM Static Linter
```bash
genvm-lint check contracts/patent_prior_art_oracle.py
```
Output: 0 errors detected across 13 contract methods.

### Test Suite Execution
```bash
python -m pytest tests/ -q
```
Output: 50 passed in direct mode test suite covering registration, challenges, web render failure, 250-bps quantization, bond routing, soft-fail refunds, and custody conservation.
