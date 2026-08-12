# AGENTS.md — komga-mcp

MCP server exposing Komga's REST API as tools for browsing and managing comic, manga, BD, magazine, and ebook libraries. Uses FastMCP, `uv` for deps.

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
All tools go through Komga's REST API keyed on `KOMGA_API_KEY`. Keep API keys out of code, logs, and commit messages.