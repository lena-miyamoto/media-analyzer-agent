---
name: summarize-book
description: 'Summarize a book, pamphlet, or essay into a markdown brief under tmp/ from a title and optional author.'
argument-hint: 'Provide the title of the work and optionally the author when disambiguation is needed'
user-invocable: true
---

# Summarize Book

Cross-harness source of truth for the `summarize-book` skill.

## When to Use

- Input is one or two parameters: title, and optionally author.
- Summary of a book, pamphlet, essay, article, or speech.
- Output is a scratch markdown summary under `tmp/` unless the user specifies a different path.

## Procedure

1. Classify input:
   - One parameter → title.
   - Two parameters → title, author.
   - More than two, or empty title → stop and ask.
2. Resolve the work identity:
   - Ambiguous title without author → stop and ask.
   - Prefer the full primary text over excerpts, reviews, or secondary commentary.
3. Obtain the entire primary text before analysis.
   - If the user provides a URL or local file, use that directly.
   - If the user provides only a title, search for the full text: prefer publicly available open-access sources, then general web search.
   - If the full text is not available in the language implied by the user's title, check whether a version in another language exists and use that instead. The summary must still be written in the language of the user's title, regardless of the source language.
   - If no reliable full text can be found, report and stop; do not improvise from excerpts, summaries, reviews, metadata, or secondary discussion.
4. Read and analyze the entire primary text before drafting the summary.
   - Do not rely on an existing summary of the same work, whether already in the repo or found elsewhere.
   - Do not base the summary on notes, excerpts, introductions, reviews, or commentary instead of the work itself.
   - Unless the user explicitly authorizes a broader basis, use only the original text; add no author biography, other works, historical context, later interpretations, or common critiques from outside it.
   - If the text is ambiguous, note the ambiguity rather than resolving it using outside knowledge.
5. Read the full text closely enough to identify:
   - intended audience as presented in the text
   - central thesis
   - major arguments and turns
   - conclusions
   - relevant limits, tensions, disputed points
6. Write `tmp/<normalized-title>.summary.md` (or user-specified path):
   - H1: `# <Author>, <Title>` (or `# <Title>` if author unknown).
   - `## Summary` — compact prose synthesis, not chapter-by-chapter notes.
   - `## Most Important Points` — flat bullets.
   - Stay focused on the text, not broad background.

Parameter handling, source order, summary structure, and validation live here — not in higher-level docs or wrappers.

## Writing Rules

- Match the output language to the input language. Determine the language from the title the user supplied: if the title is in German, write the summary in German; if in English, write in English; and so on. Only use a different language when the user explicitly asks for one. This holds regardless of the source language — if the full text was only available in English but the user's title was German, the summary is still written in German.
- Concise but substantive: thesis, line of argument, practical stakes.
- Source-bound: do not add background or interpretation from outside the complete original text unless the user explicitly authorizes it.
- Existing summaries of the same work are not valid source material for the summary.
- Preserve specificity from the text itself; do not project later meanings backward unless the text provides the basis for that distinction.
- Do not overclaim. Flag uncertain attribution, completeness, dating, or ambiguous wording.

## Validation

1. Exactly one title, at most one author.
2. The entire primary text was obtained before analysis; no summary, review, excerpt, or secondary commentary was used as a substitute.
3. The summary is based solely on the primary text, with ambiguity reported instead of resolved from outside knowledge.
4. Output has H1, `## Summary`, `## Most Important Points`.
5. Run markdown diagnostics if available.
6. Report unresolved ambiguities.

## Output

- Name the markdown file created/updated.
- Name the source used.
- Report disambiguation or unresolved ambiguity.
