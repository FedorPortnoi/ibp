You just completed a significant change to Stirlitz. Do the following immediately:

1. Identify what changed:
   - Which files were modified
   - What the change does
   - Whether it fixes a bug, adds a feature, or refactors

2. Update the relevant Obsidian note:
   - Bug fix → update 02 - Stirlitz/Dev Workflow/Debugging Guide.md if it reveals a new pattern
   - New feature → update the relevant Architecture/ note
   - New route → update Architecture/System Overview.md blueprint table
   - New env var → update Architecture/Environment Setup.md
   - TODO completed → remove from Roadmap/Active TODOs.md and add to resolved section
   - Deployment change → update Roadmap/Deployment.md
   - Security change → update Security/Pentest Report.md or Security/Auth & Session.md
   - Source status change → update Roadmap/Source Status.md
   - Test added → update Testing/Test Coverage Map.md

3. Write a dev log entry:
   - Create or append to 02 - Stirlitz/Dev Logs/[TODAY'S DATE].md
   - Format:
     ## [TIME] — [ONE LINE SUMMARY]
     **Changed:** [files modified]
     **What:** [what it does]
     **Why:** [reason/context]
     **Next:** [what comes after this]

4. Update Stirlitz HQ.md:
   - If status changed (blocker resolved, feature shipped, test count changed) update the status snapshot
   - If a new blocker appeared add it to active blockers list

5. Confirm what was updated:
   Output: "📝 Logged: [note names updated] + dev log entry written"

Be specific. Be brief. Update only what actually changed.
