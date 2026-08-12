# komga-mcp

MCP server exposing [Komga](https://github.com/gotson/komga)'s REST API as
tools for browsing and managing comic, manga, BD, magazine, and ebook
libraries. It is built with [FastMCP](https://gofastmcp.com).

## Install

Download a wheel from the [latest release](https://github.com/SavageCore/komga-mcp/releases/latest)
and install it as a `uv` tool:

```bash
uv tool install komga_mcp-*.whl
```

Register it with Claude Code:

```bash
claude mcp add komga \
  --env KOMGA_URL=https://your-komga-host \
  --env KOMGA_API_KEY=<api-key> \
  -- komga-mcp
```

### From source

```bash
uv sync
cp .env.example .env
```

```bash
claude mcp add komga \
  --env KOMGA_URL=https://your-komga-host \
  --env KOMGA_API_KEY=<api-key> \
  -- uv run --directory /path/to/komga-mcp komga-mcp
```

## Configuration

Komga API keys are created in the Komga user settings. The key is sent as
`X-API-Key` on every request. The server does not accept credentials supplied
by an MCP tool call.

| Env var | Required | Default |
|---|---|---|
| `KOMGA_URL` | yes | - |
| `KOMGA_API_KEY` | yes | - |
| `KOMGA_VERIFY_TLS` | no | `true` |

`KOMGA_URL` is the server root, without `/api`; the client adds the documented
`/api/v1` and `/api/v2` paths itself. Set `KOMGA_VERIFY_TLS=false` only when a
self-signed certificate is intentional.

## Tools

The server exposes the useful JSON portions of Komga's REST API. Tools marked
ADMIN require the Komga administrator role. Image, file-download, page-stream,
and multipart ComicRack endpoints are intentionally excluded.

### Libraries

| Tool | Endpoint |
|---|---|
| `list_libraries` | `GET /api/v1/libraries` |
| `get_library` | `GET /api/v1/libraries/{libraryId}` |
| `create_library` | `POST /api/v1/libraries` (ADMIN) |
| `update_library` | `PATCH /api/v1/libraries/{libraryId}` (ADMIN) |
| `delete_library` | `DELETE /api/v1/libraries/{libraryId}` (ADMIN) |
| `scan_library` | `POST /api/v1/libraries/{libraryId}/scan` (ADMIN) |
| `analyze_library` | `POST /api/v1/libraries/{libraryId}/analyze` (ADMIN) |
| `refresh_library_metadata` | `POST /api/v1/libraries/{libraryId}/metadata/refresh` (ADMIN) |
| `empty_library_trash` | `POST /api/v1/libraries/{libraryId}/empty-trash` (ADMIN) |

### Series

| Tool | Endpoint |
|---|---|
| `search_series` | `POST /api/v1/series/list` |
| `search_series_alphabetical_groups` | `POST /api/v1/series/list/alphabetical-groups` |
| `get_series` | `GET /api/v1/series/{seriesId}` |
| `get_series_collections` | `GET /api/v1/series/{seriesId}/collections` |
| `get_latest_series` | `GET /api/v1/series/latest` |
| `get_new_series` | `GET /api/v1/series/new` |
| `get_updated_series` | `GET /api/v1/series/updated` |
| `list_series_thumbnails` | `GET /api/v1/series/{seriesId}/thumbnails` |
| `update_series_metadata` | `PATCH /api/v1/series/{seriesId}/metadata` (ADMIN) |
| `refresh_series_metadata` | `POST /api/v1/series/{seriesId}/metadata/refresh` (ADMIN) |
| `analyze_series` | `POST /api/v1/series/{seriesId}/analyze` (ADMIN) |
| `mark_series_read` | `POST /api/v1/series/{seriesId}/read-progress` |
| `mark_series_unread` | `DELETE /api/v1/series/{seriesId}/read-progress` |

### Books

| Tool | Endpoint |
|---|---|
| `search_books` | `POST /api/v1/books/list` |
| `get_book` | `GET /api/v1/books/{bookId}` |
| `get_book_pages` | `GET /api/v1/books/{bookId}/pages` |
| `get_book_next` | `GET /api/v1/books/{bookId}/next` |
| `get_book_previous` | `GET /api/v1/books/{bookId}/previous` |
| `get_book_readlists` | `GET /api/v1/books/{bookId}/readlists` |
| `list_book_thumbnails` | `GET /api/v1/books/{bookId}/thumbnails` |
| `get_latest_books` | `GET /api/v1/books/latest` |
| `get_books_ondeck` | `GET /api/v1/books/ondeck` |
| `get_duplicate_books` | `GET /api/v1/books/duplicates` (ADMIN) |
| `update_book_metadata` | `PATCH /api/v1/books/{bookId}/metadata` (ADMIN) |
| `update_books_metadata_bulk` | `PATCH /api/v1/books/metadata` (ADMIN) |
| `refresh_book_metadata` | `POST /api/v1/books/{bookId}/metadata/refresh` (ADMIN) |
| `analyze_book` | `POST /api/v1/books/{bookId}/analyze` (ADMIN) |
| `set_book_read_progress` | `PATCH /api/v1/books/{bookId}/read-progress` |
| `mark_book_unread` | `DELETE /api/v1/books/{bookId}/read-progress` |

### Collections and readlists

| Tool | Endpoint |
|---|---|
| `list_collections`, `get_collection`, `get_collection_series` | `GET /api/v1/collections...` (the latter supports filters) |
| `create_collection`, `update_collection`, `delete_collection` | `POST/PATCH/DELETE /api/v1/collections...` (ADMIN) |
| `list_readlists`, `get_readlist`, `get_readlist_books` | `GET /api/v1/readlists...` |
| `get_readlist_book_next`, `get_readlist_book_previous` | `GET /api/v1/readlists/{id}/books/{bookId}/next|previous` |
| `create_readlist`, `update_readlist`, `delete_readlist` | `POST/PATCH/DELETE /api/v1/readlists...` (ADMIN) |

### Referential metadata

`list_authors`, `list_author_names`, `list_author_roles`, `list_tags`,
`list_genres`, `list_publishers`, `list_languages`, `list_age_ratings`,
`list_sharing_labels`, and `list_series_release_years` expose the corresponding
read-only `/api/v2` endpoints and accept the relevant search, relationship,
pagination, and sorting filters.

### Users and server

`whoami`, `list_users`, `create_user`, `update_user`, `delete_user`,
`change_my_password`, `change_user_password`, `list_my_api_keys`,
`create_api_key`, `delete_api_key`, `list_my_auth_activity`, and
`list_auth_activity` expose user and API-key management.

`get_server_info`, `get_server_settings`, `update_server_settings`,
`get_server_claim_status`, `get_server_history`, `clear_server_tasks`, and
`list_filesystem` expose server administration and diagnostics.

## Search conditions

`search_series`, `search_books`, and `search_series_alphabetical_groups` send a
JSON body containing `fullTextSearch` and an optional recursive `condition`.
Pagination is sent as query parameters (`page`, `size`, repeated `sort`, and
`unpaged`). For example:

```json
{
  "fullTextSearch": "berserk",
  "condition": {
    "allOf": [
      {"genre": {"operator": "contains", "value": "action"}},
      {"readStatus": {"operator": "is", "value": "UNREAD"}}
    ]
  }
}
```

Use `anyOf` for OR and `allOf` for AND. String operators include `is`, `isNot`,
`beginsWith`, `contains`, `endsWith`, and their negative forms. Boolean fields
use `isTrue` or `isFalse`; date fields use `after`, `before`, `isInTheLast`,
`isNotInTheLast`, `isNull`, or `isNotNull`.

Metadata patches use Komga's normal semantics: omit a field to leave it alone,
or send `null` to unset it. Read progress accepts `page` and/or `completed`.

## Development

```bash
make help
```

| Command | Does |
|---|---|
| `make sync` | Run `uv sync` |
| `make test` | Run the offline test suite |
| `make test-integration` | Run live tests (needs `KOMGA_URL`/`KOMGA_API_KEY`) |
| `make build` | Build wheel and sdist into `dist/` |
| `make bump-patch` / `bump-minor` / `bump-major` | Bump package version and lockfile |
| `make clean` | Remove build artifacts |

The release workflow runs tests and publishes wheel and sdist files whenever a
`v*` tag is pushed.
