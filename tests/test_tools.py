"""Offline endpoint tests for the Komga MCP server.

Every tool is called through FastMCP's in-memory Client and the request is
captured by httpx.MockTransport. No Komga instance or network is required.
"""

import json
import re

import httpx
import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.exceptions import ToolError

import komga_mcp


KOMGA_CONTRACT = {
    ("GET", r"^/api/v1/libraries$"),
    ("GET", r"^/api/v1/libraries/(?P<id>[^/]+)$"),
    ("POST", r"^/api/v1/libraries$"),
    ("PATCH", r"^/api/v1/libraries/(?P<id>[^/]+)$"),
    ("DELETE", r"^/api/v1/libraries/(?P<id>[^/]+)$"),
    ("POST", r"^/api/v1/libraries/(?P<id>[^/]+)/scan$"),
    ("POST", r"^/api/v1/libraries/(?P<id>[^/]+)/analyze$"),
    ("POST", r"^/api/v1/libraries/(?P<id>[^/]+)/metadata/refresh$"),
    ("POST", r"^/api/v1/libraries/(?P<id>[^/]+)/empty-trash$"),
    ("POST", r"^/api/v1/series/list$"),
    ("POST", r"^/api/v1/series/list/alphabetical-groups$"),
    ("GET", r"^/api/v1/series/(?P<id>[^/]+)$"),
    ("GET", r"^/api/v1/series/(?P<id>[^/]+)/collections$"),
    ("GET", r"^/api/v1/series/latest$"),
    ("GET", r"^/api/v1/series/new$"),
    ("GET", r"^/api/v1/series/updated$"),
    ("GET", r"^/api/v1/series/(?P<id>[^/]+)/thumbnails$"),
    ("PATCH", r"^/api/v1/series/(?P<id>[^/]+)/metadata$"),
    ("POST", r"^/api/v1/series/(?P<id>[^/]+)/metadata/refresh$"),
    ("POST", r"^/api/v1/series/(?P<id>[^/]+)/analyze$"),
    ("POST", r"^/api/v1/series/(?P<id>[^/]+)/read-progress$"),
    ("DELETE", r"^/api/v1/series/(?P<id>[^/]+)/read-progress$"),
    ("POST", r"^/api/v1/books/list$"),
    ("GET", r"^/api/v1/books/(?P<id>[^/]+)$"),
    ("GET", r"^/api/v1/books/(?P<id>[^/]+)/pages$"),
    ("GET", r"^/api/v1/books/(?P<id>[^/]+)/next$"),
    ("GET", r"^/api/v1/books/(?P<id>[^/]+)/previous$"),
    ("GET", r"^/api/v1/books/(?P<id>[^/]+)/readlists$"),
    ("GET", r"^/api/v1/books/(?P<id>[^/]+)/thumbnails$"),
    ("GET", r"^/api/v1/books/latest$"),
    ("GET", r"^/api/v1/books/ondeck$"),
    ("GET", r"^/api/v1/books/duplicates$"),
    ("PATCH", r"^/api/v1/books/(?P<id>[^/]+)/metadata$"),
    ("PATCH", r"^/api/v1/books/metadata$"),
    ("POST", r"^/api/v1/books/(?P<id>[^/]+)/metadata/refresh$"),
    ("POST", r"^/api/v1/books/(?P<id>[^/]+)/analyze$"),
    ("PATCH", r"^/api/v1/books/(?P<id>[^/]+)/read-progress$"),
    ("DELETE", r"^/api/v1/books/(?P<id>[^/]+)/read-progress$"),
    ("GET", r"^/api/v1/collections$"),
    ("GET", r"^/api/v1/collections/(?P<id>[^/]+)$"),
    ("GET", r"^/api/v1/collections/(?P<id>[^/]+)/series$"),
    ("POST", r"^/api/v1/collections$"),
    ("PATCH", r"^/api/v1/collections/(?P<id>[^/]+)$"),
    ("DELETE", r"^/api/v1/collections/(?P<id>[^/]+)$"),
    ("GET", r"^/api/v1/readlists$"),
    ("GET", r"^/api/v1/readlists/(?P<id>[^/]+)$"),
    ("GET", r"^/api/v1/readlists/(?P<id>[^/]+)/books$"),
    ("GET", r"^/api/v1/readlists/(?P<id>[^/]+)/books/(?P<bookId>[^/]+)/next$"),
    ("GET", r"^/api/v1/readlists/(?P<id>[^/]+)/books/(?P<bookId>[^/]+)/previous$"),
    ("POST", r"^/api/v1/readlists$"),
    ("PATCH", r"^/api/v1/readlists/(?P<id>[^/]+)$"),
    ("DELETE", r"^/api/v1/readlists/(?P<id>[^/]+)$"),
    ("GET", r"^/api/v2/authors$"),
    ("GET", r"^/api/v2/authors/names$"),
    ("GET", r"^/api/v2/authors/roles$"),
    ("GET", r"^/api/v2/tags$"),
    ("GET", r"^/api/v2/genres$"),
    ("GET", r"^/api/v2/publishers$"),
    ("GET", r"^/api/v2/languages$"),
    ("GET", r"^/api/v2/age-ratings$"),
    ("GET", r"^/api/v2/sharing-labels$"),
    ("GET", r"^/api/v2/series/release-years$"),
    ("GET", r"^/api/v2/users/me$"),
    ("GET", r"^/api/v2/users$"),
    ("POST", r"^/api/v2/users$"),
    ("PATCH", r"^/api/v2/users/(?P<id>[^/]+)$"),
    ("DELETE", r"^/api/v2/users/(?P<id>[^/]+)$"),
    ("PATCH", r"^/api/v2/users/me/password$"),
    ("PATCH", r"^/api/v2/users/(?P<id>[^/]+)/password$"),
    ("GET", r"^/api/v2/users/me/api-keys$"),
    ("POST", r"^/api/v2/users/me/api-keys$"),
    ("DELETE", r"^/api/v2/users/me/api-keys/(?P<keyId>[^/]+)$"),
    ("GET", r"^/api/v2/users/me/authentication-activity$"),
    ("GET", r"^/api/v2/users/authentication-activity$"),
    ("GET", r"^/api/v1/settings$"),
    ("PATCH", r"^/api/v1/settings$"),
    ("GET", r"^/api/v1/claim$"),
    ("GET", r"^/api/v1/history$"),
    ("POST", r"^/api/v1/filesystem$"),
    ("GET", r"^/actuator/info$"),
    ("DELETE", r"^/api/v1/tasks$"),
}

_CONTRACT = {(method, re.compile(pattern)) for method, pattern in KOMGA_CONTRACT}


def _contract_match(method: str, path: str) -> bool:
    return any(method == m and p.match(path) for m, p in _CONTRACT)


class Recorder:
    def __init__(self):
        self.method = None
        self.url = None
        self.headers = None
        self.json = None
        self.response = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.method = request.method
        self.url = request.url
        self.headers = request.headers
        self.json = json.loads(request.content) if request.content else None
        if self.response is not None:
            return self.response
        path = request.url.raw_path.split(b"?")[0].decode()
        if _contract_match(request.method, path):
            return httpx.Response(200, json={"success": True})
        return httpx.Response(405, json={"message": "no such Komga route"})


@pytest.fixture
def recorder():
    return Recorder()


@pytest_asyncio.fixture
async def server(recorder, monkeypatch):
    client = komga_mcp.build_client(
        "https://komga.example.com",
        "test-key",
        transport=httpx.MockTransport(recorder.handler),
    )
    monkeypatch.setattr(komga_mcp, "_client", client)
    yield komga_mcp.mcp
    await client.aclose()


async def call(server, name, **kwargs):
    async with Client(server) as client:
        return await client.call_tool(name, kwargs)


CASES = [
    ("list_libraries", {}, "GET", "/api/v1/libraries"),
    ("get_library", {"library_id": "library 1"}, "GET", "/api/v1/libraries/library%201"),
    ("create_library", {"library": {"name": "Library"}}, "POST", "/api/v1/libraries"),
    ("update_library", {"library_id": "l1", "patch": {"name": "New"}}, "PATCH", "/api/v1/libraries/l1"),
    ("delete_library", {"library_id": "l1"}, "DELETE", "/api/v1/libraries/l1"),
    ("scan_library", {"library_id": "l1"}, "POST", "/api/v1/libraries/l1/scan"),
    ("analyze_library", {"library_id": "l1"}, "POST", "/api/v1/libraries/l1/analyze"),
    ("refresh_library_metadata", {"library_id": "l1"}, "POST", "/api/v1/libraries/l1/metadata/refresh"),
    ("empty_library_trash", {"library_id": "l1"}, "POST", "/api/v1/libraries/l1/empty-trash"),
    ("search_series", {"full_text": "manga", "condition": {"readStatus": {"operator": "is", "value": "UNREAD"}}}, "POST", "/api/v1/series/list"),
    ("search_series_alphabetical_groups", {}, "POST", "/api/v1/series/list/alphabetical-groups"),
    ("get_series", {"series_id": "series 1"}, "GET", "/api/v1/series/series%201"),
    ("get_series_collections", {"series_id": "s1"}, "GET", "/api/v1/series/s1/collections"),
    ("get_latest_series", {}, "GET", "/api/v1/series/latest"),
    ("get_new_series", {}, "GET", "/api/v1/series/new"),
    ("get_updated_series", {}, "GET", "/api/v1/series/updated"),
    ("list_series_thumbnails", {"series_id": "s1"}, "GET", "/api/v1/series/s1/thumbnails"),
    ("update_series_metadata", {"series_id": "s1", "patch": {"title": "New"}}, "PATCH", "/api/v1/series/s1/metadata"),
    ("refresh_series_metadata", {"series_id": "s1"}, "POST", "/api/v1/series/s1/metadata/refresh"),
    ("analyze_series", {"series_id": "s1"}, "POST", "/api/v1/series/s1/analyze"),
    ("mark_series_read", {"series_id": "s1"}, "POST", "/api/v1/series/s1/read-progress"),
    ("mark_series_unread", {"series_id": "s1"}, "DELETE", "/api/v1/series/s1/read-progress"),
    ("search_books", {"full_text": "chapter"}, "POST", "/api/v1/books/list"),
    ("get_book", {"book_id": "book 1"}, "GET", "/api/v1/books/book%201"),
    ("get_book_pages", {"book_id": "b1"}, "GET", "/api/v1/books/b1/pages"),
    ("get_book_next", {"book_id": "b1"}, "GET", "/api/v1/books/b1/next"),
    ("get_book_previous", {"book_id": "b1"}, "GET", "/api/v1/books/b1/previous"),
    ("get_book_readlists", {"book_id": "b1"}, "GET", "/api/v1/books/b1/readlists"),
    ("list_book_thumbnails", {"book_id": "b1"}, "GET", "/api/v1/books/b1/thumbnails"),
    ("get_latest_books", {}, "GET", "/api/v1/books/latest"),
    ("get_books_ondeck", {}, "GET", "/api/v1/books/ondeck"),
    ("get_duplicate_books", {}, "GET", "/api/v1/books/duplicates"),
    ("update_book_metadata", {"book_id": "b1", "patch": {"title": "New"}}, "PATCH", "/api/v1/books/b1/metadata"),
    ("update_books_metadata_bulk", {"updates": {"b1": {"title": "New"}}}, "PATCH", "/api/v1/books/metadata"),
    ("refresh_book_metadata", {"book_id": "b1"}, "POST", "/api/v1/books/b1/metadata/refresh"),
    ("analyze_book", {"book_id": "b1"}, "POST", "/api/v1/books/b1/analyze"),
    ("set_book_read_progress", {"book_id": "b1", "page": 4, "completed": False}, "PATCH", "/api/v1/books/b1/read-progress"),
    ("mark_book_unread", {"book_id": "b1"}, "DELETE", "/api/v1/books/b1/read-progress"),
    ("list_collections", {"search": "favorites", "library_id": ["l1"]}, "GET", "/api/v1/collections"),
    ("get_collection", {"collection_id": "c 1"}, "GET", "/api/v1/collections/c%201"),
    ("get_collection_series", {"collection_id": "c1", "genre": ["Sci-Fi"]}, "GET", "/api/v1/collections/c1/series"),
    ("create_collection", {"collection": {"name": "Favorites"}}, "POST", "/api/v1/collections"),
    ("update_collection", {"collection_id": "c1", "patch": {"name": "New"}}, "PATCH", "/api/v1/collections/c1"),
    ("delete_collection", {"collection_id": "c1"}, "DELETE", "/api/v1/collections/c1"),
    ("list_readlists", {"search": "weekend"}, "GET", "/api/v1/readlists"),
    ("get_readlist", {"readlist_id": "r1"}, "GET", "/api/v1/readlists/r1"),
    ("get_readlist_books", {"readlist_id": "r1", "read_status": ["UNREAD"]}, "GET", "/api/v1/readlists/r1/books"),
    ("get_readlist_book_next", {"readlist_id": "r1", "book_id": "b1"}, "GET", "/api/v1/readlists/r1/books/b1/next"),
    ("get_readlist_book_previous", {"readlist_id": "r1", "book_id": "b1"}, "GET", "/api/v1/readlists/r1/books/b1/previous"),
    ("create_readlist", {"readlist": {"name": "Weekend"}}, "POST", "/api/v1/readlists"),
    ("update_readlist", {"readlist_id": "r1", "patch": {"name": "New"}}, "PATCH", "/api/v1/readlists/r1"),
    ("delete_readlist", {"readlist_id": "r1"}, "DELETE", "/api/v1/readlists/r1"),
    ("list_authors", {"role": "writer", "library_id": ["l1"]}, "GET", "/api/v2/authors"),
    ("list_author_names", {}, "GET", "/api/v2/authors/names"),
    ("list_author_roles", {}, "GET", "/api/v2/authors/roles"),
    ("list_tags", {"include": "BOTH"}, "GET", "/api/v2/tags"),
    ("list_genres", {}, "GET", "/api/v2/genres"),
    ("list_publishers", {}, "GET", "/api/v2/publishers"),
    ("list_languages", {}, "GET", "/api/v2/languages"),
    ("list_age_ratings", {}, "GET", "/api/v2/age-ratings"),
    ("list_sharing_labels", {}, "GET", "/api/v2/sharing-labels"),
    ("list_series_release_years", {}, "GET", "/api/v2/series/release-years"),
    ("whoami", {}, "GET", "/api/v2/users/me"),
    ("list_users", {}, "GET", "/api/v2/users"),
    ("create_user", {"user": {"email": "user@example.com"}}, "POST", "/api/v2/users"),
    ("update_user", {"user_id": "u1", "patch": {"email": "new@example.com"}}, "PATCH", "/api/v2/users/u1"),
    ("delete_user", {"user_id": "u1"}, "DELETE", "/api/v2/users/u1"),
    ("change_my_password", {"password": {"oldPassword": "old", "newPassword": "new"}}, "PATCH", "/api/v2/users/me/password"),
    ("change_user_password", {"user_id": "u1", "password": {"password": "new"}}, "PATCH", "/api/v2/users/u1/password"),
    ("list_my_api_keys", {}, "GET", "/api/v2/users/me/api-keys"),
    ("create_api_key", {"request": {"name": "MCP"}}, "POST", "/api/v2/users/me/api-keys"),
    ("delete_api_key", {"key_id": "key 1"}, "DELETE", "/api/v2/users/me/api-keys/key%201"),
    ("list_my_auth_activity", {}, "GET", "/api/v2/users/me/authentication-activity"),
    ("list_auth_activity", {}, "GET", "/api/v2/users/authentication-activity"),
    ("get_server_info", {}, "GET", "/actuator/info"),
    ("get_server_settings", {}, "GET", "/api/v1/settings"),
    ("update_server_settings", {"patch": {"application": {}}}, "PATCH", "/api/v1/settings"),
    ("get_server_claim_status", {}, "GET", "/api/v1/claim"),
    ("get_server_history", {}, "GET", "/api/v1/history"),
    ("clear_server_tasks", {}, "DELETE", "/api/v1/tasks"),
    ("list_filesystem", {"path": "/data", "show_files": True}, "POST", "/api/v1/filesystem"),
]


@pytest.mark.parametrize("name,kwargs,method,path", CASES)
async def test_every_tool_makes_expected_request(server, recorder, name, kwargs, method, path):
    result = await call(server, name, **kwargs)
    assert result.data == {"success": True}
    assert recorder.method == method
    assert recorder.url.raw_path.split(b"?")[0].decode() == path


def test_parametrized_cases_satisfy_contract():
    for name, _kwargs, method, path in CASES:
        assert _contract_match(method, path), f"{name}: {method} {path} not covered by KOMGA_CONTRACT"


async def test_search_encodes_body_and_pagination(server, recorder):
    await call(server, "search_books", full_text="one", page=2, size=10, sort=["metadata.title,asc", "numberSort,desc"])
    assert recorder.json == {"fullTextSearch": "one"}
    assert recorder.url.params.get_list("sort") == ["metadata.title,asc", "numberSort,desc"]
    assert recorder.url.params["page"] == "2"
    assert recorder.url.params["size"] == "10"


async def test_filesystem_request_contains_required_fields(server, recorder):
    await call(server, "list_filesystem", path="/data", show_files=True)
    assert recorder.json == {"path": "/data", "showFiles": True}


async def test_auth_header_is_sent(server, recorder):
    await call(server, "whoami")
    assert recorder.headers["x-api-key"] == "test-key"


async def test_no_api_key_means_no_auth_header(recorder):
    client = komga_mcp.build_client(
        "https://komga.example.com",
        None,
        transport=httpx.MockTransport(recorder.handler),
    )
    komga_mcp._client = client
    await call(komga_mcp.mcp, "whoami")
    assert "x-api-key" not in recorder.headers
    await client.aclose()


async def test_error_message_reaches_caller(server, recorder):
    recorder.response = httpx.Response(404, json={"message": "Book not found"})
    with pytest.raises(ToolError, match="Book not found"):
        await call(server, "get_book", book_id="missing")


async def test_error_status_surfaces_for_non_json_body(server, recorder):
    recorder.response = httpx.Response(502, text="<html>Bad Gateway</html>")
    with pytest.raises(ToolError, match="502"):
        await call(server, "whoami")


def test_main_requires_url(monkeypatch):
    monkeypatch.delenv("KOMGA_URL", raising=False)
    monkeypatch.setenv("KOMGA_API_KEY", "key")
    with pytest.raises(SystemExit):
        komga_mcp.main()


def test_main_requires_api_key(monkeypatch):
    monkeypatch.setenv("KOMGA_URL", "https://komga.example.com")
    monkeypatch.delenv("KOMGA_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        komga_mcp.main()
