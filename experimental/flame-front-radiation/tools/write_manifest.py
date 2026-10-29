"""Write experimental/flame-front-radiation/SOURCE_SHA256.json."""
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
X = ROOT / 'experimental/flame-front-radiation'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
files = sorted(p for p in X.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'SOURCE_SHA256.json'
               and '.pytest_cache' not in p.parts)
copies = [
    {"copy": "adapters/frozen_copy/routing/core.py", "source": "integration/kit/routing_candidate/baseline/routing-package/routing/core.py"},
    {"copy": "adapters/frozen_copy/routing/independent.py", "source": "integration/kit/routing_candidate/baseline/routing-package/routing/independent.py"},
    {"copy": "adapters/frozen_copy/zsweep.py", "source": "integration/kit/phaseB/zsweep.py"},
]
for c in copies:
    c["sha256"] = sha(X / c["copy"]); assert c["sha256"] == sha(ROOT / c["source"])
out = {"schema": "wfg.flamefront.source-manifest/1", "law_version": "wfg.radiation.law/2-flamefront",
       "frozen_copies": copies,
       "files": {str(p.relative_to(X)): sha(p) for p in files}}
(X / 'SOURCE_SHA256.json').write_text(json.dumps(out, indent=1) + "\n")
print(len(out['files']), 'files')
