import datetime
import json
import os
from collections import defaultdict

from main import cleanup, load_config, _main_k8s, _main_machine
from src.util import DOCKER, SANDBOX_INST


os.system(f"scripts/init-sandbox.sh {SANDBOX_INST}")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cwd = os.getcwd()
os.chdir(BASE_DIR)

cfg = load_config()

res = []
for spec in cfg.values():
    subs = spec["substrate"]
    _main = _main_machine if subs == "machine" else _main_k8s
    versions = _main(spec)
    res.append((spec, versions))
    print(versions)


final = {}
# final = {charm: {rel: {vm: ,k8s: } } }
for spec, vers in res:
    subs = spec["substrate"].replace("machine", "vm")
    canonical_name = spec["name"].replace("-k8s", "")
    if canonical_name not in final:
        final[canonical_name] = defaultdict(lambda: {"vm": "---", "k8s": "---"})
    for ver in vers:
        snap_ver = f" ({ver.snap})" if ver.snap and ver.snap != "unknown" else ""
        ver_txt = ver.workload + snap_ver
        final[canonical_name][ver.charm][subs] = ver_txt


formatted = {}
for charm, data in final.items():
    formatted[charm] = [{"channel": c, "versions": {"k8s": data[c]["k8s"], "vm": data[c]["vm"]}} for c in data]


js = f"""
updatedAt = "{datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0)}";
releaseData = {json.dumps(formatted)};
"""

print(js)

with open("releaseData.js", "w") as f:
    f.write(js)


os.system("./publish releaseData.js")

cleanup()
os.system(f"lxc rm --force {SANDBOX_INST}")
os.chdir(cwd)
