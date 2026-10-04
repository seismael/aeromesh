# Example catalog

These are unsigned, tool-free drafts, not approved production agents. They require a real configured model. Output schemas check structure, not factual accuracy. No signing identity or trust roots are shipped.

Use `amx run registry/agents/structured-summary.json "Text to summarize" --development` for a local evaluation, or build a release, review it, sign it with your own key, explicitly trust that key, and approve an operator policy. See the main README and `docs/RELEASES.md`.

The previous Postgres, cloud, payments, RAG, security and social-publishing examples were removed: their integrations and business outcomes were not validated. The real local MCP transport example is `examples/dependency-inventory/`.
