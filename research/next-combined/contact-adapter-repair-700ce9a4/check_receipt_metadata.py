"""Receipt source hashes and prior Git blob identities, without study reads."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parent / "audit-1c"
r=json.loads((REPO / "research/sipp-routing/KNOWN_FOOTPRINT_ADAPTER_RECEIPT.json").read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
sources=r["source_sha256"]
for relative,digest in sources.items():
    assert sha(REPO / relative)==digest, relative
preserved=list(r["preserved_evidence_sha256"])
def tree(revision):
    output=subprocess.check_output(["git","ls-tree","-r",revision,"--",*preserved],cwd=REPO,text=True)
    return {row.split("\t",1)[1]:row.split("\t",1)[0].split()[-1] for row in output.splitlines()}
before,after=tree("HEAD^"),tree("HEAD")
assert set(before)==set(after)==set(preserved)
assert before==after
for relative,digest in r["timing_compatibility_reference"]["sources"].items():
    assert sha(REPO / relative)==digest
result={"status":"PASS_RECEIPT_METADATA_CHECKS","commit":"fd8bf2e78532b76d2dd2cfd094d3499def90fc23","reviewed_source_hashes":len(sources),"unchanged_prior_git_blobs":len(preserved),"timing_reference_hashes":len(r["timing_compatibility_reference"]["sources"]),"scope":"Source bytes and Git object metadata only. No prior real graph, trajectory arrays or native planner records were opened."}
(HERE / "receipt_checks.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result))
