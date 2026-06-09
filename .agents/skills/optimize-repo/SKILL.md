---
name: optimize-repo
description: 'Optimize this repo''s instruction, skill, and agent files: cut redundancy, restore source-of-truth ownership, keep Copilot and Claude surfaces aligned. Use when cleaning up customization files in this workspace.'
argument-hint: 'Scope to optimize; report-only or apply fixes'
user-invocable: true
---

# Optimize Repo

Cross-harness source of truth for optimizing this repo's customization and instruction files. Also the audit path: run report-only when the user wants findings without edits.

## When to Use

- Clean up or audit instruction files, skills, or agents.
- Re-verify any repo `*.md` for verbosity, repetition, padded explanation.
- Targets: redundancy, stale routing, harness drift, source-of-truth violations.

## Procedure

1. Mode: review-only (report) or cleanup (smallest edits that restore ownership and cut repetition).
2. Respect repo ignore boundaries before any audit or edit:
   - Treat all files and folders excluded by `.gitignore` as out of scope for this skill.
   - Do not read, audit, edit, move, delete, or regenerate ignored paths.
   - If a requested cleanup would require touching an ignored path, stop and report that it is intentionally excluded.
3. Re-verify every in-scope `*.md` for writing quality:
   - Cut verbosity and repetition.
   - Compress explanation when meaning survives.
   - Tighten wording even when structure is fine.
4. Anchor on boundaries from `AGENTS.md` and `.github/copilot-instructions.md`:
   - Shared procedure: `.agents/skills/<name>/SKILL.md`.
   - `.github/skills`, `.claude/skills`: thin wrappers.
   - Repo-wide workflow: `AGENTS.md`.
   - Harness routing: `CLAUDE.md`, `.github/copilot-instructions.md`.
   - Agents: short, role-focused.
5. Audit before editing:
   - Duplicated procedure across shared skills and wrappers.
   - Stale paths or source-of-truth references.
   - Paired agents drifted beyond needed harness differences.
   - Repo docs restating routing owned elsewhere.
6. Narrowest useful fix:
   - Delete over rewrite.
   - Update references over adding explanation.
   - One owner per stable rule.
   - Keep discovery-critical frontmatter; shrink only duplicated body.
7. Re-check after edits:
   - Names, descriptions, argument hints aligned.
   - Wrapper bodies still point at the right shared file.
   - Repo docs advertise only surfaces worth exposing.

## Writing Rules

- Strict source-of-truth ownership.
- Anything excluded by `.gitignore` is out of scope and must remain untouched.
- Wrappers and paired agents stay short unless a harness difference forces more.
- Preserve keyword-rich frontmatter for discovery.
- Match the repo's direct procedural tone.
- Prefer brevity and clarity over grammatical smoothness in every repo `*.md`.
- Drop repetitive phrasing and padding when the meaning carries tighter.
- Never sacrifice meaning or expressiveness for shorter prose.
- Don't replace duplication with a new documentation layer.

## Validation

1. Markdown/frontmatter diagnostics on every changed file.
2. Confirm no file or folder excluded by `.gitignore` was touched.
3. Grep for stale paths, outdated source-of-truth references, old duplicated phrases.
4. Re-read each changed `*.md` for verbosity and repetition; tighten until no obvious padding remains.
5. Shared skill files hold the procedure; wrappers stay minimal.
6. Paired agents aligned except for needed harness differences.
7. Routing/README changes match actual file layout.

## Output

- Files optimized.
- Files audited, unchanged.
- Remaining inconsistencies left intentionally.
