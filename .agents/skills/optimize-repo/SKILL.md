---
name: optimize-repo
description: 'Optimize this repo''s instruction, skill, and agent files: cut redundancy, restore source-of-truth ownership, keep Copilot and Claude surfaces aligned. Use when cleaning up customization files in this workspace.'
argument-hint: 'Scope to optimize; report-only or apply fixes'
user-invocable: true
---

# Optimize Repo

Cross-harness source of truth for cleaning up this repo's customization files after agents produce verbose, duplicated,
or drifted instructions. Use this as the audit path in report-only mode and as the cleanup playbook in apply-fixes mode.

## When to Use

- Clean up or audit instruction files, skills, or agents.
- Re-verify any repo `*.md` for verbosity, repetition, padded explanation.
- Targets: redundancy, stale routing, harness drift, source-of-truth violations.
- Restore the current repo structure after cheaper or less careful models copy long rules into the wrong files.

## Current Structure

This project uses `.agents/` as the source of truth for all skills. `.claude/` and `.github/` contain thin wrappers
for each harness.

| Surface | Owner / Shape |
|---------|---------------|
| Repo workflow, source priority, tool preferences, shared rules | `AGENTS.md`; main instruction file — all shared rules live here. |
| Claude entrypoint | `CLAUDE.md`; thin pointer to `AGENTS.md` (`@AGENTS.md`) and skill/agent routing. |
| Copilot entrypoint | `.github/copilot-instructions.md`; thin pointer to `AGENTS.md` and Copilot wrappers. |
| Shared skills | `.agents/skills/<name>/SKILL.md`; owns actual procedure. Both harnesses route through wrappers. |
| Claude skill wrappers | `.claude/skills/<name>/SKILL.md`; frontmatter plus one pointer line to `.agents/`. |
| Copilot skill wrappers | `.github/skills/<name>/SKILL.md`; frontmatter plus one pointer line to `.agents/`. |
| Claude Code agent | `.claude/agents/<name>.md`; role, routing, and repo-specific behavior. |
| Copilot agent | `.github/agents/<name>.agent.md`; harness metadata plus role definition. |
| Agent/skill resource dirs | `.agents/skills/<name>/rules/`; on-demand reference files for oversized instruction files (see 500-line rule). |
| Human onboarding | `README.md`; install/tooling examples, not policy detail. |

## Reference Ownership

Skills and docs must point to these owner files instead of restating their rules.

| Domain | Owner |
|--------|-------|
| Shared repo workflow, source priority, tool preferences, output rules | `AGENTS.md` |
| Article summarization procedure | `.agents/skills/summarize-article/SKILL.md` |
| Book/essay summarization procedure | `.agents/skills/summarize-book/SKILL.md` |
| Video summarization procedure | `.agents/skills/summarize-video/SKILL.md` |
| Repo optimization and audit procedure | `.agents/skills/optimize-repo/SKILL.md` |
| Instruction file compression | `.agents/skills/compress-skill/SKILL.md` |
| Claude Code agent behavior | `.claude/agents/media-analyzer.md` |
| Copilot agent definition | `.github/agents/media-analyzer.agent.md` |
| Context engineering best practices | `.agents/skills/optimize-repo/rules/context-engineering-best-practices.md` |
| Copilot entrypoint routing | `.github/copilot-instructions.md` |
| Claude Code entrypoint routing | `CLAUDE.md` |
| Human onboarding | `README.md` |

## Procedure

1. Mode: review-only (report) or cleanup (smallest edits that restore ownership and cut repetition). If the user asked
   for a plan only, do not edit.
2. Respect repo ignore boundaries before any audit or edit:
   - Treat all files and folders excluded by `.gitignore` as out of scope for this skill.
   - Do not read, audit, edit, move, delete, or regenerate ignored paths.
   - If a requested cleanup would require touching an ignored path, stop and report that it is intentionally excluded.
3. Capture the current state before editing:
   - Check `git status --short`.
   - Count relevant instruction lines with `wc -l AGENTS.md CLAUDE.md README.md .agents/skills/*/SKILL.md
     .claude/skills/*/SKILL.md .github/skills/*/SKILL.md .claude/agents/*.md .github/agents/*`.
   - Flag any instruction file over ~500 lines for splitting (see 500-line rule in audit step 4).
   - Read changed files before patching; assume user/formatter edits are intentional unless they break the task.
4. Audit against the structure above. **Before evaluating any file, read
   `.agents/skills/optimize-repo/rules/context-engineering-best-practices.md`** — it is the authoritative
   standard for all instruction files in this repo. Every audit criterion below derives from it. Violations
   are findings that MUST be fixed or explicitly justified in the affected file (with reason). "The file was
   already long" is not a justification — split it. "It's convenient to keep everything together" is not a
   justification — separate concerns into the correct mechanism.
   - `AGENTS.md` should ideally stay under 80 lines but must never exceed 150 lines and keep source priority as a table.
   - Confirm `AGENTS.md` references the context-engineering-best-practices file — add the pointer if missing.
   - Wrapper files should stay about 10 lines: frontmatter, heading, pointer.
   - Shared skills should contain input parsing, delegated calls, procedure, validation, and output only.
   - Agent files should be one focused role; evidence and safety rules stay in the shared agent file.
   - Reference docs should each own one domain and should not copy each other's lists.
   - **500-line rule:** Any instruction file over ~500 lines must be split into a slim core file (~200–500 lines
     of always-needed content) plus a `rules/` subdirectory holding self-contained reference files. Each
     resource file gets minimal YAML frontmatter (`description`) and is read on-demand via explicit "Read
     `<path>` when `<condition>`" instructions in the core file. Resource files hold: domain-specific
     knowledge, output templates, bootstrap/setup procedures — anything not needed every invocation.
     When compressing prose to fit within the core file limit, never drop: emphasis markers,
     obligation keywords (must/never/CRITICAL/YOU MUST), temporal framing, enumerated item
     counts, identity claims, or consequence statements. Compression must be lossless per
     `compress-skill`. If compression would weaken any of these, keep the original
     text and split to a resource file instead.
   - `README.md` should explain onboarding and use tables for command examples; avoid becoming a second policy surface.
5. Repair messy instructions in this order:
   - Restore source-of-truth ownership first; move or delete restated policy before wordsmithing.
   - Replace copied rules with short pointers such as `Follow .agents/skills/<name>/SKILL.md.` or `Follow AGENTS.md.`
   - Delete padded explanation when a command, table row, or owner-doc pointer carries the meaning.
   - Convert command lists to tables when agents need to scan operation → command quickly.
   - Keep command examples in `AGENTS.md` and README synchronized in spirit, but do not duplicate every policy note.
   - **Split oversized files (>~500 lines):** Identify self-contained sections that aren't needed every invocation
     (domain-specific knowledge, output templates, bootstrap/setup procedures). Extract each to a resource file in a
     `rules/` subdirectory with YAML frontmatter (`description`). Replace with an explicit "Read `<path>` when
     `<condition>`" instruction. Keep core identity, safety rules, writing rules, and always-needed procedures inline.
     - After splitting, optionally run `compress-skill` on the slimmed core file to tighten
       prose. If compressing, verify losslessness per the categories in `compress-skill`
       ("Lossless definition" section) before accepting the result.
     - Never compress resource files extracted to `rules/` — they are already self-contained and
       on-demand; compression there only risks content loss with no line-budget benefit.
6. Keep discovery-critical frontmatter concise:
   - Skill descriptions should identify when to invoke the skill, not explain policy.
   - Argument hints should show input shape only.
   - If a wrapper needs policy text to be correct, the shared skill or reference owner is probably missing a pointer.
7. Re-check after edits:
   - Names, descriptions, and argument hints aligned across `.agents`, `.github`, and `.claude` surfaces.
   - Wrapper bodies still point at the right shared file.
   - Paired agents differ only where the harness requires different metadata/tools.
   - Repo docs advertise only surfaces worth exposing.

## Redundancy Patterns

After cleanup, grep for these patterns in all repo `*.md` files (excluding wrappers and this audit list). Remaining
matches must only appear in the listed owner files.

`yt-dlp`, `--write-auto-subs`, `--skip-download`, `subtitle track`, `--sub-langs`, `--write-subs`
→ `.agents/skills/summarize-video/SKILL.md` only.

`html2text`, `-utf8`, `-width 100`, `-nobs`
→ `AGENTS.md` only (tool preference).

`mlr`, `csvcut`, `csvlook`, `csvstat`, `csvjson`
→ `AGENTS.md` only (tool preference).

`pubmed.ncbi.nlm.nih.gov`, `europepmc.org`, `scholar.google.com`, `doaj.org`, `tripdatabase.com`, `openmd.com`, `freemedicaljournals.com`
→ `AGENTS.md` only (source priority).

`de.wikipedia.org`, `en.wikipedia.org`
→ `AGENTS.md` only (Wikipedia preference).

`www.sci-hub.st`, `Sci-Hub`
→ `AGENTS.md` only (full-text fallback).

`DocCheck`, `Flexicon`, `flexikon.doccheck.com`
→ `AGENTS.md` only (medical wiki).

`## Summary`, `## Most Important Points`
→ `.agents/skills/summarize-article/SKILL.md` and `.agents/skills/summarize-video/SKILL.md` only.

Author biography / other works / historical context prohibitions
→ `AGENTS.md` only.

`tmp/`
→ `AGENTS.md` only (scratch output dir).

No local archive, no local database
→ `AGENTS.md` only.

`.pymarkdown.yaml`
→ Config file. `AGENTS.md` may reference the Markdown standard.

## Preferred Shapes

- Use tables for command matrices, routing maps, source-of-truth maps, source priority, and platform/mirror status.
- Use bullets for short behavior rules and validation checks.
- Do not nest bullets deeper than one level unless the existing file already requires it for readability.
- Avoid long prose in wrappers and entrypoints; `AGENTS.md` is the main instruction file and may be longer.
- Preserve non-ASCII already used for German terms, arrows, and source names; do not add decorative symbols.

## Writing Rules

- **Context engineering best practices are mandatory.** Read and follow
  `.agents/skills/optimize-repo/rules/context-engineering-best-practices.md` when writing or editing any
  instruction file. Deviations require explicit justification in the affected file.
- Match the repo's direct procedural tone.
- Never sacrifice meaning or expressiveness for shorter prose. Meaning includes: emphasis keywords
  and formatting, temporal framing, enumerated element count and order, identity-level claims, and
  consequence statements. If compression would drop or weaken any of these, prefer extraction to a
  resource file over inline shortening.
- Strict source-of-truth ownership.
- Anything excluded by `.gitignore` is out of scope and must remain untouched.
- Skill wrappers and agent wrappers stay short unless a harness difference requires more.
- Preserve keyword-rich frontmatter for discovery.
- Prefer brevity and clarity over grammatical smoothness in every repo `*.md`.
- Drop repetitive phrasing and padding when the meaning carries tighter.
- Don't replace duplication with a new documentation layer.

## Validation

1. **Confirm `.agents/skills/optimize-repo/rules/context-engineering-best-practices.md` was read** before any
   instruction file was evaluated. The audit is incomplete without it.
2. Run frontmatter YAML and Markdown formatting review on every changed file. `.pymarkdown.yaml` defines this
   repo's Markdown standard. If `pymarkdownlnt` is available, run it with `--config .pymarkdown.yaml`; otherwise,
   manually verify YAML frontmatter validity and Markdown link integrity.
3. Run `git diff --check`.
4. Confirm no file or folder excluded by `.gitignore` was touched.
5. Re-run the redundancy-pattern grep and account for every remaining match.
6. Compare paired skill wrappers: `.github/skills/<name>/SKILL.md` and `.claude/skills/<name>/SKILL.md` should match
   except for deliberate harness differences.
7. Re-read changed `*.md` for: padding; repeated phrases; stale owner references; accidental second
   sources of truth; and **lossy compression** — dropped emphasis keywords (CRITICAL, MUST, NEVER,
   ALWAYS, IMPORTANT, ESSENTIAL), stripped bold/italic formatting, lost temporal framing
   (before/after, sequencing), altered enumerated element counts or order, weakened identity-level
   claims, or removed consequence statements. If compression was applied during the cleanup, verify
   it was lossless per the `compress-skill` self-check.
8. Confirm `AGENTS.md` is compact and source priority rules remain clear.
9. **Log every best-practice deviation** with the affected file and the explicit justification provided.
   If no justification was provided, the deviation is an unresolved finding.
10. After completing edits, re-read each changed file and verify no regressions against the audit criteria above.

## Output

- Files optimized.
- Files audited, unchanged.
- Validation performed.
- Remaining inconsistencies left intentionally, with reason.
