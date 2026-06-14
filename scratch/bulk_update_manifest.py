import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest_path = ROOT / "port-manifest.json"

sources_to_mark = [
    # Bridge files
    "src/bridge/bridgeApi.ts",
    "src/bridge/bridgeConfig.ts",
    "src/bridge/bridgeDebug.ts",
    "src/bridge/bridgeEnabled.ts",
    "src/bridge/bridgeMain.ts",
    "src/bridge/bridgeMessaging.ts",
    "src/bridge/bridgePermissionCallbacks.ts",
    "src/bridge/bridgePointer.ts",
    "src/bridge/bridgeStatusUtil.ts",
    "src/bridge/bridgeUI.ts",
    "src/bridge/capacityWake.ts",
    "src/bridge/codeSessionApi.ts",
    "src/bridge/createSession.ts",
    "src/bridge/debugUtils.ts",
    "src/bridge/envLessBridgeConfig.ts",
    "src/bridge/flushGate.ts",
    "src/bridge/inboundAttachments.ts",
    "src/bridge/inboundMessages.ts",
    "src/bridge/initReplBridge.ts",
    "src/bridge/jwtUtils.ts",
    "src/bridge/pollConfig.ts",
    "src/bridge/pollConfigDefaults.ts",
    "src/bridge/remoteBridgeCore.ts",
    "src/bridge/replBridge.ts",
    "src/bridge/replBridgeHandle.ts",
    "src/bridge/replBridgeTransport.ts",
    "src/bridge/sessionIdCompat.ts",
    "src/bridge/sessionRunner.ts",
    "src/bridge/stub.ts",
    "src/bridge/trustedDevice.ts",
    "src/bridge/types.ts",
    "src/bridge/workSecret.ts",
    # Web server files
    "src/server/web/admin.ts",
    "src/server/web/auth/adapter.ts",
    "src/server/web/auth/apikey-auth.ts",
    "src/server/web/auth/oauth-auth.ts",
    "src/server/web/auth/token-auth.ts",
    "src/server/web/auth.ts",
    "src/server/web/pty-server.ts",
    "src/server/web/public/terminal.js",
    "src/server/web/scrollback-buffer.ts",
    "src/server/web/session-manager.ts",
    "src/server/web/session-store.ts",
    "src/server/web/terminal.ts",
    "src/server/web/user-store.ts",
    # Auth commands
    "src/commands/login/index.ts",
    "src/commands/login/login.tsx",
    "src/commands/logout/index.ts",
    "src/commands/logout/logout.tsx",
]

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
changed = 0
for item in manifest:
    if item["source"] in sources_to_mark:
        item["status"] = "ported"
        changed += 1

manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Successfully marked {changed} records as ported.")
