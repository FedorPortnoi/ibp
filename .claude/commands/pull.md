Load a specific section of the Obsidian brain on demand.
Usage: /pull [topic]

Based on the topic requested, read and summarize the relevant note:
- "architecture" or "system" → read Architecture/System Overview.md
- "database" or "db" or "models" → read Architecture/Database Schema.md
- "claude" or "ai" → read Architecture/Claude AI Integration.md
- "deploy" or "deployment" or "server" → read Roadmap/Deployment.md
- "todos" or "roadmap" → read Roadmap/Active TODOs.md
- "sources" or "status" → read Roadmap/Source Status.md
- "vk" or "tokens" → read Architecture/VK Token System.md
- "telegram" or "telethon" → read Architecture/Telethon Setup.md
- "security" or "auth" → read Security/Auth & Session.md
- "pentest" → read Security/Pentest Report.md
- "testing" or "tests" → read Testing/Test Coverage Map.md
- "debug" or "debugging" → read Dev Workflow/Debugging Guide.md
- "env" or "environment" → read Architecture/Environment Setup.md
- "pipeline" → read Architecture/System Overview.md focusing on pipeline stages
- "business" or "billing" → read Business Logic/Free Tier & Subscriptions.md
- "glossary" → read Architecture/Glossary.md
- "changelog" or "history" → read History/Changelog.md
- "portfolio" → read Portfolio/Stirlitz as Portfolio Piece.md

After reading, output:
"📖 [note name] loaded" followed by a concise summary of the most relevant parts.

If topic is not recognized, list all available topics.
