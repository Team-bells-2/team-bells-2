Core Rules for AI CODING AGENTS:

- Always state assumptions and list what was changed in a short summary.
- Ask feedback questions always when a concept/implementation in the code seems vague, never invent new concepts in the code-base on your won.
- Commit small and often always max files in a commit is 10.
- Never commit .env or print secrets.
- Work only on the assigned task, on its own branch, never on main branch.
- Touch only the listed files and folders. Ask first if you need more.
- No new dependencies without asking, and no mass refactors or renames.
- Never edit tests, CI config, AGENTS.md or merged migrations.
- Never “fix” a failing test by changing the assertion. Report the failure instead.
- No destructive commands (rm -rf, git reset --hard, git push --force, DROP TABLE) and no --no-verify. Enforce this with your agent tool’s command allow-list where it has one.
