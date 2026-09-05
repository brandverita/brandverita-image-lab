"""JWKS access-token verification for the BrandVerita Generation API.

Local, network-light verification of Supabase-issued access tokens against
public JWKS endpoints. No Supabase SDK — PyJWT + cryptography only, matching
the api_image pins.

Issuers
-------
Primary issuer: the staging comfy-ui Supabase project. Its base URL is passed
in by the caller (from supabase_rest.supabase_config()), so this module has no
hard-coded project reference.

Extra issuers: the optional environment variable EXTRA_JWT_ISSUER_URLS holds a
comma-separated list of additional trusted Supabase project base URLs (e.g.
the Studio project). Each extra issuer is verified exactly like the primary:
issuer "{base}/auth/v1", public keys from
"{base}/auth/v1/.well-known/jwks.json", audience "authenticated".

A token is accepted when ANY configured issuer verifies it. Extra issuers are
server-side configuration only — never client-supplied — and grant no extra
capability: registry gates and flags run after auth as before.

Failure contract (unchanged): this module returns None on any verification
failure and never raises for an unverifiable token. The caller decides the
HTTP failure kind (token_invalid vs. the primary-only REST fallback).
"""

import os
from typing import Optional

import jwt
from jwt import PyJWKClient

_AUDIENCE = "authenticated"
# Asymmetric algorithms only. Legacy HS256 tokens have no key in the public
# JWKS, so they fail here and fall through to the caller's REST fallback —
# preserving the v5/v6 behaviour for older sessions on the primary issuer.
_ALGORITHMS = ["ES256", "RS256"]
_JWKS_LIFESPAN_SECONDS = 3600

# One PyJWKClient per issuer base URL, created lazily. cache_keys=True makes
# the client reuse fetched JWKS and refetch only on an unknown kid, so steady
# state adds no outbound call per request.
_jwk_clients: dict[str, PyJWKClient] = {}


def _normalise_base(url: str) -> str:
    return url.strip().rstrip("/")


def _issuer_for(base: str) -> str:
    return f"{base}/auth/v1"


def _jwks_url_for(base: str) -> str:
    return f"{base}/auth/v1/.well-known/jwks.json"


def extra_issuer_bases() -> list[str]:
    """Configured extra issuer base URLs (may be empty)."""
    raw = os.environ.get("EXTRA_JWT_ISSUER_URLS", "")
    return [_normalise_base(part) for part in raw.split(",") if part.strip()]


def issuer_bases(primary_base: str) -> list[str]:
    """Primary issuer first, then any extras, de-duplicated, order stable."""
    bases = [_normalise_base(primary_base)]
    for extra in extra_issuer_bases():
        if extra not in bases:
            bases.append(extra)
    return bases


def issuer_labels(primary_base: str) -> list[str]:
    """Short key-free labels for /health: the project-ref host label per issuer.

    "https://thspgkedjkiltrcimond.supabase.co" -> "thspgkedjkiltrcimond"
    """
    labels = []
    for base in issuer_bases(primary_base):
        host = base.split("://", 1)[-1]
        labels.append(host.split(".")[0] or host)
    return labels


def _client_for(base: str) -> PyJWKClient:
    client = _jwk_clients.get(base)
    if client is None:
        client = PyJWKClient(
            _jwks_url_for(base),
            cache_keys=True,
            lifespan=_JWKS_LIFESPAN_SECONDS,
        )
        _jwk_clients[base] = client
    return client


def _verify_with_issuer(token: str, base: str) -> Optional[str]:
    """Return the verified user id for this issuer, or None on any failure.

    Every failure — bad signature, wrong issuer, wrong audience, expired, JWKS
    fetch error, unknown kid — collapses to None. The caller owns the mapping
    to HTTP failure kinds; this function must never leak which check failed.
    """
    try:
        signing_key = _client_for(base).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            audience=_AUDIENCE,
            issuer=_issuer_for(base),
        )
    except Exception:  # noqa: BLE001 — any verification failure means "not this issuer"
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def token_issuer_base(token: str) -> Optional[str]:
    """The token's issuer base URL, read WITHOUT verifying the signature.

    Used only to route the caller's REST fallback (an extra-issuer token must
    not be checked against the primary project's REST auth endpoint). Never
    use this to authenticate — the signature is not checked here.
    """
    try:
        claims = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": False},
        )
    except Exception:  # noqa: BLE001 — malformed token; caller treats as invalid
        return None
    iss = claims.get("iss")
    if not isinstance(iss, str) or not iss:
        return None
    iss = iss.rstrip("/")
    suffix = "/auth/v1"
    if iss.endswith(suffix):
        return iss[: -len(suffix)]
    return iss


def verify_via_jwks(token: str, primary_base: str) -> Optional[str]:
    """Return the verified user id, or None if no configured issuer accepts it.

    Interface unchanged from the single-issuer version: the primary (comfy-ui)
    base URL is passed in; extras come from EXTRA_JWT_ISSUER_URLS. Primary is
    tried first so the common Lab path costs at most one cached key lookup.
    """
    for base in issuer_bases(primary_base):
        user_id = _verify_with_issuer(token, base)
        if user_id:
            return user_id
    return None
