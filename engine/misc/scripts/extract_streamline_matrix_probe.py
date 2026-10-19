"""Snapshot the production converter for the standalone SDK convention probe."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = args.source.read_text()
    match = re.search(r"static sl::float4x4 sl_convert_matrix\(const Projection &mtx\) \{.*?\n\}", source, re.S)
    if not match:
        raise ValueError("Production converter was not found")
    args.output.mkdir(parents=True, exist_ok=False)
    helper = match.group(0) + "\n"
    (args.output / "conversion_under_test.h").write_text(helper)
    (args.output / "provenance.json").write_text(json.dumps({
        "source": str(args.source.resolve()), "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "helper_sha256": hashlib.sha256(helper.encode()).hexdigest(), "performance_accepted": False,
        "quality_accepted": False}, indent=2) + "\n")


if __name__ == "__main__":
    main()
