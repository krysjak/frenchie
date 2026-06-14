from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: mark_port_status.py <status> <source> [<source> ...]")
    status = sys.argv[1]
    sources = set(sys.argv[2:])
    manifest_path = ROOT / "port-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed = 0
    for item in manifest:
        if item["source"] in sources:
            item["status"] = status
            changed += 1
    missing = sources - {item["source"] for item in manifest}
    if missing:
        raise SystemExit(f"missing sources: {sorted(missing)}")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"marked {changed} records as {status}")


if __name__ == "__main__":
    main()
