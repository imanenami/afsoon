"""Workflow definitions."""

import datetime
import inspect
import json
import logging
from collections import defaultdict
from typing import cast

import rock
import snap
from models import CharmSpec, WorkflowSettings
from util import keep_main_only, prepare_sandbox

from .base import push_to_remote, register

logger = logging.getLogger(__name__)


@register(aliases=["releases"])
def gather_releases(settings: WorkflowSettings) -> None:
    """Gather charm releases and associated workflow versions for different tracks."""
    prepare_sandbox()
    cfg = keep_main_only(settings.charms.values())
    res = []
    # iterate over all defined charms
    for spec in cfg:
        spec = cast(CharmSpec, spec)
        subs = spec.substrate
        _main = snap.resolve_machine_charm_all if subs == "machine" else rock.resolve_k8s_charm_all
        versions = _main(spec)
        res.append((spec, versions))
        print(versions)

    # format results for a nice HTML/JS rendering:
    # final = {charm: {rel: {vm: ,k8s: } } }
    final = {}
    _known_versions = ""
    for spec, vers in res:
        subs = spec.substrate.replace("machine", "vm")
        canonical_name = spec.name.replace("-k8s", "")
        if canonical_name not in final:
            final[canonical_name] = defaultdict(
                lambda: {"vm": "---", "k8s": "---", "group": spec.group}
            )
        for ver in vers:
            snap_ver = f" ({ver.snap})" if ver.snap and ver.snap != "unknown" else ""
            ver_txt = ver.workload + snap_ver
            final[canonical_name][ver.charm][subs] = ver_txt
            # print known version format
            if spec.substrate == "machine":
                _known_versions += f"snap,{spec.snap},{ver.snap},{ver.workload}\n"
            else:
                _known_versions += f"rock,{spec.name},{ver.image},{ver.workload}\n"

    print("###\n\n")
    print(_known_versions)
    print("###\n\n")

    formatted = {}
    for charm, data in final.items():
        formatted[charm] = [
            {
                "channel": c,
                "group": data[c]["group"],
                "versions": {"k8s": data[c]["k8s"], "vm": data[c]["vm"]},
            }
            for c in data
        ]

    js = inspect.cleandoc(f"""
        updatedAt = "{datetime.datetime.now(tz=datetime.UTC).replace(microsecond=0)}";
        releaseData = {json.dumps(formatted)};
    """)

    print(js)
    with open("releaseData.js", "w") as f:
        f.write(js)

    push_to_remote(add={"releaseData.js": "js/releaseData.js"})
