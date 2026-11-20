# Unit and direct integration tests for PatentPriorArtOracle
# Covers patent registration, prior-art challenges, fail-closed web fetching,
# 250-bps grid consensus, bond routing, soft-fail payable refunds, EOA payouts,
# expired refunds, and 0-wei custody residue conservation.

import json
import pytest
from genlayer.py.types import Address, u256


MIN_BOND = 1000000000000000  # 0.001 GEN
VALID_FILING_URL = "https://patents.google.com/patent/US10987654B2/en"
VALID_PRIOR_ART_URL = "https://patents.google.com/patent/US9876543B1/en"
VALID_TITLE = "Zero-Knowledge Rollup State Verification System"
VALID_FP = "0x9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
FILING_BODY = "PATENT FILING SPECIFICATION: A zero knowledge proof verification mechanism for decentralized state rollups with recursive SNARK proofs."
PRIOR_ART_BODY = "PRIOR ART CITATION: An earlier system verifying batch state transitions using cryptographic validity proofs on distributed ledgers."


def deploy_oracle(direct_deploy, direct_vm, direct_alice, bond=MIN_BOND):
    direct_vm.sender = direct_alice
    direct_vm.value = 0
    direct_vm.warp("2026-11-20T12:00:00Z")
    contract = direct_deploy("contracts/patent_prior_art_oracle.py", u256(bond))
    return contract


def assert_custody_conservation(contract):
    invariants = contract.get_accounting_invariants()
    assert invariants["is_conserved"] is True, f"Conservation violated: {invariants}"
    assert invariants["stranded_residue_wei"] == 0, f"Stranded residue: {invariants}"
    assert invariants["native_custody_balance_wei"] == invariants["expected_sum_wei"]


# 1. Initial deployment state
def test_initial_deployment_state(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    assert contract.get_min_novelty_bond() == u256(MIN_BOND)
    assert contract.get_claim_count() == u256(0)
    inv = contract.get_accounting_invariants()
    assert inv["native_custody_balance_wei"] == 0
    assert inv["active_claim_bonds_wei"] == 0
    assert inv["active_challenge_bonds_wei"] == 0
    assert inv["total_refundable_balances_wei"] == 0
    assert_custody_conservation(contract)


# 2. Constructor rejects zero bond
def test_constructor_rejects_zero_bond(direct_vm, direct_deploy, direct_alice):
    with direct_vm.expect_revert("Minimum novelty bond must be positive"):
        direct_deploy("contracts/patent_prior_art_oracle.py", u256(0))


# 3. Patent registration happy path
def test_register_patent_claim_happy_path(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND

    cid = contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))
    assert cid == u256(1)
    assert contract.get_claim_count() == u256(1)

    c = contract.get_claim(u256(1))
    assert c["claim_title"] == VALID_TITLE
    assert c["novelty_bond_wei"] == MIN_BOND
    assert c["status"] == "REGISTERED"
    assert c["has_challenger"] is False
    assert_custody_conservation(contract)


# 4. Patent registration surplus refund
def test_register_patent_claim_surplus_refund(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND * 3  # Surplus of 2 * MIN_BOND

    cid = contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))
    assert cid == u256(1)

    refund = contract.get_refundable_balance(direct_alice)
    assert refund == u256(MIN_BOND * 2)

    inv = contract.get_accounting_invariants()
    assert inv["active_claim_bonds_wei"] == MIN_BOND
    assert inv["total_refundable_balances_wei"] == MIN_BOND * 2
    assert inv["native_custody_balance_wei"] == MIN_BOND * 3
    assert_custody_conservation(contract)


# 5. Soft-fail underpaid registration
def test_register_patent_claim_soft_fail_underpaid(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND - 1

    cid = contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))
    assert cid == u256(0)
    assert contract.get_claim_count() == u256(0)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND - 1)
    assert_custody_conservation(contract)


# 6. Soft-fail title too short
def test_register_patent_claim_soft_fail_title_too_short(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND

    cid = contract.register_patent_claim_payable("AB", VALID_FP, VALID_FILING_URL, u256(600))
    assert cid == u256(0)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 7. Soft-fail title too long
def test_register_patent_claim_soft_fail_title_too_long(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND

    cid = contract.register_patent_claim_payable("A" * 121, VALID_FP, VALID_FILING_URL, u256(600))
    assert cid == u256(0)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 8. Soft-fail fingerprint too short
def test_register_patent_claim_soft_fail_fingerprint_too_short(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND

    cid = contract.register_patent_claim_payable(VALID_TITLE, "0x12345", VALID_FILING_URL, u256(600))
    assert cid == u256(0)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 9. Soft-fail fingerprint too long
def test_register_patent_claim_soft_fail_fingerprint_too_long(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND

    cid = contract.register_patent_claim_payable(VALID_TITLE, "0x" + "a" * 128, VALID_FILING_URL, u256(600))
    assert cid == u256(0)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 10. Soft-fail URL too short
def test_register_patent_claim_soft_fail_url_too_short(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND

    cid = contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, "http://a", u256(600))
    assert cid == u256(0)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 11. Soft-fail URL too long
def test_register_patent_claim_soft_fail_url_too_long(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND

    cid = contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, "https://example.com/" + "u" * 500, u256(600))
    assert cid == u256(0)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 12. Soft-fail invalid URL scheme
def test_register_patent_claim_soft_fail_invalid_url_scheme(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND

    cid = contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, "ftp://example.com/patent.pdf", u256(600))
    assert cid == u256(0)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 13. Soft-fail challenge window below floor
def test_register_patent_claim_soft_fail_challenge_window_below_floor(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND

    cid = contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(29))
    assert cid == u256(0)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 14. Soft-fail challenge window above ceiling
def test_register_patent_claim_soft_fail_challenge_window_above_ceiling(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND

    cid = contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(2592001))
    assert cid == u256(0)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 15. Multiple claims increment counter
def test_multiple_claims_registration_increments_counter(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)

    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    c1 = contract.register_patent_claim_payable("Title 1", VALID_FP, VALID_FILING_URL, u256(100))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND
    c2 = contract.register_patent_claim_payable("Title 2", VALID_FP, VALID_FILING_URL, u256(200))

    assert c1 == u256(1)
    assert c2 == u256(2)
    assert contract.get_claim_count() == u256(2)
    assert_custody_conservation(contract)


# 16. Prior-art challenge happy path
def test_submit_prior_art_challenge_happy_path(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND
    ok = contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "Invalidated by US9876543B1")
    assert ok is True

    c = contract.get_claim(u256(1))
    assert c["status"] == "CHALLENGED"
    assert c["has_challenger"] is True
    assert c["challenger"].lower() == f"0x{direct_bob.hex().lower()}"
    assert c["challenge_bond_wei"] == MIN_BOND
    assert_custody_conservation(contract)


# 17. Prior-art challenge surplus refund
def test_submit_prior_art_challenge_surplus_refund(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND * 2  # Surplus of MIN_BOND
    ok = contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "Valid challenge notes")
    assert ok is True

    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 18. Challenge soft-fail non-existent claim
def test_submit_prior_art_challenge_soft_fail_nonexistent_claim(direct_vm, direct_deploy, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_bob)
    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND

    ok = contract.submit_prior_art_challenge_payable(u256(999), VALID_PRIOR_ART_URL, "Notes")
    assert ok is False
    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 19. Challenge soft-fail already challenged
def test_submit_prior_art_challenge_soft_fail_already_challenged(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND
    contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "First challenge")

    direct_vm.sender = direct_charlie
    direct_vm.value = MIN_BOND
    ok2 = contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "Second challenge")
    assert ok2 is False
    assert contract.get_refundable_balance(direct_charlie) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 20. Challenge soft-fail inventor self-challenge
def test_submit_prior_art_challenge_soft_fail_inventor_self_challenge(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))

    # Alice attempts to challenge her own claim
    direct_vm.value = MIN_BOND
    ok = contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "Self challenge attempt")
    assert ok is False
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 21. Challenge soft-fail underpaid
def test_submit_prior_art_challenge_soft_fail_underpaid(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND - 10
    ok = contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "Underpaid attempt")
    assert ok is False
    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND - 10)
    assert_custody_conservation(contract)


# 22. Challenge soft-fail after deadline
def test_submit_prior_art_challenge_soft_fail_after_challenge_deadline(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(100))

    # Warp past deadline (100 seconds)
    direct_vm.warp("2026-11-20T12:02:00Z")

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND
    ok = contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "Late challenge attempt")
    assert ok is False
    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 23. Challenge soft-fail invalid URL
def test_submit_prior_art_challenge_soft_fail_invalid_url(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND
    ok = contract.submit_prior_art_challenge_payable(u256(1), "invalid-url", "Notes")
    assert ok is False
    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 24. Challenge soft-fail invalid citation notes
def test_submit_prior_art_challenge_soft_fail_invalid_citation_notes(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND
    ok = contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "no")  # < 3 chars
    assert ok is False
    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 25. Adjudicate reverts if challenge window still open
def test_adjudicate_reverts_if_challenge_window_still_open(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(600))

    with direct_vm.expect_revert("Challenge window is still open; cannot adjudicate yet"):
        contract.adjudicate_patent_novelty(u256(1))


# 26. Adjudicate uncontested claim cleared
def test_adjudicate_uncontested_claim_cleared(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    # Warp past challenge window
    direct_vm.warp("2026-11-20T12:01:30Z")
    direct_vm.mock_web(r".*patents\.google\.com.*", {"body": FILING_BODY})

    res = contract.adjudicate_patent_novelty(u256(1))
    assert res["verdict"] == "NOVEL_CLAIM_CLEARED"
    assert res["sources_verified"] is True
    assert res["inventor_payout_wei"] == MIN_BOND
    assert res["challenger_payout_wei"] == 0

    c = contract.get_claim(u256(1))
    assert c["status"] == "ADJUDICATED"
    assert c["novelty_verdict"] == "NOVEL_CLAIM_CLEARED"
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 27. Adjudicate uncontested fail-closed when filing unreachable
def test_adjudicate_uncontested_fail_closed_filing_unreachable(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    direct_vm.warp("2026-11-20T12:01:30Z")
    # No web mock registered: render will fail

    res = contract.adjudicate_patent_novelty(u256(1))
    assert res["verdict"] == "EVIDENCE_UNAVAILABLE_FAIL_CLOSED"
    assert res["sources_verified"] is False
    assert res["inventor_payout_wei"] == MIN_BOND
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 28. Adjudicate uncontested fail-closed when filing returns < 32 chars
def test_adjudicate_uncontested_fail_closed_filing_too_short(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    direct_vm.warp("2026-11-20T12:01:30Z")
    direct_vm.mock_web(r".*patents\.google\.com.*", {"body": "Short filing text"})  # < 32 chars

    res = contract.adjudicate_patent_novelty(u256(1))
    assert res["verdict"] == "EVIDENCE_UNAVAILABLE_FAIL_CLOSED"
    assert res["sources_verified"] is False
    assert res["inventor_payout_wei"] == MIN_BOND
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 29. Adjudicate challenged fail-closed when prior art unreachable
def test_adjudicate_challenged_fail_closed_prior_art_unreachable(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND
    contract.submit_prior_art_challenge_payable(u256(1), "https://unreachable.priorart.org/citation", "Citing prior art")

    direct_vm.warp("2026-11-20T12:01:30Z")
    # Mock only filing URL, leave prior art URL unmocked
    direct_vm.mock_web(r".*patents\.google\.com.*", {"body": FILING_BODY})

    res = contract.adjudicate_patent_novelty(u256(1))
    assert res["verdict"] == "EVIDENCE_UNAVAILABLE_FAIL_CLOSED"
    assert res["sources_verified"] is False
    assert res["inventor_payout_wei"] == MIN_BOND
    assert res["challenger_payout_wei"] == MIN_BOND
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 30. Adjudicate challenged fail-closed when prior art < 32 chars
def test_adjudicate_challenged_fail_closed_prior_art_too_short(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND
    contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "Citing prior art")

    direct_vm.warp("2026-11-20T12:01:30Z")
    direct_vm.mock_web(r".*US10987654B2.*", {"body": FILING_BODY})
    direct_vm.mock_web(r".*US9876543B1.*", {"body": "Too short"})

    res = contract.adjudicate_patent_novelty(u256(1))
    assert res["verdict"] == "EVIDENCE_UNAVAILABLE_FAIL_CLOSED"
    assert res["sources_verified"] is False
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# Helper to run challenged adjudication with given mocked LLM response
def run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, llm_overlap_bps):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND
    contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "Counter citation")

    direct_vm.warp("2026-11-20T12:01:30Z")
    direct_vm.mock_web(r".*US10987654B2.*", {"body": FILING_BODY})
    direct_vm.mock_web(r".*US9876543B1.*", {"body": PRIOR_ART_BODY})

    mock_resp = json.dumps({
        "verdict": "IGNORED_WILL_BE_DERIVED",
        "overlap_bps": llm_overlap_bps,
        "rationale": f"Adjudication test for overlap {llm_overlap_bps}"
    })
    direct_vm.mock_llm(r".*patent claim examiner.*", mock_resp)

    res = contract.adjudicate_patent_novelty(u256(1))
    return contract, res


# 31. Verdict NOVEL_CLAIM_CLEARED (0 bps)
def test_adjudicate_verdict_novel_claim_cleared_grid_0_bps(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, res = run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, 0)
    assert res["verdict"] == "NOVEL_CLAIM_CLEARED"
    assert res["overlap_bps"] == 0
    assert res["inventor_payout_wei"] == MIN_BOND * 2
    assert res["challenger_payout_wei"] == 0
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND * 2)
    assert contract.get_refundable_balance(direct_bob) == u256(0)
    assert_custody_conservation(contract)


# 32. Verdict NOVEL_CLAIM_CLEARED (250 bps)
def test_adjudicate_verdict_novel_claim_cleared_grid_250_bps(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, res = run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, 250)
    assert res["verdict"] == "NOVEL_CLAIM_CLEARED"
    assert res["overlap_bps"] == 250
    assert res["inventor_payout_wei"] == MIN_BOND * 2
    assert res["challenger_payout_wei"] == 0
    assert_custody_conservation(contract)


# 33. Verdict NOVEL_CLAIM_CLEARED at upper boundary (2000 bps)
def test_adjudicate_verdict_novel_claim_cleared_boundary_2000_bps(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, res = run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, 2000)
    assert res["verdict"] == "NOVEL_CLAIM_CLEARED"
    assert res["overlap_bps"] == 2000
    assert res["inventor_payout_wei"] == MIN_BOND * 2
    assert res["challenger_payout_wei"] == 0
    assert_custody_conservation(contract)


# 34. Verdict PARTIAL_OVERLAP_AMEND at lower boundary (2250 bps)
def test_adjudicate_verdict_partial_overlap_boundary_2250_bps(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, res = run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, 2250)
    assert res["verdict"] == "PARTIAL_OVERLAP_AMEND"
    assert res["overlap_bps"] == 2250
    assert res["inventor_payout_wei"] == MIN_BOND
    assert res["challenger_payout_wei"] == MIN_BOND
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 35. Verdict PARTIAL_OVERLAP_AMEND mid grid (5000 bps)
def test_adjudicate_verdict_partial_overlap_mid_grid_5000_bps(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, res = run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, 5000)
    assert res["verdict"] == "PARTIAL_OVERLAP_AMEND"
    assert res["overlap_bps"] == 5000
    assert res["inventor_payout_wei"] == MIN_BOND
    assert res["challenger_payout_wei"] == MIN_BOND
    assert_custody_conservation(contract)


# 36. Verdict PARTIAL_OVERLAP_AMEND upper boundary (6750 bps)
def test_adjudicate_verdict_partial_overlap_boundary_6750_bps(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, res = run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, 6750)
    assert res["verdict"] == "PARTIAL_OVERLAP_AMEND"
    assert res["overlap_bps"] == 6750
    assert res["inventor_payout_wei"] == MIN_BOND
    assert res["challenger_payout_wei"] == MIN_BOND
    assert_custody_conservation(contract)


# 37. Verdict PRIOR_ART_INVALIDATED lower boundary (7000 bps)
def test_adjudicate_verdict_prior_art_invalidated_boundary_7000_bps(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, res = run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, 7000)
    assert res["verdict"] == "PRIOR_ART_INVALIDATED"
    assert res["overlap_bps"] == 7000
    assert res["inventor_payout_wei"] == 0
    assert res["challenger_payout_wei"] == MIN_BOND * 2
    assert contract.get_refundable_balance(direct_alice) == u256(0)
    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND * 2)
    assert_custody_conservation(contract)


# 38. Verdict PRIOR_ART_INVALIDATED mid grid (8500 bps)
def test_adjudicate_verdict_prior_art_invalidated_grid_8500_bps(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, res = run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, 8500)
    assert res["verdict"] == "PRIOR_ART_INVALIDATED"
    assert res["overlap_bps"] == 8500
    assert res["inventor_payout_wei"] == 0
    assert res["challenger_payout_wei"] == MIN_BOND * 2
    assert_custody_conservation(contract)


# 39. Verdict PRIOR_ART_INVALIDATED max grid (10000 bps)
def test_adjudicate_verdict_prior_art_invalidated_grid_10000_bps(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, res = run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, 10000)
    assert res["verdict"] == "PRIOR_ART_INVALIDATED"
    assert res["overlap_bps"] == 10000
    assert res["inventor_payout_wei"] == 0
    assert res["challenger_payout_wei"] == MIN_BOND * 2
    assert_custody_conservation(contract)


# 40. Arbitrary bps quantized to 250-bps grid
def test_adjudicate_quantizes_arbitrary_bps_to_250_grid(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, res = run_challenged_case(direct_vm, direct_deploy, direct_alice, direct_bob, 3141)
    # 3141 rounds to 3250
    assert res["overlap_bps"] == 3250
    assert res["verdict"] == "PARTIAL_OVERLAP_AMEND"
    assert_custody_conservation(contract)


# 41. Adjudicate reverts if adjudication deadline passed
def test_adjudicate_reverts_if_adjudication_deadline_passed(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    # Warp past adjudication deadline (60s + 172800s = 48h 1m)
    direct_vm.warp("2026-11-23T12:00:00Z")

    with direct_vm.expect_revert("Adjudication deadline has passed; claim must be refunded via claim_expired_patent_refund"):
        contract.adjudicate_patent_novelty(u256(1))


# 42. Adjudicate reverts if already resolved
def test_adjudicate_reverts_if_already_resolved(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    direct_vm.warp("2026-11-20T12:01:30Z")
    direct_vm.mock_web(r".*patents\.google\.com.*", {"body": FILING_BODY})
    contract.adjudicate_patent_novelty(u256(1))

    with direct_vm.expect_revert("Claim has already been resolved"):
        contract.adjudicate_patent_novelty(u256(1))


# 43. Expired refund uncontested claim
def test_claim_expired_patent_refund_uncontested(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    direct_vm.warp("2026-11-23T12:00:00Z")
    ok = contract.claim_expired_patent_refund(u256(1))
    assert ok is True

    c = contract.get_claim(u256(1))
    assert c["status"] == "EXPIRED_REFUNDED"
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 44. Expired refund challenged claim
def test_claim_expired_patent_refund_challenged(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND
    contract.submit_prior_art_challenge_payable(u256(1), VALID_PRIOR_ART_URL, "Notes")

    direct_vm.warp("2026-11-23T12:00:00Z")
    ok = contract.claim_expired_patent_refund(u256(1))
    assert ok is True

    c = contract.get_claim(u256(1))
    assert c["status"] == "EXPIRED_REFUNDED"
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND)
    assert contract.get_refundable_balance(direct_bob) == u256(MIN_BOND)
    assert_custody_conservation(contract)


# 45. Expired refund reverts if not expired
def test_claim_expired_patent_refund_reverts_if_not_expired(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))

    with direct_vm.expect_revert("is not expired"):
        contract.claim_expired_patent_refund(u256(1))


# 46. Deposit payable and full withdrawal
def test_deposit_and_withdraw_refundable_balance(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND * 5

    dep = contract.deposit_payable()
    assert dep == u256(MIN_BOND * 5)
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND * 5)
    assert_custody_conservation(contract)

    direct_vm._gl_call_hook = lambda vm, req: {"ok": None}
    with direct_vm.prank(direct_alice):
        withdrew = contract.withdraw_refundable_balance()
        assert withdrew == u256(MIN_BOND * 5)

    assert contract.get_refundable_balance(direct_alice) == u256(0)
    assert_custody_conservation(contract)


# 47. Partial withdrawal
def test_partial_withdraw(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND * 10
    contract.deposit_payable()

    direct_vm._gl_call_hook = lambda vm, req: {"ok": None}
    with direct_vm.prank(direct_alice):
        withdrew = contract.withdraw(u256(MIN_BOND * 4))
        assert withdrew == u256(MIN_BOND * 4)

    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND * 6)
    assert_custody_conservation(contract)


# 48. Withdraw fails on zero or exceeding balance
def test_withdraw_fails_when_zero_or_exceeding(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("No refundable balance available"):
        contract.withdraw_refundable_balance()

    with direct_vm.expect_revert("Insufficient refundable balance"):
        contract.withdraw(u256(100))


# 49. Withdrawal delivery failure preserves balance intact
def test_withdraw_delivery_failure_preserves_balance(direct_vm, direct_deploy, direct_alice):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND * 2
    contract.deposit_payable()

    def failing_hook(vm, req):
        raise RuntimeError("RPC simulated transfer failure")

    direct_vm._gl_call_hook = failing_hook

    with direct_vm.prank(direct_alice):
        with direct_vm.expect_revert("Native transfer delivery failed; refundable balance preserved intact"):
            contract.withdraw_refundable_balance()

    # Balance remains intact!
    assert contract.get_refundable_balance(direct_alice) == u256(MIN_BOND * 2)
    assert_custody_conservation(contract)


# 50. Comprehensive multi-claim zero-wei conservation
def test_comprehensive_multi_claim_zero_wei_conservation(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = deploy_oracle(direct_deploy, direct_vm, direct_alice)
    direct_vm._gl_call_hook = lambda vm, req: {"ok": None}

    # Alice deposits
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND * 5
    contract.deposit_payable()
    assert_custody_conservation(contract)

    # Bob soft-fails
    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND // 2
    contract.register_patent_claim_payable("Bad", VALID_FP, VALID_FILING_URL, u256(60))
    assert_custody_conservation(contract)

    # Charlie registers valid claim
    direct_vm.sender = direct_charlie
    direct_vm.value = MIN_BOND * 2  # Surplus
    c1 = contract.register_patent_claim_payable(VALID_TITLE, VALID_FP, VALID_FILING_URL, u256(60))
    assert_custody_conservation(contract)

    # Alice challenges Charlie
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND
    contract.submit_prior_art_challenge_payable(c1, VALID_PRIOR_ART_URL, "Prior art cited")
    assert_custody_conservation(contract)

    # Adjudicate
    direct_vm.warp("2026-11-20T12:01:30Z")
    direct_vm.mock_web(r".*US10987654B2.*", {"body": FILING_BODY})
    direct_vm.mock_web(r".*US9876543B1.*", {"body": PRIOR_ART_BODY})
    direct_vm.mock_llm(r".*", json.dumps({"verdict": "IGNORED", "overlap_bps": 5000, "rationale": "partial overlap"}))
    contract.adjudicate_patent_novelty(c1)
    assert_custody_conservation(contract)

    # Alice withdraws partial
    with direct_vm.prank(direct_alice):
        contract.withdraw(u256(MIN_BOND))
    assert_custody_conservation(contract)

    final_inv = contract.get_accounting_invariants()
    assert final_inv["is_conserved"] is True
    assert final_inv["stranded_residue_wei"] == 0
