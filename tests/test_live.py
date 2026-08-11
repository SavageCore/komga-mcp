"""Integration tests against a real Komga instance.

Skipped unless KOMGA_URL and KOMGA_API_KEY are set. Run with:
    uv run pytest -m integration
"""

import os
import uuid

import pytest
from fastmcp import Client

import komga_mcp

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (os.environ.get("KOMGA_URL") and os.environ.get("KOMGA_API_KEY")),
        reason="requires KOMGA_URL and KOMGA_API_KEY",
    ),
]


@pytest.fixture(autouse=True)
def configure_client():
    komga_mcp._client = komga_mcp.build_client(
        os.environ["KOMGA_URL"],
        os.environ["KOMGA_API_KEY"],
        verify=komga_mcp._env_bool(os.environ.get("KOMGA_VERIFY_TLS")),
    )
    yield


async def call(name, **kwargs):
    async with Client(komga_mcp.mcp) as client:
        return await client.call_tool(name, kwargs)


async def test_whoami_returns_current_user():
    result = await call("whoami")
    assert isinstance(result.data, dict)
    assert "id" in result.data


async def test_libraries_are_readable():
    result = await call("list_libraries")
    assert result.data is not None


async def test_collection_lifecycle():
    name = f"mcp-test-{uuid.uuid4().hex[:8]}"
    created = None
    try:
        created = await call("create_collection", collection={"name": name, "ordered": False, "seriesIds": []})
        collection_id = created.data["id"]
        fetched = await call("get_collection", collection_id=collection_id)
        assert fetched.data["name"] == name
        patched = await call("update_collection", collection_id=collection_id, patch={"name": f"{name}-updated"})
        assert patched.data["name"] == f"{name}-updated"
    finally:
        if created and created.data.get("id"):
            await call("delete_collection", collection_id=created.data["id"])
