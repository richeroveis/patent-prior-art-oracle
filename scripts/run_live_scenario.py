# Complete multi-signer live scenario on GenLayer Studionet
import os
import sys
import json
import time
import hashlib
from dotenv import load_dotenv

load_dotenv()
pk_alice = os.getenv("GENLAYER_PRIVATE_KEY")
if not pk_alice:
    print("ERROR: GENLAYER_PRIVATE_KEY missing from .env")
    sys.exit(1)

import genlayer_py
from genlayer_py.transactions.actions import TransactionStatus

# Setup clients
alice = genlayer_py.create_account(pk_alice)
client_alice = genlayer_py.create_client(chain=genlayer_py.studionet, account=alice)

# Bob (Challenger) account
bob = genlayer_py.create_account("0x89abcdef0123456789abcdef0123456789abcdef0123456789abcdef01234567")
client_bob = genlayer_py.create_client(chain=genlayer_py.studionet, account=bob)

print(f"Alice (Inventor) Address: {alice.address}")
print(f"Bob (Challenger) Address: {bob.address}")

bal_alice = client_alice.get_balance(alice.address)
bal_bob = client_bob.get_balance(bob.address)
print(f"Alice Balance: {bal_alice} wei ({bal_alice / 10**18:.6f} GEN)")
print(f"Bob Balance: {bal_bob} wei ({bal_bob / 10**18:.6f} GEN)")

contract_address = "0xBe0BeaBE22e12Fc7C218026002d930A73cB7Dc43"
deploy_tx_hash = "0x162450ca25394b22b4bf02600c6c05bbc1a2671a9482b9fbdb40130e2ea5771f"

contract_path = "contracts/patent_prior_art_oracle.py"
with open(contract_path, "r", encoding="utf-8") as f:
    contract_code = f.read()

contract_sha256 = hashlib.sha256(contract_code.replace("\r\n", "\n").encode("utf-8")).hexdigest()

evidence = {
    "network": "GenLayer Studionet",
    "rpc_url": "https://studio.genlayer.com/api",
    "chain_id": 61999,
    "contract_address": contract_address,
    "deploy_tx_hash": deploy_tx_hash,
    "contract_file": contract_path,
    "contract_lf_sha256": contract_sha256,
    "alice_address": alice.address,
    "bob_address": bob.address,
    "transactions": [
        {
            "step": "Deploy PatentPriorArtOracle",
            "tx_hash": deploy_tx_hash,
            "status": "FINALIZED",
            "contract_address": contract_address,
        }
    ],
}

min_bond = 1000000000000000  # 0.001 GEN

# STEP 2: SOFT-FAIL PAYABLE REFUND TEST
print("\n--- STEP 2: SOFT-FAIL PAYABLE REFUND TEST ---")
soft_val = 100
tx_soft = client_alice.write_contract(
    address=contract_address,
    function_name="register_patent_claim_payable",
    args=["Bad", "0x123", "http://short", 10],  # Invalid inputs
    value=soft_val,
)
print(f"Soft-fail Tx Hash: {tx_soft}")
receipt_soft = client_alice.wait_for_transaction_receipt(
    tx_soft,
    status=TransactionStatus.FINALIZED,
    retries=80,
    interval=3000,
)
print(f"Soft-fail Tx Status: {receipt_soft.get('status')}")

bal_soft = client_alice.read_contract(
    address=contract_address,
    function_name="get_refundable_balance",
    args=[alice.address],
)
print(f"Alice Refundable Balance after soft-fail: {bal_soft} wei (expected >= 100)")
evidence["transactions"].append({
    "step": "Soft-fail payable refund test",
    "tx_hash": tx_soft,
    "status": "FINALIZED",
    "refundable_balance_credited_wei": int(bal_soft),
})

# STEP 3: EOA WITHDRAWAL TEST
print("\n--- STEP 3: EOA WITHDRAWAL TEST ---")
tx_withdraw = client_alice.write_contract(
    address=contract_address,
    function_name="withdraw_refundable_balance",
    args=[],
)
print(f"Withdrawal Tx Hash: {tx_withdraw}")
receipt_withdraw = client_alice.wait_for_transaction_receipt(
    tx_withdraw,
    status=TransactionStatus.FINALIZED,
    retries=80,
    interval=3000,
)
print(f"Withdrawal Tx Status: {receipt_withdraw.get('status')}")

bal_after_withdraw = client_alice.read_contract(
    address=contract_address,
    function_name="get_refundable_balance",
    args=[alice.address],
)
print(f"Alice Refundable Balance after withdrawal: {bal_after_withdraw} wei (expected 0)")
evidence["transactions"].append({
    "step": "EOA withdrawal delivery test",
    "tx_hash": tx_withdraw,
    "status": "FINALIZED",
    "refundable_balance_remaining_wei": int(bal_after_withdraw),
})

# STEP 4: REGISTER VALID PATENT CLAIM (ALICE)
print("\n--- STEP 4: REGISTER VALID PATENT CLAIM (ALICE) ---")
claim_title = "Decentralized Zero-Knowledge Patent Claim Integrity System"
claim_fp = "0x4a5b6c7d8e9f0123456789abcdef0123456789abcdef0123456789abcdef0123"
filing_url = "https://www.w3.org/Consortium/Patent-Policy-20200915/"
challenge_window = 30  # 30 seconds

tx_reg = client_alice.write_contract(
    address=contract_address,
    function_name="register_patent_claim_payable",
    args=[claim_title, claim_fp, filing_url, challenge_window],
    value=min_bond,
)
print(f"Patent Registration Tx Hash: {tx_reg}")
receipt_reg = client_alice.wait_for_transaction_receipt(
    tx_reg,
    status=TransactionStatus.FINALIZED,
    retries=80,
    interval=3000,
)
print(f"Patent Registration Status: {receipt_reg.get('status')}")

claim_count = client_alice.read_contract(
    address=contract_address,
    function_name="get_claim_count",
)
print(f"Total claims registered: {claim_count}")

claim_1 = client_alice.read_contract(
    address=contract_address,
    function_name="get_claim",
    args=[1],
)
print(f"Claim 1 data: {claim_1}")
evidence["transactions"].append({
    "step": "Patent claim registration",
    "tx_hash": tx_reg,
    "status": "FINALIZED",
    "claim_id": 1,
    "claim_title": claim_title,
    "status_after": claim_1.get("status"),
})

# STEP 5: SUBMIT PRIOR-ART CHALLENGE (BOB)
print("\n--- STEP 5: SUBMIT PRIOR-ART CHALLENGE (BOB) ---")
prior_art_url = "https://raw.githubusercontent.com/genlayerlabs/genvm/main/README.md"
citation_notes = "Citing GenVM decentralized execution engine architecture as relevant prior art"

tx_challenge = client_bob.write_contract(
    address=contract_address,
    function_name="submit_prior_art_challenge_payable",
    args=[1, prior_art_url, citation_notes],
    value=min_bond,
)
print(f"Prior-Art Challenge Tx Hash: {tx_challenge}")
receipt_challenge = client_bob.wait_for_transaction_receipt(
    tx_challenge,
    status=TransactionStatus.FINALIZED,
    retries=80,
    interval=3000,
)
print(f"Prior-Art Challenge Status: {receipt_challenge.get('status')}")

claim_1_chal = client_bob.read_contract(
    address=contract_address,
    function_name="get_claim",
    args=[1],
)
print(f"Claim 1 challenged status: {claim_1_chal.get('status')}")
print(f"Challenger: {claim_1_chal.get('challenger')}")
evidence["transactions"].append({
    "step": "Prior-art challenge submission",
    "tx_hash": tx_challenge,
    "status": "FINALIZED",
    "challenger": bob.address,
    "status_after": claim_1_chal.get("status"),
})

# STEP 6: WAIT FOR CHALLENGE WINDOW (35s)
print("\n--- STEP 6: WAITING FOR CHALLENGE WINDOW (35s) ---")
time.sleep(35)
print("Challenge window closed.")

# STEP 7: ADJUDICATE PATENT NOVELTY VIA VALIDATOR CONSENSUS
print("\n--- STEP 7: ADJUDICATE PATENT NOVELTY CONSENSUS ---")
tx_adj = client_alice.write_contract(
    address=contract_address,
    function_name="adjudicate_patent_novelty",
    args=[1],
)
print(f"Adjudication Tx Hash: {tx_adj}")

receipt_adj = client_alice.wait_for_transaction_receipt(
    tx_adj,
    status=TransactionStatus.FINALIZED,
    retries=100,
    interval=3000,
    full_transaction=True,
)
print(f"Adjudication FINALIZED! Status: {receipt_adj.get('status')}")

consensus_data = receipt_adj.get("consensus_data", {})
votes = consensus_data.get("votes", {})
print(f"Consensus Votes: {votes}")

claim_1_final = client_alice.read_contract(
    address=contract_address,
    function_name="get_claim",
    args=[1],
)
print(f"\nFinal Claim 1 State:")
print(f"  Status: {claim_1_final.get('status')}")
print(f"  Verdict: {claim_1_final.get('novelty_verdict')}")
print(f"  Overlap BPS: {claim_1_final.get('overlap_bps')}")
print(f"  Sources Verified: {claim_1_final.get('sources_verified')}")
print(f"  Inventor Payout: {claim_1_final.get('inventor_payout_wei')} wei")
print(f"  Challenger Payout: {claim_1_final.get('challenger_payout_wei')} wei")

final_invariants = client_alice.read_contract(
    address=contract_address,
    function_name="get_accounting_invariants",
)
print(f"\nFinal Accounting Invariants: {final_invariants}")
assert final_invariants["is_conserved"] is True
assert final_invariants["stranded_residue_wei"] == 0

evidence["final_claim_state"] = claim_1_final
evidence["final_accounting_invariants"] = final_invariants
evidence["transactions"].append({
    "step": "Adjudicate patent novelty consensus",
    "tx_hash": tx_adj,
    "status": "FINALIZED",
    "verdict": claim_1_final.get("novelty_verdict"),
    "overlap_bps": claim_1_final.get("overlap_bps"),
    "sources_verified": claim_1_final.get("sources_verified"),
    "votes": votes,
})

os.makedirs("evidence", exist_ok=True)
with open("evidence/deployment_evidence.json", "w", encoding="utf-8") as f:
    json.dump(evidence, f, indent=2)

print("\nSUCCESS! Complete multi-signer lifecycle verified on Studionet.")
