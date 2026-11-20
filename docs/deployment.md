# Studionet Deployment & Live Evidence: PatentPriorArtOracle

## Overview

The `PatentPriorArtOracle` intelligent contract was deployed and verified on GenLayer Studionet. A complete multi-signer lifecycle was executed across two distinct accounts: Alice (Inventor) and Bob (Challenger).

- **Network:** GenLayer Studionet
- **RPC Endpoint:** `https://studio.genlayer.com/api`
- **Chain ID:** `61999`
- **Contract Address:** `0xBe0BeaBE22e12Fc7C218026002d930A73cB7Dc43`
- **Contract Source File:** `contracts/patent_prior_art_oracle.py`
- **Contract LF SHA-256:** `c28f16d17cb4a2420d7f17da0d98a3c467fb2078fd1cbbc61019b1add422f760`
- **Deployer (Alice):** `0x154a452b0755EE812014C1405B15D905BA06f9c7`
- **Challenger (Bob):** `0x1A2C7dF16f7800d0493959461edE7bEff385b7cd`

---

## On-Chain Lifecycle Transactions

All transactions below reached status `FINALIZED` (Status 7) with multi-validator consensus on Studionet.

| Step | Function | Caller | Transaction Hash | Status | Details / Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Deployment | Alice | `0x162450ca25394b22b4bf02600c6c05bbc1a2671a9482b9fbdb40130e2ea5771f` | FINALIZED | Deployed at `0xBe0BeaBE22e12Fc7C218026002d930A73cB7Dc43` |
| 2 | `register_patent_claim_payable` (Invalid) | Alice | `0x1f10d5a6d766751fe47b497c50cf0822987630eda73d5b0ec8491d1538c14253` | FINALIZED | Non-trapping soft-fail: credited 100 wei to `refundable_balances` |
| 3 | `withdraw_refundable_balance` | Alice | `0x452567215f94568ed19673f6ceac4658cc684dac7d70d94588607265afc7d3a7` | FINALIZED | EOA withdrawal delivery: balance drained to 0 wei |
| 4 | `register_patent_claim_payable` | Alice | `0x2f9f2f9977ac305f41a0f751eaff79c7f8e146ec233cceb79c6599630f8768ed` | FINALIZED | Registered Claim 1 with 0.001 GEN bond |
| 5 | `submit_prior_art_challenge_payable` | Bob | `0x61ec45a767ff7777293dc1524aab98c6b87505f4db9826913de5105d245d44d4` | FINALIZED | Prior-art challenge submitted with 0.001 GEN bond |
| 6 | `adjudicate_patent_novelty` | Alice | `0xeb936c92940236fe352849a6fd00892447eda966c2e6d4bc55c459db0f890cf7` | FINALIZED | Fail-closed consensus reached (`MAJORITY_AGREE`) |

---

## Validator Consensus Detail

Adjudication Transaction: `0xeb936c92940236fe352849a6fd00892447eda966c2e6d4bc55c459db0f890cf7`

Validator Votes:
- `0x4eeaD269a60bB89c98a23c1BCd0bd101CafD90E0`: `agree`
- `0x6fe9DE3d0adc76D6416A13CD8107aaE49A3CF98F`: `agree`
- `0x813890bC5bEDEB4F5437570962379F04738F18Cb`: `agree`
- `0x1B490819e040562a5fb40CD64B1c70D4419c38d1`: `idle`
- `0x725Ab89db6A9DD886Ba71Bc5E63a01070C325bE3`: `idle`

Resulting State for Claim 1:
- **Status:** `ADJUDICATED`
- **Novelty Verdict:** `EVIDENCE_UNAVAILABLE_FAIL_CLOSED`
- **Overlap BPS:** `0`
- **Sources Verified:** `False`
- **Inventor Payout:** `1000000000000000` wei (0.001 GEN)
- **Challenger Payout:** `0` wei

---

## Accounting Invariant Verification

On-chain accounting invariants verified after all steps:
- `native_custody_balance_wei`: `2000000000000000` wei (0.002 GEN)
- `active_claim_bonds_wei`: `0` wei
- `active_challenge_bonds_wei`: `0` wei
- `total_refundable_balances_wei`: `2000000000000000` wei (0.002 GEN)
- `is_conserved`: `True`
- `stranded_residue_wei`: `0` wei
