---
name: summarize-video
description: 'Summarize a video into a markdown brief under tmp/ from a video URL and optional subtitle language. Fetch the full subtitle track first with local yt-dlp, abort immediately if yt-dlp is unavailable.'
argument-hint: 'Provide the video URL and optionally a subtitle language code or yt-dlp language selector'
user-invocable: true
---

# Summarize Video

Cross-harness source of truth for the `summarize-video` skill.

## When to Use

- Input is one or two parameters: video URL, and optionally subtitle language.
- Summary of a video when the subtitle track is the primary analyzable source.
- Output is a scratch markdown summary under `tmp/` unless the user specifies a different path.

## Procedure

1. Classify input:
   - One parameter -> video URL.
   - Two parameters -> video URL, subtitle language.
   - More than two, or empty URL -> stop and ask.
2. Before any fetch or analysis, verify `yt-dlp` is installed locally with `command -v yt-dlp`.
   - If `yt-dlp` is unavailable, tell the user to install it first and abort immediately.
3. Resolve the video identity:
   - Prefer a direct URL supplied by the user.
   - If the URL is missing or ambiguous, stop and ask rather than guessing.
4. Obtain the entire subtitle track before analysis.
   - Use `--skip-download` so no video media is downloaded.
   - Use the official subtitle flags documented by `yt-dlp`: `--write-subs`, `--write-auto-subs`, `--sub-format`, `--sub-langs`, `--skip-download`.
   - Default command pattern:

```bash
yt-dlp --write-subs --write-auto-subs --sub-format "srt/vtt/best" --sub-langs "<requested-lang-or-all,-live_chat>" --skip-download "<video-url>"
```

   - Prefer manually provided subtitles when present; fall back to auto-generated subtitles when manual subtitles are absent.
   - If no subtitle track can be obtained, report and stop; do not improvise from the title, description, comments, clips, screenshots, or secondary commentary.
5. Read and analyze the entire subtitle track before drafting the summary.
   - Do not rely on an existing summary of the same video, whether already in the repo or found elsewhere.
   - Do not substitute the video description, chapter list, comments, thumbnails, or outside commentary for the subtitle text.
   - Unless the user explicitly authorizes broader evidence, use only the subtitle text; add no speaker or channel background, other works, historical context, later interpretations, or common critiques from outside it.
   - If the subtitle text is ambiguous, note the ambiguity rather than resolving it using outside knowledge.
   - If the subtitle track is obviously partial, truncated, or machine-generated with major gaps, flag that limitation explicitly.
6. Read the full subtitle text closely enough to identify:
   - intended audience as presented in the subtitle text
   - central thesis or main argument
   - major arguments and turns
   - conclusions
   - relevant limits, tensions, disputed points, or subtitle-only blind spots
7. Write `tmp/<normalized-video-title>.summary.md` (or user-specified path):
   - H1: `# <Channel or Speaker>, <Video Title>` (or `# <Video Title>` if uncertain).
   - `## Summary` - compact prose synthesis, not timestamp notes.
   - `## Most Important Points` - flat bullets.
   - Stay focused on the subtitle text and state when subtitle-only evidence limits confidence about visuals or tone.

Parameter handling, subtitle-fetch requirements, source order, summary structure, and validation live here - not in higher-level docs or wrappers.

## Writing Rules

- Write `## Summary` and `## Most Important Points` in the source language unless the user explicitly asks for another output language. Determine that language from the video title or subtitle language the user supplied: if the title or subtitle track is in German, write those sections in German; if in English, write them in English; and so on.
- Concise but substantive: thesis, line of argument, practical stakes.
- Source-bound: do not add background or interpretation from outside the complete subtitle track unless the user explicitly authorizes it.
- Existing summaries of the same video are not valid source material for the summary.
- Preserve specificity from the subtitle text itself and flag when subtitle-only evidence leaves visual rhetoric, graphics, or cited media unverifiable.
- Do not overclaim. Flag uncertain attribution, completeness, dating, or subtitle quality.

## Validation

1. Exactly one video URL, at most one subtitle-language parameter.
2. `yt-dlp` availability was checked first; if missing, the workflow stopped immediately and told the user to install it.
3. The official subtitle flags were used together with `--skip-download`; no video media download was required for the summary workflow.
4. The entire subtitle track was obtained before analysis; no description, comments, or secondary commentary was used as a substitute.
5. The summary is based solely on the subtitle text, with ambiguity reported instead of resolved from outside knowledge.
6. Output has H1, `## Summary`, `## Most Important Points`.
7. Run markdown diagnostics if available.
8. Report whether the summary used manual subtitles or auto subtitles, plus any completeness limits.

## Output

- Name the markdown file created or updated.
- Name the subtitle file used and whether it was manual or auto-generated.
- Report unresolved ambiguity or transcript limitations.
