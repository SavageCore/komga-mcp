# AGENTS.md — komga-mcp

MCP server exposing Komga's REST API as tools for browsing and managing comic, manga, BD, magazine, and ebook libraries. Uses FastMCP, `uv` for deps.

Exposed as **8 resource-scoped portmanteau tools**, not one tool per endpoint — see "Portmanteau registration" below. A prior version registered all 81 endpoints individually; that blew the MCP context budget (~81 tools × ~250 tokens ≈ 20k tokens just for this one server) and has been retired.

## Testing
- Offline suite: `make test` (or `uv run pytest`)
- Live integration (needs `KOMGA_URL`/`KOMGA_API_KEY`): `make test-integration`

## Release workflow
Always use the `make bump-*` targets to bump the version (`uv version --bump patch|minor|major`), which updates `pyproject.toml` and `uv.lock` together. Do NOT edit the version by hand.

- Bump: `make bump-patch` (or `bump-minor` / `bump-major`)
- Commit message is **just the version**, e.g. `0.1.2` — nothing else.
- Tag it `v<version>` (e.g. `v0.1.2`).
- Push main and the tag:
  ```
  git push origin main
  git push origin v<version>
  ```
- Then sync the project copy:
  ```
  cd /home/savagecore/Documents/christopfarr/mcp/komga-mcp
  git fetch origin && git reset --hard origin/main
  ```
- Deploy to the Proxmox host (root SSH key): pull the repo then reinstall the uv tool:
  ```
  ssh root@192.168.50.3 -- 'cd /root/komga-mcp && git fetch origin && git reset --hard origin/main'
  ssh root@192.168.50.3 -- 'cd /root/komga-mcp && uv tool install --force .'
  ```
  The host runs it via `uv tool install` → `/root/.local/bin/komga-mcp` (not from the repo).

## Env note
All tools go through Komga's REST API keyed on `KOMGA_API_KEY`. Keep API keys out of code, logs, and commit messages. Responses are returned without reshaping so an MCP client can use the same information as Komga's own web client. 33 operations carry a "Requires ADMIN" / "Requires the Komga ADMIN role" note in their docstring — this is documentation-only (Komga itself enforces the role via a 403; nothing here checks it). Those notes survive automatically in each group tool's per-operation description since the underlying functions and their docstrings are unchanged by the portmanteau refactor.

## Portmanteau registration — **do not go back to one tool per endpoint**
- `_GROUPS` near the bottom of `komga_mcp.py` buckets every endpoint function into one of 8 resource groups (`komga_libraries`, `komga_series`, `komga_books`, ...) matching the file's own section headers exactly. `_register_tools()` registers exactly one MCP tool per group via `_register_group`, which wraps the group's functions in a single `dispatch(operation, arguments)` closure. The endpoint functions themselves are unchanged — they're plain callables looked up by name via `globals()`, not separately-registered tools. Function names stay unprefixed (`list_libraries`, not `komga_list_libraries`) as before; only the group *tool* names carry the `komga_` prefix.
- `operation` is typed `Literal[<the group's function names>]`, so FastMCP/pydantic validates it against the real operation list before `dispatch` ever runs — an invalid operation never reaches the group tool's body.
- Adding a new endpoint: write the function as before (no decorator), then add its name to exactly one group in `_GROUPS`. `tests/test_tools.py::test_all_cases_grouped` fails if a `CASES` entry doesn't match `_GROUPS` exactly.
- New resource area big enough to need its own group (rare): add a new `_GROUPS` key. Keep the total group count at or under ~15 — that ceiling is the entire point of this pattern; operations-per-group has no ceiling (e.g. `komga_books` carries 16 fine).
- If you're tempted to add a per-endpoint `@mcp.tool` decorator back, don't — every endpoint must be reachable only via its group's `operation` enum. An 81-tool server (one per endpoint) previously cost ~20k tokens of system-prompt budget on every session start; the 8-tool grouped version costs roughly a tenth of that.
- Annotations: a group tool is `readOnlyHint=True` (`READONLY`) only when *every* operation in it was originally read-only (tracked in `_register_tools()`'s `readonly_names` set). Mixed groups carry no hints.

## Fixed while refactoring: the f-string-docstring bug
`search_series`, `search_series_alphabetical_groups`, and `search_books` used to declare their docstring as `f"""... {SEARCH_DOC}"""` — an f-string is an *expression*, not a docstring, so `__doc__` was silently `None` for all three and they shipped with no description to MCP clients. Fixed by giving each a real string-literal docstring and appending `SEARCH_DOC` via an explicit `fn.__doc__ = f"{fn.__doc__} {SEARCH_DOC}"` assignment right after the function. If you add another tool that needs a shared doc fragment, follow that pattern — never put an f-string where Python expects a docstring.