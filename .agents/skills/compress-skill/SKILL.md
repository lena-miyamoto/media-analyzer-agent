---
name: compress-skill
description: "Compresses instruction .md files to cut token cost, keeping meaning exact. Accepts a file, directory, glob, or list of these. Rewrites body text in place: short fragments, plain words, technical jargon kept verbatim. No scripts, no external calls. Skips README.md, CONTRIBUTING.md, DEVELOPMENT.md, CHANGELOG.md unless named directly. Invoke after editing any instruction file, or when explicitly asked to compress instruction files."
disable-model-invocation: false
user-invocable: true
---

# compress-skill

Compress instruction `.md` files. Cut token cost, keep meaning exact.

## Input handling

Arg: file path, directory, glob, or space/comma-separated list.

- File → target directly.
- Directory → `find <dir> -name '*.md'` via `Bash`.
- Glob pattern → expand via `Bash` (`shopt -s globstar nullglob; printf '%s\n' <pattern>`).
- List → split on whitespace/comma; resolve each per rules above; dedupe.

No arg → ask for file(s), directory, or glob; stop until given.

## Scope — skip by default

Files named `README.md`, `CONTRIBUTING.md`, `DEVELOPMENT.md`, `CHANGELOG.md`.

Override: file named directly as arg → process anyway. Files pulled in via directory/glob/list stay filtered.

## Process

Per file, section-by-section — no scripts, no external calls:

1. Resolve arg into target list (see Input handling).
2. Scope check per file — skip if matched, unless named directly as a file arg.
3. **Read file** (skip if already in context this turn).
4. **Density check.** Apply criteria below. If file meets all density thresholds, skip it, note which criteria triggered, continue. Never skip on subjective judgement alone.
5. **Save original.** Step 3 content is reference. Hold in context as baseline for all comparisons.
6. **Section-by-section rewrite via `Edit`/`Write`:**
   a. Identify major heading sections (`##` or `###` delimited blocks).
   b. Compress one section at a time, applying rules below.
   c. After each section: self-check against saved original BEFORE next section.
   d. If any check fails for that section, fix in place, then proceed.
7. **Final re-read.** After all sections done, re-read entire edited file via `Read` (mandatory — fresh call). Review as first-time reader — primary verification, not afterthought.
8. **Full self-check** (below), comparing re-read against original (step 5), item by item. Fix in place if needed.
9. Repeat 2–8 per remaining file.

## Density check — concrete thresholds

Skip only when **all four** true (never on subjective judgement):

1. **Fragment ratio:** >80% of non-heading, non-code-block, non-blank lines are fragments (no subject + verb pair).
2. **Word density:** average <10 words per non-blank content line. Body-text lines only — exclude headings, code blocks, single path/command bullets.
3. **Sentence length:** no body-text sentence >12 words. Sentence = prose unit ending in `.`/`!`/`?`, not inside code block or inline span.
4. **Compression-room test:** at least one compression rule (see Word + sentence level) applies to some content line. None applies anywhere → no room to compress, regardless of other thresholds.

When skipping, state: "Skipping `<filename>` — density thresholds met: `<list which ones triggered>`."

If any single threshold fails → file is not dense → compress normally.

## Lossless definition

Lossless: these survive compression exactly as in original, strength and order unchanged:

- Emphasis keywords and formatting — bold, italic, and emphasis words (CRITICAL, MUST, NEVER, ALWAYS,
  IMPORTANT, ESSENTIAL).
- Temporal framing — sequencing and timing words (before, after, at session opening, first, then).
- Enumerated elements — count and order of listed items, especially when items carry distinct meanings
  or the list defines a complete set (e.g., "four non-negotiable elements: ...").
- Identity-level claims — statements about what something *is* or *is not*, category membership,
  foundational definitions ("you are [not] practicing from...", "this is [not]...").
- Consequence statements — cause-effect chains, conditional outcomes ("Without X, Y", "You cannot...
  without...", "Skipping this means...").
- Per-item symmetry — if every item in a list carries a shared emphasis phrase (e.g., "Never skip it"),
  all items must retain it equally.

Any compression that loses one of these categories is over-optimized — restore the lost content.

## Compression rules

### Word + sentence level

- Fragments, not full sentences; drop subject, articles (a/an/the).
- Cut filler (just, really, basically, actually, simply, essentially, generally), pleasantries (sure, certainly, happy to), hedging (might be worth, could consider, it would be good to), connective fluff (however, furthermore, additionally, in addition).
- Shorten redundant phrasing: "in order to" → "to", "make sure to" → "ensure", "the reason is because" → "because", "utilize" → "use".
- Plain, everyday words. Exception: technical jargon (library/API names, protocols, CLI flags, error strings) — keep exact, never paraphrase or simplify.
- Sentences that must stay full: ≤20 words.
- Merge or cut bullets/examples making the same point twice.
- Comparatives (more than N, at least N, no more than N, up to N) → keep direction exact. Don't collapse to shorthand like "N+" — that can silently shift the threshold.

### Tiebreaker: when in doubt, preserve

Compression biases toward cutting. Counter:

- **Doubt → preserve.** Uncertain about any Lossless category → keep. Cut only when certain removal loses nothing from all six.
- **Borderline load-bearing → load-bearing.** Might be emphasis, temporal, identity, or consequential → IS load-bearing until proven otherwise.
- **Burden of proof is on removal.** Don't argue "probably safe." Argue "definitely safe — here's why it touches none of the six Lossless categories."

Not an excuse to skip — a rule against over-compression. Compress aggressively where clearly safe; freeze where uncertain.

### Never touch — preserve byte-exact

- Code blocks (fenced + indented), inline code, inline formatting (`**bold**`, `*italic*`)
- URLs, markdown links, file paths, commands, env vars
- Technical terms, proper nouns, numbers, dates, version strings
- Emphasis keywords beyond must/should/never/always: `CRITICAL`, `IMPORTANT:`, `YOU MUST`, `NEVER`,
  `ALWAYS`, `ESSENTIAL`, `MANDATORY`, `NOT OPTIONAL` — treat as obligation words, never weaken or drop.
- Headings (exact text + order), list nesting, table structure (compress cell text only), frontmatter/YAML

### Self-check before done

Self-check runs twice: per-section during editing (step 6c), full-file review after mandatory re-read (step 8). Full-file review authoritative.

**Full-file review procedure:**

1. Re-read the edited file (already done in step 7 — fresh in context).
2. Audit as if someone else wrote it. Read each line against original (step 5).
3. Mentally diff each changed section against original. Focus on *removals* — meaning lost in deletions, rarely in additions.
4. Run each checklist item against compressed file, cross-referencing saved original. Uncertain check → fail — tiebreaker applies here too.

**Checklist:**

- Byte-exact spans above unchanged?
- Heading count + order unchanged?
- No leaked meta-commentary, stray `---`, or fence artifacts?
- Emphasis markers (bold `**`/`__`, italic `*`/`_`) and all emphasis keywords (CRITICAL, IMPORTANT, YOU MUST, NEVER, ALWAYS, ESSENTIAL, MANDATORY, NOT OPTIONAL, must, should, always, never) unchanged in presence, strength, and direction?
- Temporal framing words (before/after, first/then, at session opening, sequencing) preserved?
- Enumerated element count and order preserved when the enumeration defines a complete set or carries distinct meanings per item?
- Identity-level claims ("you are [not]...", "this is [not]...", category membership) unchanged?
- Consequence statements ("Without X, Y", "You cannot... without...", "Skipping this means...", cause-effect chains) preserved in full?
- Per-item symmetric emphasis (e.g., "Never skip it" on every item) preserved equally?
- Trailing newline still there?
- **Diff scan:** review every removal. For each, confirm outside all six Lossless categories. Flag ambiguous removals — restore if not confidently safe.

Any check fails → fix directly. Don't restart from scratch. If 3+ checks fail, re-edit offending sections against original, re-run full-file review.

## Pattern

Example: "You should always make sure to run the test suite before pushing any changes to the main branch. This is important because it helps catch bugs early and prevents broken builds from being deployed to production." → "Run tests before push to main. Catches bugs early, prevents broken prod deploys."
