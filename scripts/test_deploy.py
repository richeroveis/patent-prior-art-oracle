import os
import time
from dotenv import load_dotenv

load_dotenv()
pk_alice = os.getenv("GENLAYER_PRIVATE_KEY")
import genlayer_py

alice = genlayer_py.create_account(pk_alice)
client = genlayer_py.create_client(chain=genlayer_py.studionet, account=alice)

with open("contracts/patent_prior_art_oracle.py", "r", encoding="utf-8") as f:
    code = f.read()

print("Submitting deploy_contract transaction...")
tx_hash = client.deploy_contract(code=code, args=[1000000000000000])
print(f"Deploy tx hash: {tx_hash}")

for i in range(30):
    tx = client.get_transaction(tx_hash)
    status = tx.get("status") if tx else None
    print(f"Poll {i+1}: status={status}")
    if str(status) in ("FINALIZED", "ACCEPTED", "4", "5"):
        print("Tx decided! Keys:", list(tx.keys()))
        print("Data:", tx.get("data"))
        print("Recipient:", tx.get("recipient"))
        print("Consensus data:", tx.get("consensus_data"))
        break
    time.sleep(3)
