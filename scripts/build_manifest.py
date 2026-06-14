from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PORT_ROOT = ROOT / "python-port"
SOURCE_EXTS = {".ts", ".tsx", ".js"}


def target_for(source: Path) -> str:
    relative = source.relative_to(ROOT)
    parts = list(relative.parts)
    if parts[0] == "src":
        parts[0] = "claude_code_py"
    elif parts[0] == "mcp-server":
        parts = ["claude_code_py", "mcp", *parts[1:]]
    elif parts[0] == "scripts":
        parts = ["scripts", *parts[1:]]
    elif parts[0] == "web":
        parts = ["web_port", *parts[1:]]
    suffix = "".join(Path(parts[-1]).suffixes)
    if suffix:
        parts[-1] = Path(parts[-1]).name.removesuffix(suffix) + ".py"
    return str(Path(*parts)).replace("\\", "/")


def build_manifest() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for source in sorted(ROOT.rglob("*")):
        if ".git" in source.parts or "node_modules" in source.parts or "python-port" in source.parts:
            continue
        if source.suffix.lower() not in SOURCE_EXTS:
            continue
        records.append(
            {
                "source": str(source.relative_to(ROOT)).replace("\\", "/"),
                "target": target_for(source),
                "status": "pending",
            }
        )
    return records


def main() -> None:
    manifest = build_manifest()
    output = PORT_ROOT / "port-manifest.json"
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(manifest)} records to {output}")


if __name__ == "__main__":
    main()
