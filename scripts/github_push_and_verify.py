import os
import sys
import subprocess
import tempfile
import urllib.request
import urllib.error
import json
import hashlib
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("GITHUB_TOKEN")
if not token:
    print("ERROR: GITHUB_TOKEN is not set in .env")
    sys.exit(1)

repo_name = "patent-prior-art-oracle"
full_repo = f"richeroveis/{repo_name}"
api_url = f"https://api.github.com/repos/{full_repo}"

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "Antigravity-Agent",
}

# 1. Check or Create Repo
print(f"Checking repository {full_repo} on GitHub...")
req = urllib.request.Request(api_url, headers=headers)
repo_exists = False
try:
    with urllib.request.urlopen(req) as resp:
        if resp.status == 200:
            print("Repository exists.")
            repo_exists = True
except urllib.error.HTTPError as e:
    if e.code == 404:
        print("Repository does not exist. Creating repository...")
        create_url = "https://api.github.com/user/repos"
        payload = json.dumps({
            "name": repo_name,
            "description": "PatentPriorArtOracle: Staked Patent Claim Novelty and Public Prior-Art Audit Registry on GenLayer",
            "private": False,
            "has_issues": True,
        }).encode("utf-8")
        create_req = urllib.request.Request(create_url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(create_req) as create_resp:
                print(f"Created repository successfully (status {create_resp.status}).")
                repo_exists = True
        except urllib.error.HTTPError as ce:
            print(f"Error creating repo: {ce.code} {ce.read().decode('utf-8')}")
            sys.exit(1)
    else:
        print(f"HTTP error checking repo: {e.code}")
        sys.exit(1)

# 2. Configure Git, Commit, Tag, Push via GIT_ASKPASS
print("\nStaging files and updating commit...")
subprocess.run(["git", "add", "."], check=True)

commit_msg = "feat: implement and verify PatentPriorArtOracle on GenLayer Studionet"
subprocess.run(["git", "commit", "--amend", "-m", commit_msg], check=True)

# Tag studionet-v1
subprocess.run(["git", "tag", "-f", "-a", "studionet-v1", "-m", "Studionet deployment v1 release"], check=True)

# Set remote URL without credentials
remote_url = f"https://github.com/{full_repo}.git"
remotes = subprocess.check_output(["git", "remote"]).decode("utf-8").split()
if "origin" in remotes:
    subprocess.run(["git", "remote", "set-url", "origin", remote_url], check=True)
else:
    subprocess.run(["git", "remote", "add", "origin", remote_url], check=True)

# Create a temporary askpass script to safely pass the token
with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
    askpass_py = f.name
    f.write(f"""import sys
prompt = sys.argv[1].lower() if len(sys.argv) > 1 else ""
if "username" in prompt:
    print("x-access-token")
else:
    print('{token}')
""")

with tempfile.NamedTemporaryFile("w", suffix=".bat", delete=False) as f_bat:
    askpass_bat = f_bat.name
    f_bat.write(f"@python \"{askpass_py}\" %*\n")

env = os.environ.copy()
env["GIT_ASKPASS"] = askpass_bat
env["GIT_TERMINAL_PROMPT"] = "0"

git_cmd_base = ["git", "-c", "credential.helper="]

try:
    print("\nPushing main branch to GitHub...")
    res = subprocess.run(git_cmd_base + ["push", "-u", "origin", "main", "--force"], env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Git push failed: {res.stderr}")
        sys.exit(1)
    print("Git push main successful.")

    print("Pushing tag studionet-v1 to GitHub...")
    res_tag = subprocess.run(git_cmd_base + ["push", "origin", "studionet-v1", "--force"], env=env, capture_output=True, text=True)
    if res_tag.returncode != 0:
        print(f"Git push tag failed: {res_tag.stderr}")
        sys.exit(1)
    print("Git push tag successful.")
finally:
    if os.path.exists(askpass_py):
        os.remove(askpass_py)
    if os.path.exists(askpass_bat):
        os.remove(askpass_bat)

# 3. Verify 4-way LF SHA-256 identity
print("\n--- 4-WAY LF SHA-256 IDENTITY VERIFICATION ---")
contract_rel_path = "contracts/patent_prior_art_oracle.py"

# Hash 1: Local file (normalized to LF)
with open(contract_rel_path, "r", encoding="utf-8") as f:
    local_content = f.read().replace("\r\n", "\n")
hash_local = hashlib.sha256(local_content.encode("utf-8")).hexdigest()
print(f"1. Local File LF SHA-256:       {hash_local}")

# Hash 2: Git HEAD blob
head_blob = subprocess.check_output(["git", "show", f"HEAD:{contract_rel_path}"]).decode("utf-8").replace("\r\n", "\n")
hash_git = hashlib.sha256(head_blob.encode("utf-8")).hexdigest()
print(f"2. Git HEAD Blob LF SHA-256:    {hash_git}")

# Hash 3: Remote GitHub raw file (normalized to LF)
raw_url = f"https://raw.githubusercontent.com/{full_repo}/main/{contract_rel_path}"
print(f"Fetching remote content from {raw_url} ...")
req_raw = urllib.request.Request(raw_url, headers={"Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req_raw) as resp:
    remote_content = resp.read().decode("utf-8").replace("\r\n", "\n")
hash_remote = hashlib.sha256(remote_content.encode("utf-8")).hexdigest()
print(f"3. GitHub Raw LF SHA-256:       {hash_remote}")

# Hash 4: Deployed contract source hash recorded in evidence
with open("evidence/deployment_evidence.json", "r", encoding="utf-8") as f:
    evidence_data = json.load(f)
hash_deployed = evidence_data["contract_lf_sha256"]
print(f"4. Deployed Source LF SHA-256:  {hash_deployed}")

assert hash_local == hash_git == hash_remote == hash_deployed, "SHA-256 MISMATCH DETECTED!"
print("\nPERFECT 4-WAY SHA-256 IDENTITY VERIFIED!")
