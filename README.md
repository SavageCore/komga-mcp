# komga-mcp

Part of the [arr-mcps](https://github.com/arr-mcps/arr-mcps) collection.
MCP server exposing [Komga](https://github.com/gotson/komga)'s REST API as
tools for browsing and managing comic, manga, BD, magazine, and ebook
libraries. It is built with [FastMCP](https://gofastmcp.com).

## Install

Download a wheel from the [latest release](https://github.com/arr-mcps/komga-mcp/releases/latest)
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

**8 resource-scoped tools**, each covering multiple Komga REST endpoints
(81 total) via an `operation` parameter. Call a tool with `operation` set
to one of its listed operations (the function names below, e.g.
`list_libraries`) and an `arguments` dict matching that operation's
parameters — the tool's own description (visible to your MCP client)
lists every operation, its signature, and a one-line doc, including any
"Requires ADMIN" notes. Image, file-download, page-stream, and multipart
ComicRack endpoints are intentionally excluded.

| Tool | Operations | Kind | Covers |
|---|---|---|---|
| `komga_libraries` | 9 | reads + writes | Libraries: list, get, create, update, delete, scan, analyze, refresh metadata, empty trash |
| `komga_series` | 13 | reads + writes | Series: search, get, collections, latest/new/updated, thumbnails, metadata, analyze, read progress |
| `komga_books` | 16 | reads + writes | Books: search, get, pages, next/previous, readlists, thumbnails, latest/ondeck/duplicates, metadata, analyze, read progress |
| `komga_collections` | 6 | reads + writes | Collections: list, get, series, create, update, delete |
| `komga_readlists` | 8 | reads + writes | Readlists: list, get, books, next/previous book, create, update, delete |
| `komga_referential_metadata` | 10 | read-only | Authors, tags, genres, publishers, languages, age ratings, sharing labels, release years |
| `komga_users_api_keys` | 12 | reads + writes | whoami, users CRUD, passwords, API keys, auth activity |
| `komga_server` | 7 | reads + writes | Server info, settings, claim status, history, tasks, filesystem |

Example: `komga_libraries(operation="scan_library", arguments={"library_id": "l1"})`.

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
