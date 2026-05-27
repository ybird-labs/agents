# pi-context-hub

Pi extension wrapping [Context Hub](https://github.com/andrewyng/context-hub) (`@aisuite/chub`) so Pi can search and fetch current API/SDK docs without going through generic bash or MCP.

## Tools

- `chub_search` — search Context Hub docs and skills.
- `chub_get` — fetch a doc/skill by ID, language, version, specific file, or full entry.
- `chub_annotate` — manage local persistent annotations.
- `chub_feedback` — optionally send non-sensitive up/down doc feedback.

It also registers a `/chub` command for manual CLI access.

## Install locally while developing

From this directory:

```bash
npm install
pi -e .
```

Or install as a Pi package from the parent repo:

```bash
pi install ./pi-context-hub
```

If installed from a local path, run `npm install` in `pi-context-hub/` first so `@aisuite/chub` is available locally.

## Chub binary resolution

By default the extension runs the package-local `@aisuite/chub` binary with Node, so it does not depend on a global `chub` on `PATH`.

Overrides:

- `PI_CONTEXT_HUB_CHUB_BIN=/absolute/path/to/chub` — run a specific executable.
- `PI_CONTEXT_HUB_ALLOW_GLOBAL_CHUB=1` — explicitly allow fallback to `chub` from `PATH` if package-local resolution fails.

## Example prompts

```text
Use Context Hub docs and implement Stripe Checkout in TypeScript.
```

```text
Search current OpenAI Python SDK docs before writing the integration.
```

Manual command:

```text
/chub search openai
/chub get openai/chat --lang py
```

## Security notes

`chub_annotate` stores local notes under Context Hub's normal local config/cache area. Do not put secrets, private code, credentials, or sensitive architecture details in annotations or feedback.
