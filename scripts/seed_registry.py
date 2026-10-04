"""Build an unsigned example release; never manufacture a trusted publisher.

python scripts/seed_registry.py registry/workflows/summary-review.json output.release.json
"""

import argparse
import json
from pathlib import Path
from aero.services.releases import build_release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    parser.add_argument("output")
    args = parser.parse_args()
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(build_release(args.target), stream, indent=2)
        stream.write("\n")
    print(f"Unsigned release written to {args.output}; sign and approve explicitly.")


if __name__ == "__main__":
    main()
