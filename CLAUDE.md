## Brain
Vault: C:\Users\fedor\Obsidian\Brain\
If this path is missing, ask for the current vault path before relying on vault context.

Before project work, read the relevant vault file first. Tiny commands and narrow file inspections do not require a vault read.
After significant changes, update the dev log and any docs affected by the change. Significant means behavior changes, architecture changes, deploy/ops changes, new external integrations, security/rate-limit changes, or test/audit changes that alter project status.

## Vault Structure for this project
| File | Use when |
|---|---|
| Projects/Stirlitz (IBP)/stirlitz-ibp.md | Default project overview; start here when context is unclear. |
| Projects/Stirlitz (IBP)/stirlitz-dev-log.md | Most recent session context; update after significant changes. |
| Projects/Stirlitz (IBP)/stirlitz-decisions.md | Open decisions and blockers. |
| Projects/Stirlitz (IBP)/stirlitz-architecture.md | Touching structure or module boundaries. |
| Projects/Stirlitz (IBP)/stirlitz-routes-blueprints.md | Touching routes, auth, or blueprints. |
| Projects/Stirlitz (IBP)/stirlitz-database-models.md | Touching models, migrations, or persistence behavior. |
| Projects/Stirlitz (IBP)/stirlitz-external-integrations.md | Touching APIs or external services. |
| Projects/Stirlitz (IBP)/stirlitz-known-issues.md | Debugging or triage. |
| Projects/Stirlitz (IBP)/stirlitz-ops-runbook.md | Deploying, production health, or ops work. Also see `docs/production-health-timeout-runbook.md`. |
| Projects/Stirlitz (IBP)/stirlitz-dev-setup.md | Setting up env or deployment prerequisites. |
| Projects/Stirlitz (IBP)/stirlitz-credentials.md | Integration status only. |
| Projects/Stirlitz (IBP)/stirlitz-pipeline-9-stages.md | Working on pipeline stages. |
| Projects/Stirlitz (IBP)/stirlitz-service-files.md | Working on service-layer code. |
| Projects/Stirlitz (IBP)/stirlitz-security-pentest.md | Touching auth, rate limits, DoS protection, or security posture. |
| Projects/Stirlitz (IBP)/stirlitz-ai-prompts.md | Working on Claude AI integration. |
| Projects/Stirlitz (IBP)/stirlitz-ideal-system-map.md | North-star vision of the full system: pipeline waves, dossier sections, cross-cutting systems, data flow. Use when designing new features or evaluating scope. |

## Conventions
- Dev Log: append-only, newest first, format ## YYYY-MM-DD
- Decisions: one entry per decision, with date, status, reasoning
- Credentials: status only — never actual keys or secrets
- Infer current work from repo, vault, and conversation context first. Ask only when the goal is still ambiguous or a wrong assumption would be risky.
