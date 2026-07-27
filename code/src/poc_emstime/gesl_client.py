"""Client for GESL's documented public API (email + apikey, not the
undocumented session-JWT endpoint used to discover gesl_manifest's sigids).

Signature data is static once published on GESL -- download_signature() is a
cache-or-fetch operation, not something that re-hits the network on every
call, since a fixed signature ID never changes underneath it.
"""

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

GESL_API_URL = "https://gesl.ornl.gov/api/apps/gesl"
REPO_ROOT = Path(__file__).resolve().parents[3]
GESL_DATA_DIR = REPO_ROOT / "data" / "gesl"
GESL_RAW_DIR = GESL_DATA_DIR / "raw"

# Loaded at import time (not lazily inside _credentials()) so os.environ is
# already populated by the time anything -- including a test's skipif
# condition -- checks for GESL_APIKEY. Safe to call even with no .env
# present (e.g. in CI): load_dotenv() just returns False and leaves
# os.environ untouched, and _credentials() raises a clear error later if
# something actually tries to use the API without credentials.
load_dotenv(REPO_ROOT / ".env")


def _credentials() -> tuple[str, str]:
    email = os.environ.get("GESL_EMAIL")
    apikey = os.environ.get("GESL_APIKEY")
    if not email or not apikey:
        raise RuntimeError(
            "GESL_EMAIL and GESL_APIKEY must be set (copy .env.example to .env "
            "and fill in) -- register a free account at "
            "https://gesl.ornl.gov/account/register and copy your key from "
            "Applications/API."
        )
    return email, apikey


def _post(payload: dict) -> httpx.Response:
    email, apikey = _credentials()
    body = {"email": email, "apikey": apikey, **payload}
    resp = httpx.post(GESL_API_URL, json=body, timeout=120.0)
    resp.raise_for_status()
    return resp


def download_signature(sigid: int, sigtype: str = "data quality", force: bool = False) -> Path:
    """Downloads and caches sigId-{sigid}.zip under data/gesl/raw/, skipping
    the network call entirely when already cached (force=False)."""
    GESL_RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = GESL_RAW_DIR / f"sigId-{sigid}.zip"
    if dest.exists() and not force:
        return dest

    resp = _post({"sigid": sigid, "sigtype": sigtype, "output": "data"})
    if not resp.content.startswith(b"PK"):
        # GESL can return a JSON error body with a 200 status (e.g. a bad
        # apikey) rather than an HTTP error -- raise_for_status() alone
        # wouldn't catch that, so check the actual payload looks like a zip.
        raise RuntimeError(
            f"expected a zip file for sigid {sigid}, got non-zip content "
            f"(first 200 bytes): {resp.content[:200]!r}"
        )
    dest.write_bytes(resp.content)
    return dest
