"""Unit tests for charm, rock, snap, and trivy modules."""

import json
import os

import trivy


def test_trivy_combine_results():
    """Test combine_results will return all vulnerabilities in different reports."""
    num_results = 0
    base_dir = "tests/data/trivy"
    files = os.listdir(base_dir)
    for file in files:
        with open(f"{base_dir}/{file}") as f:
            data = json.load(f)
            for r in data["Results"]:
                num_results += len(r["Vulnerabilities"])

    assert len(trivy.combine_results(base_dir=base_dir)) == num_results
