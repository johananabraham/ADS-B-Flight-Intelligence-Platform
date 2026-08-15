#!/usr/bin/env python3
"""Export privacy-preserving relative field features from private SBS data."""

import argparse
import json
from pathlib import Path

from evaluation.field.sanitizer import sanitize_capture


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = sanitize_capture(args.manifest, args.policy, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
