# meiseki

**An Agent Skill that strips high-reading-load syntax out of AI-written Japanese documents and rewrites them into prose you can understand in a single pass.**

`meiseki`（明晰）= "lucid; clear and understandable." The one and only goal is **clarity — a reader with no prior context can read the text once and understand it correctly.**
It never adds voice, stance, or personality to the text. It runs in the **opposite direction** from `stop-ai-slop-jp`-style tools, which inject subjectivity by rewriting generic statements into first-person opinions — meiseki adds no voice and aims for neutral clarity.

> For the background and motivation, see the author's article (Japanese):
> [AIの日本語を「自然」ではなく「明晰」にする ― meiseki という明晰化プラグインを作った話](https://zenn.dev/bamboo_nova/articles/c782c9de31e24b) (Zenn).

日本語版 README は [README.md](./README.md) を参照してください。

## What it fixes

It targets **syntax** that is hard to parse even for native Japanese readers (the cause of hard-to-read text is syntax, not difficult vocabulary).

- Double negatives (litotes) / nested negation and conditionals
- Long pre-nominal modifiers / long subject–predicate distance / overloaded single sentences
- Chains of the particle「の」/ excessive nominalization and Sino-Japanese compounds
- Redundant or empty expressions (e.g.「することができます」)
- Excessive formatting such as overused bold-plus-colon bullet lists
- Three or more coordinate items buried in one sentence (unfolded into a bullet list)
- LLM boilerplate phrases (「重要なのは〜」,「掘り下げる」,「多角的」,「〜に他ならない」, etc. — machine-detected with the bundled prh dictionary)
- AI-flavored formatting and hype words (emoji bullet lists, bold-plus-colon list boilerplate,「革命的」("revolutionary"),「ゲームチェンジャー」("game changer"), etc. — machine-detected with `textlint-rule-preset-ai-writing`)
- Paragraph-level redundancy (repeated restatements of the same claim, re-summarizing right after a description, parallel facts scattered across paragraphs)

**In scope**: technical articles, READMEs, design documents, internal documentation, explanatory blog prose.
**Out of scope**: code itself, short social-media posts, creative writing such as fiction and poetry, and precision-critical legal / medical / academic texts.

## Architecture (two layers)

```
Input: Japanese document (manuscript)
        │
        ▼
[meiseki skill / LLM orchestrator]
        │
        ├──▶ textlint (run via npx — deterministic layer)
        │       Detects double negatives, sentence length, excessive commas,
        │       long kanji runs, redundancy, LLM boilerplate (bundled prh
        │       dictionary), AI-flavored formatting and hype words
        │       (preset-ai-writing), etc., as machine-readable JSON with
        │       line/column info → reading-load score (before)
        │
        └──▶ Pattern catalog A–H (LLM judgment layer)
                Handles syntax textlint cannot catch:
                long pre-nominal modifiers,「の」chains, nominalization,
                unfolding enumerations into lists (F), context-dependent
                judgment of boilerplate (G), removing paragraph-level
                repetition (H)
        │
        ▼
   Rewrite → re-run textlint to verify before→after
        │
        ▼
Output: clarified body text only (+ optionally the reading-load score)
```

- **Detection and scoring belong to textlint (deterministic layer)**; **rewriting belongs to the skill (LLM layer)**.
- The LLM covers syntax textlint cannot catch (pre-nominal modifiers,「の」chains, general nominalization, enumerations).
  **This "part textlint cannot catch" is exactly what separates meiseki from a plain textlint config.**
- No MCP server. textlint is invoked via `npx`, which ships with Node.js.

## Directory layout

```
meiseki/
├── .claude-plugin/          # Claude Code plugin manifest
├── .codex-plugin/           # Codex CLI plugin manifest
├── hooks/
│   ├── hooks.json           # PostToolUse hook definition for Claude Code
│   └── codex-hooks.json     # PostToolUse hook definition for Codex CLI
├── scripts/
│   ├── meiseki-lint-core.sh     # Deterministic-layer core: masking + textlint + threshold check (rule set swappable via env vars)
│   ├── meiseki-check.sh         # Claude Code adapter: JSON I/O and re-run guard
│   ├── codex-hook.sh            # Codex adapter: extracts paths from the apply_patch envelope and bridges
│   ├── yorisoi-vocab-check.js  # Wrapper for the vocabulary-level checker (core ships inside the skill)
│   ├── test-meiseki-check.sh    # Automated tests for the hook and the prh supplement dictionary (npm run test:hook)
│   └── test-yorisoi.sh         # Automated tests for yorisoi detection and vocabulary checks (npm run test:yorisoi)
├── .agents/skills/          # Standard Agent Skills location (shared by Claude Code and Codex)
│   ├── meiseki/
│   │   ├── SKILL.md         # LLM orchestrator for the clarity skill
│   │   └── references/
│   │       ├── patterns.md             # High-load syntax catalog A–H
│   │       ├── prh-llm-phrases.yml     # Detection dictionary for LLM boilerplate (category G, detection only)
│   │       └── textlint.config.json    # textlint config narrowed to rules that affect reading load
│   └── yorisoi/
│       ├── SKILL.md         # LLM orchestrator for the plain-Japanese skill
│       ├── scripts/vocab-check.js      # Vocabulary-level checker (morphological analysis + bundled lists)
│       └── references/
│           ├── patterns-yorisoi.md    # Guideline-derived rewrite catalog YA–YH
│           ├── prh-yorisoi.yml        # Detection dictionary: passive, speculation, honorifics, notation
│           ├── textlint-yorisoi.config.json
│           └── vocab/                  # Vocabulary lists (sources and licenses in its README)
├── examples/
│   ├── meiseki/             # Clarity examples (9 before/after pairs + measured RLS)
│   └── yorisoi/            # Plain-Japanese examples (3 before/after pairs + measured YLS)
├── package.json             # Provides npm run lint / lint:yorisoi / vocab:yorisoi / test:* for development
└── README.md
```

## Requirements

* Node.js installed

## Installation

### As an Agent Skill

Run the following in an environment with Node.js installed.

```
npx skills add https://github.com/bamboo-nova/meiseki --skill meiseki
```

### As a Claude Code plugin (optional)

`claude plugin install` takes **a plugin name registered in a marketplace** (not a path).
So `claude plugin install ./meiseki` and `claude plugin install .` fail. The correct way is to
first register the bundled `.claude-plugin/marketplace.json` as a marketplace, then install by name.

```bash
# 1. Register this plugin's marketplace (.claude-plugin/marketplace.json)
claude plugin marketplace add ./meiseki

# 2. Install as "plugin-name@marketplace-name"
claude plugin install meiseki@bamboo-nova-ja-tools
```

If you just want to load it temporarily during development without installing:

```bash
claude --plugin-dir ./meiseki
```

> You can validate the manifest with `claude plugin validate ./meiseki`.

### As a Codex CLI plugin (since v0.5.0)

Codex CLI (verified on the 0.149 series) supports the Agent Skills standard and a plugin mechanism, and can load meiseki as is.

```bash
# 1. Register this repository as a marketplace (Codex can read the Claude marketplace.json too)
codex plugin marketplace add ./meiseki

# 2. Install (the version is resolved from .codex-plugin/plugin.json)
codex plugin add meiseki@bamboo-nova-ja-tools
```

The meiseki skill (`meiseki:meiseki`) is now available from Codex.
The auto-apply hook (`hooks/codex-hooks.json`) is bundled as well, but Codex hooks
**require an explicit one-time trust grant for security reasons**. Run `/hooks` in an
interactive Codex session and trust the meiseki hook to enable it.

- Alternative without the plugin: copy `.agents/skills/meiseki/` into
  `~/.agents/skills/` to use the skill in every project. For the hook, write the
  absolute path to `scripts/codex-hook.sh` into the project's `.codex/hooks.json`
  and the same check will run.
- If the Codex sandbox blocks network access, `npx` inside the hook cannot fetch
  packages and the check passes through silently (fail-open). Running
  `npm run lint -- <any md>` once beforehand warms the cache and makes it reliable.

### Updating an existing installation (replacing an older version)

When updating to v0.3.0 or later (which ships the hook), uninstall once and reinstall.

```bash
claude plugin uninstall meiseki
claude plugin marketplace update bamboo-nova-ja-tools
claude plugin install meiseki@bamboo-nova-ja-tools
```

Restart the session after updating to activate the new hook.

## Usage

Just hand the target Japanese text to the skill. Example triggers (in Japanese):

- 「この README を読みやすく直して」("Make this README easier to read")
- 「この説明文、AIっぽいので明晰化して」("This description sounds AI-written — clarify it")
- 「冗長な日本語を削って一読で分かるようにして」("Trim the redundant Japanese so it's clear in one pass")

By default only the **rewritten body text** is returned. Say「どこを直したか教えて」("tell me what you changed") to get the list of changes as well.
Say「スコアも出して」("show the score too") to include the reading-load score (before→after).

## Plain Japanese skill `meiseki:yorisoi` (since v0.6.0)

A second skill that rewrites documents into "yorisoi nihongo" (plain Japanese) for foreign
residents and Japanese learners. It differs from meiseki in **target reader**: use meiseki to
polish prose for native readers, and yorisoi for readers still learning Japanese. Example triggers:

- 「このお知らせをやさしい日本語にして」("Rewrite this notice in plain Japanese")
- 「外国人にもわかるように書き直して」("Rewrite it so non-native readers understand")
- 「やさしい日本語かチェックして」("Just check it" — report-only mode, no rewriting)

It keeps the same two-layer architecture and adds an **official external norm** as its basis.

- Normative basis: the [Guidelines for Plain Japanese for Residency Support](https://www.moj.go.jp/isa/support/portal/plainjapanese_guideline.html)
  (Immigration Services Agency & Agency for Cultural Affairs, August 2020). Bans on double
  negatives, avoidance of passive and speculative phrasing, simplified honorifics, and notation
  rules (Western calendar years, AM/PM times, no "〜" ranges) are machine-detected by textlint
  plus a bundled prh dictionary (`prh-yorisoi.yml`)
- Vocabulary-level checking: a bundled script (`scripts/yorisoi-vocab-check.js`) tokenizes the
  text with kuromoji.js (auto-fetched on first run) and reports words above the target level with
  line positions. The default target is **roughly N4** (changeable, e.g. 「N3 で」)
- **Every "N-level" label is an estimate.** The official JLPT vocabulary lists have been
  unpublished since 2010, so the bundled lists (tanos.co.uk-derived, CC BY) and NINJAL's basic
  vocabulary survey data (CC BY 4.0) approximate them. If you obtain the JEV vocabulary list
  yourself and drop it in, it takes precedence (see `references/vocab/README.md`)
- Scoring: a "yasashisa load score" (YLS, same form as RLS) verifies before→after
- Important words that cannot be simplified are kept with an inline gloss in the guideline's
  format:「余震＜＝後から来る地震＞」("aftershock <= an earthquake that comes later>")
- **Not** wired into the auto-apply hook (on-demand only). Furigana and word spacing are out of
  scope as of v0.6.0

Development commands: `npm run lint:yorisoi -- <md>` (syntax detection) and
`npm run vocab:yorisoi -- <md>` (vocabulary check). Worked examples with measured scores live in
`examples/yorisoi/`.

## Auto-apply hook (when used as a plugin)

When enabled as a plugin, **a check runs automatically every time Claude Writes / Edits a Japanese Markdown file**.
The hook itself never calls an LLM. It runs only textlint (the deterministic layer), and when
the reading load is high it feeds back to Claude: "apply the meiseki skill and rewrite."
Claude then applies meiseki within the same session and rewrites the file.

```
Claude Writes / Edits report.md
        │
        ▼
[PostToolUse hook] scripts/meiseki-check.sh (the check core is scripts/meiseki-lint-core.sh)
  ├─ Out of scope (non-.md / excluded path / no Japanese / opt-out) → do nothing
  ├─ Re-run guard (content hash) → already judged / limit reached → exit without linting
  ├─ Mask out-of-scope regions (code, math, quotes, references, figure/table captions)
  ├─ Run textlint → no findings / minor → do nothing
  └─ Double negative present or 3+ findings
       → decision:"block" + finding summary fed back to Claude
       → Claude applies meiseki and re-Writes (until textlint passes)
```

- **Trigger condition**: at least one `no-double-negative-ja` finding (category A), or 3+ textlint findings in total.
  Separated / polite-form double negatives (caught by the prh supplement dictionary) count toward the total as ordinary prh findings.
  Note that the acceptance criterion in SKILL.md §7 is the **relative comparison** "after < before" with no absolute threshold;
  this trigger condition is therefore a simplified hook-side criterion (see the top of `scripts/meiseki-check.sh`).
- **Masking of out-of-scope regions**: the out-of-scope declaration in SKILL.md §3 is also implemented on the hook side.
  Code fences (including mermaid), math (`$...$` / `$$...$$` / `\begin{...}`), quote blocks,
  figure/table caption lines (`図1:` / `Table 1.` etc.), reference sections (from a heading like
  `## 参考文献` / `## References` to the next heading — **the whole section is masked, so it does not
  depend on the entry format: Nature / ASA / APA / IEEE / Japanese styles all work**), inline IEEE-style
  `[1] ...` lines, and footnote definitions `[^1]:` are replaced with blank lines before linting and do
  not affect the judgment. This addresses false positives on references, math, and captions in academic documents.
- **Tests**: `npm run test:hook` (= `scripts/test-meiseki-check.sh`) is provided.
  It automatically tests the supplement dictionary's detection coverage and the hook's judgment, exclusions, masking, opt-out, and loop prevention.
- **Exclusions**: `CLAUDE.md` / `AGENTS.md` / `MEMORY.md` / `SKILL.md`; anything under `.claude/`, `plans/`, `memory/`,
  `node_modules/`, `.git/`, `scratchpad/`, `/tmp`; anything under `examples/` or `references/`;
  files containing no Japanese.
- **Loop prevention**: at most 2 blocks per file per session; after that, warnings only
  (to stay consistent with the guardrail that prh findings are "not confirmed deletions").
  Judgments are recorded in a state file keyed by content hash (`$TMPDIR/meiseki-hook-state.tsv`);
  re-writing identical content replays the previous judgment without running textlint.
  Even in a different session (e.g. after a restart), content already blocked gets a warning only and is not re-blocked.
- **Fail-open**: in environments where textlint cannot run (offline, etc.), writes are never blocked.
- **Disabling**: set the environment variable `MEISEKI_HOOK_DISABLE=1`, or disable the plugin itself.
  Per file, add `meiseki: skip` to the frontmatter or write `<!-- meiseki-disable -->` anywhere in
  the body to exclude just that file.
- **About PDFs**: a PDF cannot be fixed after generation, so this hook guarantees clarity at the
  source-Markdown stage (PDF generation via pandoc etc. starts from already-clarified md).

> Hook additions and changes take effect after a session restart (or plugin reload).
> The first `npx` run may take tens of seconds to fetch packages (cached afterwards).
> If installed only as an Agent Skill (`npx skills add`), no hook is attached; the skill
> fires only when you ask, as before.

## Rule rationale for `references/textlint.config.json` (the key differentiator)

The full presets also enforce rules **unrelated to reading load** — orthographic variants, exclamation marks, katakana long vowels — and "over-polish" the text.
meiseki keeps **only the rules that affect reading load** and turns everything else off with `false`.

| Enabled (true) | Role |
|---|---|
| `no-double-negative-ja` | Double negatives (top-priority category A) |
| `sentence-length` (max 90) | Sentence length (B) |
| `max-ten` (max 3) | Excessive commas (B) |
| `max-kanji-continuous-len` (max 6) | Long kanji runs = heavy Sino-Japanese compounds (C) |
| `ja-no-redundant-expression` | Redundant expressions such as「することができる」(C/D) |
| `no-doubled-joshi` (min_interval 1) | Repeated particles (B) |
| `no-doubled-conjunction` | Repeated conjunctions (D) |
| `no-doubled-conjunctive-particle-ga` | Consecutive adversative「が」= a sign of overloading (B) |
| `ja-no-weak-phrase` | Weak phrases (D — never used to strengthen a stance) |
| `prh` (bundled dictionary `prh-llm-phrases.yml`) | LLM boilerplate (G). **Detection only** — the LLM decides in context whether to cut or keep. Also detects, via the A1 supplement section, separated / polite-form double negatives that `no-double-negative-ja` misses (e.g.「〜ないとは言えません」) |
| `preset-ai-writing/no-ai-list-formatting` | Emoji bullets, bold-plus-colon list boilerplate (E) |
| `preset-ai-writing/no-ai-emphasis-patterns` | Excessive bold inside lists (E) |
| `preset-ai-writing/no-ai-hype-expressions` | Hype words such as「革命的」(G). Detection only, like prh; the LLM judges context |
| `preset-ai-writing/ai-tech-writing-guideline` | Conciseness findings such as redundant auxiliaries and vague phrasing (D). Enabled explicitly because its default severity is info |

Rules disabled (false):

- `arabic-kanji-numbers`, `no-mix-dearu-desumasu`, `ja-no-mixed-period`
- `no-dropping-the-ra`, `no-exclamation-question-mark`, `no-nfd`

> **Note on preset tracking**: changing the pinned versions of the `textlint` package or
> `textlint-rule-preset-ja-technical-writing` may change that preset's rule keys and defaults.
> When updating, check the preset's README for the rule list and verify the keys above still exist
> and match. If new bundled rules unrelated to reading load appear, turn them off with `false` likewise.

## Reading Load Score (RLS)

```
RLS = Σ(findings per category × weight) ÷ number of sentences in the body × 100   (lower is easier to read)
```

| Category | textlint rules | Weight |
|---|---|---|
| A Nested negation (top priority) | `no-double-negative-ja` | 3 |
| B Distance / length | `sentence-length`, `max-ten`, `no-doubled-conjunctive-particle-ga` | 2 |
| C Sino-Japanese compounds / nominalization | `max-kanji-continuous-len`, `ja-no-redundant-expression` | 2 |
| D Redundant / empty | `ja-no-redundant-expression`, `no-doubled-conjunction`, `ja-no-weak-phrase`, `ai-tech-writing-guideline` | 1 |
| E Formatting | `no-ai-list-formatting`, `no-ai-emphasis-patterns` (+ LLM judgment) | 1 |
| F Structuring (enumeration) | (LLM judgment) | 1 |
| G Boilerplate | `prh` (bundled dictionary), `no-ai-hype-expressions` | 1 |
| H Paragraph redundancy | (LLM judgment) | 1 |

**Acceptance criteria: after < before is mandatory; category A (double negatives) must in principle be 0.** Intentional litotes is the only exception.

## Acceptance checklist

- [ ] Output is body text only (no analysis, headings, or commentary attached)
- [ ] Opening generalities (「近年〜」"In recent years...") are removed
- [ ] 「することができます」has become「できます」
- [ ] 「〜の〜の〜」chains are untangled
- [ ] Long pre-nominal modifiers are split; subject and predicate are close together
- [ ] **Double negatives are folded without flipping the logic** (e.g.「招かないとは言えません」→「負荷が増えることがある」"the load can increase";「増えない」"does not increase" is a mistranslation = fail)
- [ ] The polite/plain style (敬体／常体) is preserved
- [ ] API names, proper nouns, and numbers are unchanged
- [ ] Sentences that were already plain are not rewritten needlessly
- [ ] **No voice or stance has been injected** (no added first-person opinions like「自分は」, no added assertive emphasis)
- [ ] LLM boilerplate (「重要なのは〜」,「掘り下げる」, etc.) is removed (usages with real substance in context are kept)
- [ ] Paragraph-level restatements and re-summaries are removed (claims, examples, evidence, and exceptions are not lost)
- [ ] Re-running textlint shows the reading-load score is lower than before (category A is 0)

## References

The design of G (LLM boilerplate) and H (paragraph redundancy) draws on
k16shikano's [日本語技術文書の文章規範](https://gist.github.com/k16shikano/fd287c3133457c4fd8f5601d34aa817d)
(the japanese-tech-writing skill), in particular its sections on banning LLM-ish empty phrases,
eliminating redundancy, and structuring paragraphs and argumentation.

The yorisoi skill draws on the following resources:

- [Guidelines for Plain Japanese for Residency Support](https://www.moj.go.jp/isa/support/portal/plainjapanese_guideline.html) (August 2020) — the basis for the rewrite rules
- [tanos.co.uk JLPT vocabulary lists](http://www.tanos.co.uk/jlpt/) (CC BY, unofficial estimates)
- [NINJAL basic vocabulary survey data](https://mmsrv.ninjal.ac.jp/bvjsl84/) (CC BY 4.0)
- [JEV vocabulary list](https://jhlee.sakura.ne.jp/JEV/) (redistribution prohibited; optional, user-supplied)
- [jReadability](https://jreadability.net/) — the published formula behind the supplementary readability estimate

## Disclaimer

- This Agent Skill and plugin are provided "AS IS", **without any warranty** as to the accuracy, completeness, or fitness for a particular purpose of their output.
- Because meiseki **rewrites** text, the clarification process may alter the original meaning, nuance, or factual content. **Always review and verify the output yourself before using it.** Final responsibility for the content rests with the user.
- Documents requiring strict precision — legal, medical, contractual, academic — are **out of scope** (see "What it fixes"). The author accepts no responsibility for outcomes arising from such uses.
- The yorisoi skill's vocabulary-level labels ("roughly N4" etc.) are **estimates based on unofficial lists** and do not match any official JLPT standard.
- The yorisoi skill follows the official guidelines but is **not an approved or certified tool**. Simplification can alter meaning. Before publishing rewritten output as official information (administrative procedures, disaster notices, etc.), **have it reviewed by qualified staff** (Japanese-language education or multicultural affairs officers).
- The author and rights holders accept no liability for any direct or indirect damages arising from the use of, or inability to use, this Agent Skill and plugin (see `LICENSE` for details).
- This Agent Skill and plugin depend on third-party OSS such as textlint. The behavior and security of those dependencies are governed by their respective providers' terms and licenses.

## Acknowledgments

- Machine detection for E (formatting), G (hype words), and D (conciseness) uses [textlint-rule-preset-ai-writing](https://github.com/textlint-ja/textlint-rule-preset-ai-writing) (textlint-ja, MIT License).
- Thanks also to the authors and communities of [textlint](https://github.com/textlint/textlint) itself, [textlint-rule-preset-ja-technical-writing](https://github.com/textlint-ja/textlint-rule-preset-ja-technical-writing), [textlint-rule-prh](https://github.com/textlint-rule/textlint-rule-prh), and every other OSS dependency. Each package is governed by its own license.
- The yorisoi skill's vocabulary lists use Jonathan Waller's [tanos.co.uk JLPT lists](http://www.tanos.co.uk/jlpt/) (CC BY) via [jamsinclair/open-anki-jlpt-decks](https://github.com/jamsinclair/open-anki-jlpt-decks) and [elzup/jlpt-word-list](https://github.com/elzup/jlpt-word-list) (MIT), and NINJAL's [basic vocabulary survey data](https://mmsrv.ninjal.ac.jp/bvjsl84/) (CC BY 4.0).
- Morphological analysis for the vocabulary check uses [kuromoji.js](https://github.com/takuyaa/kuromoji.js) (Apache-2.0) and [kuromojin](https://github.com/azu/kuromojin) (MIT).

## License

MIT
