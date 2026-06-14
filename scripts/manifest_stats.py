from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    manifest = json.loads((ROOT / "port-manifest.json").read_text(encoding="utf-8"))
    counts = Counter(item["status"] for item in manifest)
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")
    print(f"total: {len(manifest)}")


if __name__ == "__main__":
    main()
