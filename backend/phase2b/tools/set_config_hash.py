"""Set workflow_definitions.config_hash using the API's exact canonicalisation.

    SUPABASE_URL=https://thspgkedjkiltrcimond.supabase.co \
    SUPABASE_SERVICE_ROLE_KEY=... \
    python set_config_hash.py product_scene v1

The hash is a tripwire: api.py recomputes it per request and logs
`config_hash_mismatch` when the stored value disagrees, which is how an edit
made outside the immutability trigger becomes visible. It must therefore be
written with the same encoder the API uses (sorted keys, compact separators).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import httpx

FIELDS = (
    "key",
    "version",
    "provider",
    "provider_model",
    "provider_workflow_reference",
    "input_schema",
    "output_schema",
    "allowed_dimensions",
)


def main() -> int:
    if len(sys.argv) != 3:
        return int(bool(sys.stderr.write("usage: set_config_hash.py <key> <version>\n"))) or 2
    key, version = sys.argv[1], sys.argv[2]
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not service_key:
        sys.stderr.write("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required\n")
        return 2

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0, base_url=url, headers=headers) as client:
        rows = client.get(
            "/rest/v1/workflow_definitions",
            params={"select": "*", "key": f"eq.{key}", "version": f"eq.{version}"},
        ).json()
        if not rows:
            sys.stderr.write(f"no registry row for {key}:{version}\n")
            return 1
        row = rows[0]
        config = {field: row.get(field) for field in FIELDS}
        digest = hashlib.sha256(
            json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        response = client.patch(
            "/rest/v1/workflow_definitions",
            params={"key": f"eq.{key}", "version": f"eq.{version}"},
            json={"config_hash": digest},
        )
        if response.status_code >= 300:
            sys.stderr.write(f"patch failed: {response.status_code} {response.text[:300]}\n")
            return 1
    print(f"{key}:{version} config_hash={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
