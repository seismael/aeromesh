# Example catalog

The catalog contains unsigned, tool-free agent drafts and a dependency workflow for supplied-text summarization and review. They illustrate the supported v1 schemas and require a real configured model. Output contracts validate structure; independently evaluate factual accuracy and task quality.

For a local authoring evaluation:

```bash
amx run registry/agents/structured-summary.json 'Text to summarize' --development
```

For an approved run, build the workflow release, review all embedded manifests, sign it with your own key, explicitly trust the verified public key and approve an independent operator policy. The [main README](../README.md#first-approved-release) provides the complete sequence; [release documentation](../docs/RELEASES.md) defines the policy contract.

No signing identities or automatic trust roots are shipped. [Dependency inventory](../examples/dependency-inventory/README.md) provides a separate actual local MCP tool and an offline transport check.
