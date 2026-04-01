"""Trivy vulnerability scan helpers."""

import glob
import json
import os

# TODO: improve type def.
TrivyScanResults = dict


def combine_results(base_dir: str = ".") -> list[TrivyScanResults]:
    """Combine Trivy scan JSON files."""
    result_files = glob.glob(f"{base_dir}/*-results.json")
    vuln_list = []
    for result_file in result_files:
        parts = os.path.basename(result_file).replace("-results.json", "").split("--")
        group = parts[2]
        product = parts[0] + "@" + parts[1]
        parsed = json.load(open(result_file))
        for res in parsed.get("Results", []):
            for item in res.get("Vulnerabilities", []):
                item["Target"] = res["Target"]
                item["Class"] = res["Class"]
                item["Product"] = product
                item["Group"] = group
                vuln_list.append(item)
    return vuln_list
