"""MCP tools for the Komga REST API.

Full API coverage, exposed as 8 resource-scoped *portmanteau* tools instead
of one tool per endpoint. Each portmanteau tool (e.g. komga_series,
komga_books) takes an `operation` enum plus an `arguments` dict; see
AGENTS.md for the rationale (an 80+-tool server blows the MCP context budget
on session start). `_GROUPS` near the bottom buckets every endpoint function
by resource and `_register_group` wraps each bucket in one dispatching MCP
tool; the functions themselves are not tools anymore (and stay unprefixed,
e.g. `list_libraries` - only the group tool names carry `komga_`).

Komga exposes its REST API below ``/api/v1`` and ``/api/v2``. Authentication
uses an API key in the ``X-API-Key`` header. The server deliberately returns
Komga's JSON responses without reshaping them so an MCP client can use the
same information as Komga's own web client.
"""

from __future__ import annotations

import inspect
import os
import sys
from typing import Any, Literal
from urllib.parse import quote

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

JSONObj = dict[str, Any]
JSONVal = JSONObj | list[Any] | str | int | float | bool | None

READONLY = ToolAnnotations(readOnlyHint=True)
DESTRUCTIVE = ToolAnnotations(destructiveHint=True)

mcp = FastMCP("komga-mcp")
_client: httpx.AsyncClient | None = None


def build_client(
    base_url: str,
    api_key: str | None,
    verify: bool = True,
    transport: httpx.BaseTransport | None = None,
) -> httpx.AsyncClient:
    """Build the HTTP client; ``transport`` is used by the offline tests."""
    headers = {"X-API-Key": api_key} if api_key else {}
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        headers=headers,
        verify=verify,
        transport=transport,
    )


def _id(value: str) -> str:
    return quote(value, safe="")


def _params(
    *,
    page: int | None = None,
    size: int | None = None,
    sort: list[str] | None = None,
    unpaged: bool = False,
    **values: Any,
) -> list[tuple[str, Any]]:
    result: list[tuple[str, Any]] = []
    if page is not None:
        result.append(("page", page))
    if size is not None:
        result.append(("size", size))
    if sort:
        result.extend(("sort", value) for value in sort)
    if unpaged:
        result.append(("unpaged", "true"))
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, list):
            result.extend((key, item) for item in value)
        else:
            result.append((key, value))
    return result


async def _req(
    method: str,
    path: str,
    json: Any = None,
    params: list[tuple[str, Any]] | None = None,
) -> JSONVal:
    if _client is None:
        raise ToolError("Komga client is not configured")
    response = await _client.request(method, path, json=json, params=params)
    if response.status_code >= 400:
        try:
            payload = response.json()
            message = (
                payload.get("message", response.text)
                if isinstance(payload, dict)
                else response.text
            )
        except ValueError:
            message = response.text
        raise ToolError(f"Komga API {response.status_code}: {message}")
    if response.status_code == 204 or not response.content:
        return {"success": True}
    return response.json()


def _search_body(full_text: str, condition: JSONObj | None) -> JSONObj:
    body: JSONObj = {"fullTextSearch": full_text}
    if condition is not None:
        body["condition"] = condition
    return body


def _common_page_params(
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
    **values: Any,
) -> list[tuple[str, Any]]:
    return _params(page=page, size=size, sort=sort, unpaged=unpaged, **values)


# Libraries -----------------------------------------------------------------


async def list_libraries() -> JSONVal:
    """List libraries visible to the authenticated Komga user."""
    return await _req("GET", "/api/v1/libraries")


async def get_library(library_id: str) -> JSONObj:
    """Get one library by ID."""
    return await _req("GET", f"/api/v1/libraries/{_id(library_id)}")  # type: ignore[return-value]


async def create_library(library: JSONObj) -> JSONObj:
    """Create a library. Requires the Komga ADMIN role."""
    return await _req("POST", "/api/v1/libraries", library)  # type: ignore[return-value]


async def update_library(library_id: str, patch: JSONObj) -> JSONObj:
    """Partially update a library. Requires the Komga ADMIN role."""
    return await _req("PATCH", f"/api/v1/libraries/{_id(library_id)}", patch)  # type: ignore[return-value]


async def delete_library(library_id: str) -> JSONObj:
    """Delete a library without deleting its files. Requires ADMIN."""
    return await _req("DELETE", f"/api/v1/libraries/{_id(library_id)}")  # type: ignore[return-value]


async def scan_library(library_id: str, deep: bool = False) -> JSONVal:
    """Scan a library for new or changed files. Requires ADMIN."""
    return await _req(
        "POST", f"/api/v1/libraries/{_id(library_id)}/scan", params=_params(deep=deep)
    )


async def analyze_library(library_id: str) -> JSONVal:
    """Analyze all books in a library. Requires ADMIN."""
    return await _req("POST", f"/api/v1/libraries/{_id(library_id)}/analyze")


async def refresh_library_metadata(library_id: str) -> JSONVal:
    """Refresh embedded metadata for a library. Requires ADMIN."""
    return await _req("POST", f"/api/v1/libraries/{_id(library_id)}/metadata/refresh")


async def empty_library_trash(library_id: str) -> JSONVal:
    """Permanently empty a library's trash. Requires ADMIN."""
    return await _req("POST", f"/api/v1/libraries/{_id(library_id)}/empty-trash")


# Series --------------------------------------------------------------------

SEARCH_DOC = """Structured condition leaves are keyed by fields such as
libraryId, collectionId, title, tag, genre, publisher, language, ageRating,
readStatus, seriesStatus, mediaStatus, author, deleted, complete, oneShot,
releaseDate, numberSort, and seriesId. Each leaf contains an operator object.
Use string operators is, isNot, beginsWith, doesNotBeginWith, contains,
doesNotContain, endsWith, or doesNotEndWith; booleans use isTrue/isFalse;
dates use after/before/isInTheLast/isNotInTheLast/isNull/isNotNull; and group
conditions with anyOf (OR) or allOf (AND). Read-status values are UNREAD,
READ, IN_PROGRESS; media-status values are UNKNOWN, ERROR, READY, UNSUPPORTED,
OUTDATED; series-status values are ENDED, ONGOING, ABANDONED, HIATUS.
"""


async def search_series(
    full_text: str = "",
    condition: JSONObj | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """Search series using Komga's SeriesSearch body."""
    return await _req(
        "POST",
        "/api/v1/series/list",
        _search_body(full_text, condition),
        _common_page_params(page, size, sort, unpaged),
    )


# An f-string is not a docstring - the assignments below are the actual fix
# for a bug where these three tools shipped with __doc__ == None (FastMCP
# fell back to no description). Keep SEARCH_DOC as the single source of
# truth for the search-condition syntax and splice it in explicitly.
search_series.__doc__ = f"{search_series.__doc__} {SEARCH_DOC}"


async def search_series_alphabetical_groups(
    full_text: str = "",
    condition: JSONObj | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List series grouped alphabetically."""
    return await _req(
        "POST",
        "/api/v1/series/list/alphabetical-groups",
        _search_body(full_text, condition),
        _common_page_params(page, size, sort, unpaged),
    )


search_series_alphabetical_groups.__doc__ = (
    f"{search_series_alphabetical_groups.__doc__} {SEARCH_DOC}"
)


async def get_series(series_id: str) -> JSONObj:
    """Get series details and metadata by ID."""
    return await _req("GET", f"/api/v1/series/{_id(series_id)}")  # type: ignore[return-value]


async def get_series_collections(series_id: str) -> JSONVal:
    """List collections containing a series."""
    return await _req("GET", f"/api/v1/series/{_id(series_id)}/collections")


def _series_feed_params(
    library_id: list[str] | None,
    deleted: bool | None,
    oneshot: bool | None,
    page: int,
    size: int,
    sort: list[str] | None,
    unpaged: bool,
) -> list[tuple[str, Any]]:
    return _common_page_params(
        page,
        size,
        sort,
        unpaged,
        library_id=library_id,
        deleted=deleted,
        oneshot=oneshot,
    )


async def get_latest_series(
    library_id: list[str] | None = None,
    deleted: bool | None = None,
    oneshot: bool | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List recently added or updated series."""
    return await _req(
        "GET",
        "/api/v1/series/latest",
        params=_series_feed_params(
            library_id, deleted, oneshot, page, size, sort, unpaged
        ),
    )


async def get_new_series(
    library_id: list[str] | None = None,
    deleted: bool | None = None,
    oneshot: bool | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List newly added series."""
    return await _req(
        "GET",
        "/api/v1/series/new",
        params=_series_feed_params(
            library_id, deleted, oneshot, page, size, sort, unpaged
        ),
    )


async def get_updated_series(
    library_id: list[str] | None = None,
    deleted: bool | None = None,
    oneshot: bool | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List series that were updated but are not newly added."""
    return await _req(
        "GET",
        "/api/v1/series/updated",
        params=_series_feed_params(
            library_id, deleted, oneshot, page, size, sort, unpaged
        ),
    )


async def list_series_thumbnails(series_id: str) -> JSONVal:
    """List thumbnail metadata for a series; does not download image bytes."""
    return await _req("GET", f"/api/v1/series/{_id(series_id)}/thumbnails")


async def update_series_metadata(series_id: str, patch: JSONObj) -> JSONObj:
    """Update series metadata; null unsets a field and omission keeps it. Requires ADMIN."""
    return await _req("PATCH", f"/api/v1/series/{_id(series_id)}/metadata", patch)  # type: ignore[return-value]


async def refresh_series_metadata(series_id: str) -> JSONVal:
    """Re-import embedded series metadata. Requires ADMIN."""
    return await _req("POST", f"/api/v1/series/{_id(series_id)}/metadata/refresh")


async def analyze_series(series_id: str) -> JSONVal:
    """Analyze all books in a series. Requires ADMIN."""
    return await _req("POST", f"/api/v1/series/{_id(series_id)}/analyze")


async def mark_series_read(series_id: str) -> JSONVal:
    """Mark every book in a series as read."""
    return await _req("POST", f"/api/v1/series/{_id(series_id)}/read-progress")


async def mark_series_unread(series_id: str) -> JSONVal:
    """Mark every book in a series as unread."""
    return await _req("DELETE", f"/api/v1/series/{_id(series_id)}/read-progress")


# Books ---------------------------------------------------------------------


async def search_books(
    full_text: str = "",
    condition: JSONObj | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """Search books using Komga's BookSearch body."""
    return await _req(
        "POST",
        "/api/v1/books/list",
        _search_body(full_text, condition),
        _common_page_params(page, size, sort, unpaged),
    )


search_books.__doc__ = f"{search_books.__doc__} {SEARCH_DOC}"


async def get_book(book_id: str) -> JSONObj:
    """Get book details, media information, metadata, and read progress."""
    return await _req("GET", f"/api/v1/books/{_id(book_id)}")  # type: ignore[return-value]


async def get_book_pages(book_id: str) -> JSONVal:
    """List page metadata for a book without downloading page images."""
    return await _req("GET", f"/api/v1/books/{_id(book_id)}/pages")


async def get_book_next(book_id: str) -> JSONObj:
    """Get the next book in the series."""
    return await _req("GET", f"/api/v1/books/{_id(book_id)}/next")  # type: ignore[return-value]


async def get_book_previous(book_id: str) -> JSONObj:
    """Get the previous book in the series."""
    return await _req("GET", f"/api/v1/books/{_id(book_id)}/previous")  # type: ignore[return-value]


async def get_book_readlists(book_id: str) -> JSONVal:
    """List readlists containing a book."""
    return await _req("GET", f"/api/v1/books/{_id(book_id)}/readlists")


async def list_book_thumbnails(book_id: str) -> JSONVal:
    """List thumbnail metadata for a book; does not download image bytes."""
    return await _req("GET", f"/api/v1/books/{_id(book_id)}/thumbnails")


def _book_feed_params(
    library_id: list[str] | None,
    page: int,
    size: int,
    sort: list[str] | None,
    unpaged: bool,
) -> list[tuple[str, Any]]:
    return _common_page_params(page, size, sort, unpaged, library_id=library_id)


async def get_latest_books(
    library_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List recently added or updated books."""
    return await _req(
        "GET",
        "/api/v1/books/latest",
        params=_book_feed_params(library_id, page, size, sort, unpaged),
    )


async def get_books_ondeck(
    library_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List books currently on deck for the authenticated user."""
    return await _req(
        "GET",
        "/api/v1/books/ondeck",
        params=_book_feed_params(library_id, page, size, sort, unpaged),
    )


async def get_duplicate_books(
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List duplicate books by file hash. Requires ADMIN."""
    return await _req(
        "GET",
        "/api/v1/books/duplicates",
        params=_common_page_params(page, size, sort, unpaged),
    )


async def update_book_metadata(book_id: str, patch: JSONObj) -> JSONObj:
    """Update book metadata; null unsets a field and omission keeps it. Requires ADMIN."""
    return await _req("PATCH", f"/api/v1/books/{_id(book_id)}/metadata", patch)  # type: ignore[return-value]


async def update_books_metadata_bulk(updates: JSONObj) -> JSONVal:
    """Bulk update book metadata using a map of book ID to patch. Requires ADMIN."""
    return await _req("PATCH", "/api/v1/books/metadata", updates)


async def refresh_book_metadata(book_id: str) -> JSONVal:
    """Re-import embedded metadata for a book. Requires ADMIN."""
    return await _req("POST", f"/api/v1/books/{_id(book_id)}/metadata/refresh")


async def analyze_book(book_id: str) -> JSONVal:
    """Analyze a book. Requires ADMIN."""
    return await _req("POST", f"/api/v1/books/{_id(book_id)}/analyze")


async def set_book_read_progress(
    book_id: str, page: int | None = None, completed: bool | None = None
) -> JSONVal:
    """Set a book's read position. Supply page and/or completed."""
    body = {
        key: value
        for key, value in {"page": page, "completed": completed}.items()
        if value is not None
    }
    return await _req("PATCH", f"/api/v1/books/{_id(book_id)}/read-progress", body)


async def mark_book_unread(book_id: str) -> JSONVal:
    """Mark a book as unread."""
    return await _req("DELETE", f"/api/v1/books/{_id(book_id)}/read-progress")


# Collections ----------------------------------------------------------------


async def list_collections(
    search: str | None = None,
    library_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List collections, optionally filtered by search text or library."""
    return await _req(
        "GET",
        "/api/v1/collections",
        params=_common_page_params(
            page, size, sort, unpaged, search=search, library_id=library_id
        ),
    )


async def get_collection(collection_id: str) -> JSONObj:
    """Get collection details."""
    return await _req("GET", f"/api/v1/collections/{_id(collection_id)}")  # type: ignore[return-value]


async def get_collection_series(
    collection_id: str,
    status: list[str] | None = None,
    read_status: list[str] | None = None,
    publisher: list[str] | None = None,
    language: list[str] | None = None,
    genre: list[str] | None = None,
    tag: list[str] | None = None,
    age_rating: list[str] | None = None,
    release_year: list[str] | None = None,
    author: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List series in a collection using Komga's legacy filter query params."""
    return await _req(
        "GET",
        f"/api/v1/collections/{_id(collection_id)}/series",
        params=_common_page_params(
            page,
            size,
            sort,
            unpaged,
            status=status,
            read_status=read_status,
            publisher=publisher,
            language=language,
            genre=genre,
            tag=tag,
            age_rating=age_rating,
            release_year=release_year,
            author=author,
        ),
    )


async def create_collection(collection: JSONObj) -> JSONObj:
    """Create a collection. Requires ADMIN."""
    return await _req("POST", "/api/v1/collections", collection)  # type: ignore[return-value]


async def update_collection(collection_id: str, patch: JSONObj) -> JSONObj:
    """Update a collection. Requires ADMIN."""
    return await _req("PATCH", f"/api/v1/collections/{_id(collection_id)}", patch)  # type: ignore[return-value]


async def delete_collection(collection_id: str) -> JSONVal:
    """Delete a collection. Requires ADMIN."""
    return await _req("DELETE", f"/api/v1/collections/{_id(collection_id)}")


# Readlists ------------------------------------------------------------------


async def list_readlists(
    search: str | None = None,
    library_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List readlists, optionally filtered by search text or library."""
    return await _req(
        "GET",
        "/api/v1/readlists",
        params=_common_page_params(
            page, size, sort, unpaged, search=search, library_id=library_id
        ),
    )


async def get_readlist(readlist_id: str) -> JSONObj:
    """Get readlist details."""
    return await _req("GET", f"/api/v1/readlists/{_id(readlist_id)}")  # type: ignore[return-value]


async def get_readlist_books(
    readlist_id: str,
    library_id: list[str] | None = None,
    read_status: list[str] | None = None,
    tag: list[str] | None = None,
    media_status: list[str] | None = None,
    deleted: bool | None = None,
    author: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List books in a readlist using Komga's filter query params."""
    return await _req(
        "GET",
        f"/api/v1/readlists/{_id(readlist_id)}/books",
        params=_common_page_params(
            page,
            size,
            sort,
            unpaged,
            library_id=library_id,
            read_status=read_status,
            tag=tag,
            media_status=media_status,
            deleted=deleted,
            author=author,
        ),
    )


async def get_readlist_book_next(readlist_id: str, book_id: str) -> JSONObj:
    """Get the next book in a readlist."""
    return await _req(
        "GET", f"/api/v1/readlists/{_id(readlist_id)}/books/{_id(book_id)}/next"
    )  # type: ignore[return-value]


async def get_readlist_book_previous(readlist_id: str, book_id: str) -> JSONObj:
    """Get the previous book in a readlist."""
    return await _req(
        "GET", f"/api/v1/readlists/{_id(readlist_id)}/books/{_id(book_id)}/previous"
    )  # type: ignore[return-value]


async def create_readlist(readlist: JSONObj) -> JSONObj:
    """Create a readlist. Requires ADMIN."""
    return await _req("POST", "/api/v1/readlists", readlist)  # type: ignore[return-value]


async def update_readlist(readlist_id: str, patch: JSONObj) -> JSONObj:
    """Update a readlist. Requires ADMIN."""
    return await _req("PATCH", f"/api/v1/readlists/{_id(readlist_id)}", patch)  # type: ignore[return-value]


async def delete_readlist(readlist_id: str) -> JSONVal:
    """Delete a readlist. Requires ADMIN."""
    return await _req("DELETE", f"/api/v1/readlists/{_id(readlist_id)}")


# Referential metadata ------------------------------------------------------


async def _referential(
    path: str,
    search: str | None = None,
    library_id: list[str] | None = None,
    collection_id: list[str] | None = None,
    series_id: list[str] | None = None,
    readlist_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
    **extra: Any,
) -> JSONVal:
    return await _req(
        "GET",
        path,
        params=_common_page_params(
            page,
            size,
            sort,
            unpaged,
            search=search,
            library_id=library_id,
            collection_id=collection_id,
            series_id=series_id,
            readlist_id=readlist_id,
            **extra,
        ),
    )


async def list_authors(
    search: str | None = None,
    role: str | None = None,
    library_id: list[str] | None = None,
    collection_id: list[str] | None = None,
    series_id: list[str] | None = None,
    readlist_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List author names and roles used by the library."""
    return await _referential(
        "/api/v2/authors",
        search,
        library_id,
        collection_id,
        series_id,
        readlist_id,
        page,
        size,
        sort,
        unpaged,
        role=role,
    )


async def list_author_names(
    search: str | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List distinct author names."""
    return await _referential(
        "/api/v2/authors/names",
        search,
        page=page,
        size=size,
        sort=sort,
        unpaged=unpaged,
    )


async def list_author_roles(
    search: str | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List distinct author roles."""
    return await _referential(
        "/api/v2/authors/roles",
        search,
        page=page,
        size=size,
        sort=sort,
        unpaged=unpaged,
    )


async def list_tags(
    search: str | None = None,
    include: str | None = None,
    library_id: list[str] | None = None,
    collection_id: list[str] | None = None,
    series_id: list[str] | None = None,
    readlist_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List distinct tags; include can be SERIES, BOOK, or BOTH."""
    return await _referential(
        "/api/v2/tags",
        search,
        library_id,
        collection_id,
        series_id,
        readlist_id,
        page,
        size,
        sort,
        unpaged,
        include=include,
    )


async def list_genres(
    search: str | None = None,
    library_id: list[str] | None = None,
    collection_id: list[str] | None = None,
    series_id: list[str] | None = None,
    readlist_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List distinct genres."""
    return await _referential(
        "/api/v2/genres",
        search,
        library_id,
        collection_id,
        series_id,
        readlist_id,
        page,
        size,
        sort,
        unpaged,
    )


async def list_publishers(
    search: str | None = None,
    library_id: list[str] | None = None,
    collection_id: list[str] | None = None,
    series_id: list[str] | None = None,
    readlist_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List distinct publishers."""
    return await _referential(
        "/api/v2/publishers",
        search,
        library_id,
        collection_id,
        series_id,
        readlist_id,
        page,
        size,
        sort,
        unpaged,
    )


async def list_languages(
    search: str | None = None,
    library_id: list[str] | None = None,
    collection_id: list[str] | None = None,
    series_id: list[str] | None = None,
    readlist_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List distinct languages."""
    return await _referential(
        "/api/v2/languages",
        search,
        library_id,
        collection_id,
        series_id,
        readlist_id,
        page,
        size,
        sort,
        unpaged,
    )


async def list_age_ratings(
    search: str | None = None,
    library_id: list[str] | None = None,
    collection_id: list[str] | None = None,
    series_id: list[str] | None = None,
    readlist_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List distinct age ratings."""
    return await _referential(
        "/api/v2/age-ratings",
        search,
        library_id,
        collection_id,
        series_id,
        readlist_id,
        page,
        size,
        sort,
        unpaged,
    )


async def list_sharing_labels(
    search: str | None = None,
    library_id: list[str] | None = None,
    collection_id: list[str] | None = None,
    series_id: list[str] | None = None,
    readlist_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List distinct sharing labels."""
    return await _referential(
        "/api/v2/sharing-labels",
        search,
        library_id,
        collection_id,
        series_id,
        readlist_id,
        page,
        size,
        sort,
        unpaged,
    )


async def list_series_release_years(
    search: str | None = None,
    library_id: list[str] | None = None,
    collection_id: list[str] | None = None,
    series_id: list[str] | None = None,
    readlist_id: list[str] | None = None,
    page: int = 0,
    size: int = 50,
    sort: list[str] | None = None,
    unpaged: bool = False,
) -> JSONVal:
    """List distinct series release years."""
    return await _referential(
        "/api/v2/series/release-years",
        search,
        library_id,
        collection_id,
        series_id,
        readlist_id,
        page,
        size,
        sort,
        unpaged,
    )


# Users and API keys ---------------------------------------------------------


async def whoami() -> JSONObj:
    """Return the currently authenticated user."""
    return await _req("GET", "/api/v2/users/me")  # type: ignore[return-value]


async def list_users(
    page: int = 0, size: int = 50, sort: list[str] | None = None, unpaged: bool = False
) -> JSONVal:
    """List users. Requires ADMIN."""
    return await _req(
        "GET", "/api/v2/users", params=_common_page_params(page, size, sort, unpaged)
    )


async def create_user(user: JSONObj) -> JSONObj:
    """Create a user. Requires ADMIN."""
    return await _req("POST", "/api/v2/users", user)  # type: ignore[return-value]


async def update_user(user_id: str, patch: JSONObj) -> JSONObj:
    """Update a user. Requires ADMIN."""
    return await _req("PATCH", f"/api/v2/users/{_id(user_id)}", patch)  # type: ignore[return-value]


async def delete_user(user_id: str) -> JSONVal:
    """Delete a user. Requires ADMIN."""
    return await _req("DELETE", f"/api/v2/users/{_id(user_id)}")


async def change_my_password(password: JSONObj) -> JSONVal:
    """Change the current user's password."""
    return await _req("PATCH", "/api/v2/users/me/password", password)


async def change_user_password(user_id: str, password: JSONObj) -> JSONVal:
    """Change another user's password. Requires ADMIN."""
    return await _req("PATCH", f"/api/v2/users/{_id(user_id)}/password", password)


async def list_my_api_keys() -> JSONVal:
    """List API keys belonging to the current user."""
    return await _req("GET", "/api/v2/users/me/api-keys")


async def create_api_key(request: JSONObj) -> JSONObj:
    """Create an API key for the current user."""
    return await _req("POST", "/api/v2/users/me/api-keys", request)  # type: ignore[return-value]


async def delete_api_key(key_id: str) -> JSONVal:
    """Revoke one of the current user's API keys."""
    return await _req("DELETE", f"/api/v2/users/me/api-keys/{_id(key_id)}")


async def list_my_auth_activity(
    page: int = 0, size: int = 50, sort: list[str] | None = None, unpaged: bool = False
) -> JSONVal:
    """List authentication activity for the current user."""
    return await _req(
        "GET",
        "/api/v2/users/me/authentication-activity",
        params=_common_page_params(page, size, sort, unpaged),
    )


async def list_auth_activity(
    page: int = 0, size: int = 50, sort: list[str] | None = None, unpaged: bool = False
) -> JSONVal:
    """List all authentication activity. Requires ADMIN."""
    return await _req(
        "GET",
        "/api/v2/users/authentication-activity",
        params=_common_page_params(page, size, sort, unpaged),
    )


# Server --------------------------------------------------------------------


async def get_server_info() -> JSONVal:
    """Get Komga build and runtime information. Requires ADMIN."""
    return await _req("GET", "/actuator/info")


async def get_server_settings() -> JSONObj:
    """Get server settings. Requires ADMIN."""
    return await _req("GET", "/api/v1/settings")  # type: ignore[return-value]


async def update_server_settings(patch: JSONObj) -> JSONObj:
    """Update server settings. Requires ADMIN."""
    return await _req("PATCH", "/api/v1/settings", patch)  # type: ignore[return-value]


async def get_server_claim_status() -> JSONVal:
    """Return whether the Komga server has been claimed."""
    return await _req("GET", "/api/v1/claim")


async def get_server_history(
    page: int = 0, size: int = 50, sort: list[str] | None = None, unpaged: bool = False
) -> JSONVal:
    """Get server event history. Requires ADMIN."""
    return await _req(
        "GET", "/api/v1/history", params=_common_page_params(page, size, sort, unpaged)
    )


async def clear_server_tasks() -> JSONVal:
    """Cancel all queued server tasks and return the number removed. Requires ADMIN."""
    return await _req("DELETE", "/api/v1/tasks")


async def list_filesystem(path: str, show_files: bool = False) -> JSONVal:
    """List server filesystem directories for library setup. Requires ADMIN."""
    body = {"path": path, "showFiles": show_files}
    return await _req("POST", "/api/v1/filesystem", body)


def _env_bool(value: str | None) -> bool:
    return value is None or value.strip().lower() not in {"0", "false", "no", "off"}


# Resource groups for portmanteau registration. Every tool function name
# must appear in exactly one group - see test_all_functions_grouped.
_GROUPS: dict[str, tuple[str, ...]] = {
    "komga_libraries": (
        "analyze_library",
        "create_library",
        "delete_library",
        "empty_library_trash",
        "get_library",
        "list_libraries",
        "refresh_library_metadata",
        "scan_library",
        "update_library",
    ),
    "komga_series": (
        "analyze_series",
        "get_latest_series",
        "get_new_series",
        "get_series",
        "get_series_collections",
        "get_updated_series",
        "list_series_thumbnails",
        "mark_series_read",
        "mark_series_unread",
        "refresh_series_metadata",
        "search_series",
        "search_series_alphabetical_groups",
        "update_series_metadata",
    ),
    "komga_books": (
        "analyze_book",
        "get_book",
        "get_book_next",
        "get_book_pages",
        "get_book_previous",
        "get_book_readlists",
        "get_books_ondeck",
        "get_duplicate_books",
        "get_latest_books",
        "list_book_thumbnails",
        "mark_book_unread",
        "refresh_book_metadata",
        "search_books",
        "set_book_read_progress",
        "update_book_metadata",
        "update_books_metadata_bulk",
    ),
    "komga_collections": (
        "create_collection",
        "delete_collection",
        "get_collection",
        "get_collection_series",
        "list_collections",
        "update_collection",
    ),
    "komga_readlists": (
        "create_readlist",
        "delete_readlist",
        "get_readlist",
        "get_readlist_book_next",
        "get_readlist_book_previous",
        "get_readlist_books",
        "list_readlists",
        "update_readlist",
    ),
    "komga_referential_metadata": (
        "list_age_ratings",
        "list_author_names",
        "list_author_roles",
        "list_authors",
        "list_genres",
        "list_languages",
        "list_publishers",
        "list_series_release_years",
        "list_sharing_labels",
        "list_tags",
    ),
    "komga_users_api_keys": (
        "change_my_password",
        "change_user_password",
        "create_api_key",
        "create_user",
        "delete_api_key",
        "delete_user",
        "list_auth_activity",
        "list_my_api_keys",
        "list_my_auth_activity",
        "list_users",
        "update_user",
        "whoami",
    ),
    "komga_server": (
        "clear_server_tasks",
        "get_server_claim_status",
        "get_server_history",
        "get_server_info",
        "get_server_settings",
        "list_filesystem",
        "update_server_settings",
    ),
}


def _op_line(name: str, fn: Any) -> str:
    """One line of a group tool's description: signature + one-line doc."""
    sig = ", ".join(
        p.name if p.default is inspect.Parameter.empty else f"{p.name}={p.default!r}"
        for p in inspect.signature(fn).parameters.values()
    )
    return f"- {name}({sig}) — {' '.join((fn.__doc__ or '').split())}"


def _register_group(
    group: str, names: tuple[str, ...], ns: dict[str, Any], readonly_names: set[str]
) -> None:
    """Register one dispatching tool that fans out to every function named
    in `names`. The functions themselves are untouched - they're just
    looked up by name instead of each becoming its own tool."""
    fns = {n: ns[n] for n in names}

    async def dispatch(
        operation: str, arguments: JSONObj | None = None
    ) -> JSONVal | str:
        fn = fns.get(operation)
        if fn is None:
            raise ToolError(
                f"Unknown operation {operation!r} for {group}. Valid: {', '.join(fns)}"
            )
        return await fn(**(arguments or {}))

    dispatch.__annotations__["operation"] = Literal[names]
    ann = READONLY if set(names) <= readonly_names else None
    mcp.add_tool(
        Tool.from_function(
            dispatch,
            name=group,
            description=(
                f"{group.replace('_', ' ')} operations on Komga. Pass `operation` and an "
                f"`arguments` dict matching that operation's parameters.\n\n"
                + "\n".join(_op_line(n, f) for n, f in fns.items())
            ),
            annotations=ann,
        )
    )


def _register_tools() -> None:
    ns = globals()
    readonly_names: set[str] = {
        "get_book",
        "get_book_next",
        "get_book_pages",
        "get_book_previous",
        "get_book_readlists",
        "get_books_ondeck",
        "get_collection",
        "get_collection_series",
        "get_duplicate_books",
        "get_latest_books",
        "get_latest_series",
        "get_library",
        "get_new_series",
        "get_readlist",
        "get_readlist_book_next",
        "get_readlist_book_previous",
        "get_readlist_books",
        "get_series",
        "get_series_collections",
        "get_server_claim_status",
        "get_server_history",
        "get_server_info",
        "get_server_settings",
        "get_updated_series",
        "list_age_ratings",
        "list_auth_activity",
        "list_author_names",
        "list_author_roles",
        "list_authors",
        "list_book_thumbnails",
        "list_collections",
        "list_filesystem",
        "list_genres",
        "list_languages",
        "list_libraries",
        "list_my_api_keys",
        "list_my_auth_activity",
        "list_publishers",
        "list_readlists",
        "list_series_release_years",
        "list_series_thumbnails",
        "list_sharing_labels",
        "list_tags",
        "list_users",
        "search_books",
        "search_series",
        "search_series_alphabetical_groups",
        "whoami",
    }
    for group, names in _GROUPS.items():
        _register_group(group, names, ns, readonly_names)


_register_tools()


def main() -> None:
    global _client
    url = os.environ.get("KOMGA_URL")
    api_key = os.environ.get("KOMGA_API_KEY")
    if not url:
        print(
            "KOMGA_URL environment variable is required (e.g. https://komga.example.com)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if not api_key:
        print("KOMGA_API_KEY environment variable is required", file=sys.stderr)
        raise SystemExit(1)
    _client = build_client(
        url, api_key, verify=_env_bool(os.environ.get("KOMGA_VERIFY_TLS"))
    )
    mcp.run()


if __name__ == "__main__":
    main()
