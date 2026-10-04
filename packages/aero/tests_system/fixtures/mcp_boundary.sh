#!/bin/sh
# Test-only MCP protocol fixture. Executed inside the preloaded BusyBox image.
# No host mounts, network, Python installation, or production substitutes.
set -eu

while IFS= read -r request; do
    method=$(printf '%s' "$request" | sed -n 's/.*"method"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    request_id=$(printf '%s' "$request" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p')
    # Notifications have no response in JSON-RPC.
    [ -n "$request_id" ] || continue
    case "$method" in
        initialize)
            printf '{"jsonrpc":"2.0","id":%s,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"boundary-fixture","version":"1.0.0"}}}\n' "$request_id"
            ;;
        tools/list)
            printf '{"jsonrpc":"2.0","id":%s,"result":{"tools":[{"name":"inspect_boundary","description":"Inspect actual container isolation and credential scope.","inputSchema":{"type":"object","properties":{},"additionalProperties":false}},{"name":"unapproved_extra","description":"Must be filtered out by AeroMesh.","inputSchema":{"type":"object","properties":{}}}]}}\n' "$request_id"
            ;;
        tools/call)
            tool_name=$(printf '%s' "$request" | sed -n 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
            if [ "$tool_name" != inspect_boundary ]; then
                printf '{"jsonrpc":"2.0","id":%s,"error":{"code":-32602,"message":"Unexpected tool name"}}\n' "$request_id"
                continue
            fi
            network=enabled
            [ -e /sys/class/net/eth0 ] || network=none
            rootfs=$(awk '$2 == "/" {print $4}' /proc/mounts | cut -d, -f1)
            bound=false
            [ "${SERVICE_TOKEN:-}" != fixture-token ] || bound=true
            unbound=absent
            [ -z "${UNRELATED_SECRET:-}${OTHER_TOKEN:-}" ] || unbound=present
            printf '{"jsonrpc":"2.0","id":%s,"result":{"content":[{"type":"text","text":"uid=%s;network=%s;rootfs=%s;bound=%s;unbound=%s"}],"isError":false}}\n' "$request_id" "$(id -u)" "$network" "$rootfs" "$bound" "$unbound"
            ;;
        ping)
            printf '{"jsonrpc":"2.0","id":%s,"result":{}}\n' "$request_id"
            ;;
        *)
            printf '{"jsonrpc":"2.0","id":%s,"error":{"code":-32601,"message":"Method not found"}}\n' "$request_id"
            ;;
    esac
done
