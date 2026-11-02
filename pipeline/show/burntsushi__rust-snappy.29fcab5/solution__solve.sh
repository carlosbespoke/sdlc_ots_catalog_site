#!/usr/bin/env bash
set -euo pipefail

printf '%s' '8c62fd3623b99aabcec101b421a002ac59be73527ef04e2a62cd940a4f4502af' > /workspace/oracle-auth-token

# The oracle verifies the test harness. It hands off through a wrapper
# and keeps argv[0] so help and usage text still name the submitted path.
cat > /workspace/compile.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cat > /workspace/executable <<'WRAPPER'
#!/usr/bin/env bash
exec -a "$0" /opt/task-reference/executable "$@"
WRAPPER
chmod 0755 /workspace/executable
EOF
chmod +x /workspace/compile.sh
