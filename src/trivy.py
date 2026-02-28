"""Trivy vulnerability scan helpers."""

import glob
import json
import os

# TODO: improve type def.
TrivyScanResults = dict


def load_rocks() -> set[str]:
    """Load rocks from ROCKS file."""
    raw = [line.strip() for line in open("ROCKS").readlines()]
    return {line for line in raw if line and not line.startswith("#")}


def combine_results() -> list[TrivyScanResults]:
    """Combine Trivy scan JSON files."""
    result_files = glob.glob("*-results.json")
    vuln_list = []
    for result_file in result_files:
        product = os.path.basename(result_file).replace("-results.json", "").replace("--", "@")
        parsed = json.load(open(result_file))
        for res in parsed.get("Results", []):
            for item in res.get("Vulnerabilities", []):
                item["Target"] = res["Target"]
                item["Class"] = res["Class"]
                item["Product"] = product
                vuln_list.append(item)
    return vuln_list
