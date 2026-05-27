---
name: get-api-docs
description: Use Context Hub tools to fetch current API, SDK, and library documentation before writing code against external dependencies. Use when a task mentions a third-party package, SaaS API, SDK, framework API, or asks for latest/current docs.
---

# Get API Docs with Context Hub

Use the Pi Context Hub tools instead of relying on model memory when current API or SDK details matter.

## Workflow

1. Search for the relevant entry:

```text
chub_search({ query: "stripe checkout", lang: "ts" })
```

2. Fetch the best matching documentation before coding:

```text
chub_get({ id: "stripe/api", lang: "ts" })
```

3. If the returned doc lists additional files and one is relevant, fetch that file:

```text
chub_get({ id: "stripe/api", lang: "ts", file: "references/webhooks.md" })
```

4. If you discover a concise, reusable gotcha not already in the docs, save it locally:

```text
chub_annotate({ id: "stripe/api", action: "set", note: "Webhook verification requires the raw request body before JSON parsing." })
```

Do not store secrets, credentials, private source code, or sensitive architecture details in annotations or feedback.
