import os
import time

import pytest

from poc_emstime import gesl_client
from poc_emstime.gesl_manifest import TIMING_SIGNATURES

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("GESL_APIKEY"),
        reason="GESL_APIKEY not set -- copy .env.example to .env and fill in real credentials",
    ),
]


def test_download_signature_caches_locally(tmp_path, monkeypatch):
    # Redirect the cache dir so this test never depends on (or pollutes)
    # whatever's already cached under the real data/gesl/raw/.
    monkeypatch.setattr(gesl_client, "GESL_RAW_DIR", tmp_path)

    sigid = TIMING_SIGNATURES[0].sigid  # 5711, confirmed real during design research
    path = gesl_client.download_signature(sigid)

    assert path.exists()
    assert path.read_bytes().startswith(b"PK")
    first_mtime = path.stat().st_mtime

    # A second call with force=False must not re-hit the network: assert by
    # timing rather than mocking httpx, so this also proves the cache check
    # happens *before* any request is attempted, not just that the file
    # still exists afterward.
    start = time.monotonic()
    path_again = gesl_client.download_signature(sigid)
    elapsed = time.monotonic() - start

    assert path_again == path
    assert path.stat().st_mtime == first_mtime
    assert elapsed < 1.0
