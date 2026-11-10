<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: WORKSTATION_INTEGRATION_GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-11-06 -->
<!-- INSTRUCTION_REVIEW: documentation only; no runtime qualification -->

# Gemini and workstation integration

For GoodQ product work, follow [AGENTS.md](AGENTS.md). Use
[project orientation](docs/agent/PROJECT_ORIENTATION.md) when resolving ownership
between the repository, data, workstation tools and local agents.

This file supplies integration entrypoints, not live inventory or permission.
Inspect only the configuration relevant to the requested integration:

| Surface | Local discovery point |
| --- | --- |
| PowerShell command resolution | Current process PATH, then the active `$PROFILE` if diagnosis requires it |
| Gemini MCP registrations | `%USERPROFILE%/.gemini/config/mcp_config.json`, if present |
| Gemini permissions | `%USERPROFILE%/.gemini/config/config.json`, if present |
| Credentials | Approved environment-backed store, normally `%USERPROFILE%/.env.local` |
| GoodQ model selection and budget | Resolved project config and its owning runtime contract |
| Workstation services and launchers | Their owners beneath `<tools_root>` from orientation |

Verify the installed client's actual configuration paths and supported credential
mechanism before changing integration. Inspect metadata without exposing secret
values. A legacy literal secret is not permission to create another copy.

Do not infer current models, ports, GPU capacity, authentication or permission
grants from an old guide. Resolve them only when material to the task. Installing
software, changing profiles/PATH, adding model downloads, enabling cloud billing
or changing access requires authorization covering that action. The product
roadmap owns planned features; this file has no independent cluster or IDE plan.
