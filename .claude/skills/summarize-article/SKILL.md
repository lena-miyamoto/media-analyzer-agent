---
name: summarize-article
description: 'Summarize an article into a markdown brief under tmp/ from a URL or a local document path such as PDF, Markdown, HTML, or plain text.'
argument-hint: 'Provide exactly one article source: either a URL or a local file path containing the full article text'
user-invocable: true
---

# Summarize Article

Cross-harness source of truth for the `summarize-article` skill.

## When to Use

- Input is exactly one parameter: either a URL or a local file path.
- Summary of an article, essay, speech transcript, pamphlet, or similar text when the source is already identified.
- Output is a scratch markdown summary under `tmp/` unless the user specifies a different path.

## Procedure

1. Classify input:
   - One parameter that is an `http` or `https` URL -> external article source.
   - One parameter that resolves to a readable local file path -> local document source.
   - Anything else, multiple parameters, or an unreadable path -> stop and ask.
2. Resolve the source identity:
   - For a URL, fetch the article from the supplied URL.
   - For a local file path, use that file directly if it is the primary text.
   - If the supplied source is obviously commentary, an excerpt, notes, metadata, or a review rather than the article itself, report and stop.
3. Obtain the entire primary text before analysis.
   - If the input is a URL, fetch the complete article from the supplied URL.
   - If the input is a local document such as PDF, Markdown, HTML, or plain text, extract or read the full text locally before analysis.
   - If the source only exposes a preview, excerpt, paywalled fragment, or partial capture, report and stop; do not improvise from snippets, summaries, metadata, or secondary discussion.
4. Read and analyze the entire primary text before drafting the summary.
   - Do not rely on an existing summary of the same article, whether already in the repo or found elsewhere.
   - Do not base the summary on notes, excerpts, introductions, reviews, metadata, or commentary instead of the article itself.
   - Unless the user explicitly authorizes a broader basis, use only the original article text; add no author biography, other works, historical context, later interpretations, or common critiques from outside it.
   - If the text is ambiguous, note the ambiguity rather than resolving it using outside knowledge.
5. Read the full text closely enough to identify:
   - intended audience as presented in the text
   - central thesis
   - major arguments and turns
   - conclusions
   - relevant limits, tensions, disputed points, or source-quality constraints
6. Write `tmp/<normalized-title>.summary.md` (or user-specified path):
   - H1: `# <Author>, <Title>` (or `# <Title>` if author unknown).
   - `## Summary` - compact prose synthesis, not section-by-section notes.
   - `## Most Important Points` - flat bullets.
   - Stay focused on the text, not broad background.

Parameter handling, source requirements, summary structure, and validation live here - not in higher-level docs or wrappers.

## Writing Rules

- Write `## Summary` and `## Most Important Points` in the source language unless the user explicitly asks for another output language. Determine that language from the title or article source the user supplied: if the title or article text is in German, write those sections in German; if in English, write them in English; and so on.
- Concise but substantive: thesis, line of argument, practical stakes.
- Source-bound: do not add background or interpretation from outside the complete article text unless the user explicitly authorizes it.
- Existing summaries of the same article are not valid source material for the summary.
- Preserve specificity from the text itself and flag when source format or extraction quality leaves attribution, completeness, or wording uncertain.
- Do not overclaim. Flag uncertain authorship, dating, completeness, OCR quality, or transcription quality.

## Validation

1. Exactly one source parameter was provided, and it was resolved as either a URL or a readable local file path.
2. The entire primary text was obtained before analysis; no summary, review, excerpt, metadata, or secondary commentary was used as a substitute.
3. The summary is based solely on the primary text, with ambiguity reported instead of resolved from outside knowledge.
4. Output has H1, `## Summary`, `## Most Important Points`.
5. Run markdown diagnostics if available.
6. Report unresolved ambiguity, source limitations, or extraction limits.

## Output

- Name the markdown file created or updated.
- Name the source used.
- Report unresolved ambiguity or source-quality limits.
