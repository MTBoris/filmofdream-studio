# HANDOFF — Film of Dream (state on 2026-11-09, plan approved)

## Channel status (checked 2026-11-07)
- Monetization was removed earlier (≈700 audiobooks without rights; deleted). Earn page: terms accepted, AdSense not linked, review not started.
- Channel cleaned (spam/affiliate videos, duplicates, videos with others' music hidden; card number removed from descriptions).
- Threshold until 2027-02-01: 4,000 watch hours / year; after that 8,000. Plan: 5–10 new videos in one format, then AdSense and application.
- RESTHE publishes scheduled Shorts on this channel — do not touch them; schedule our videos at other times.
- YouTube auto-dubbing is ON (Boris decided to keep it: English viewers hear an English dub).

## Decisions
- Format: 8–15 min, Russian, intrigue in title/thumbnail, hook in 5–10 s, answer at the end, rotating moods.
- Voice: Azure **ru-RU-DmitryNeural** (Boris chose it). Qwen3-TTS/Silero/Piper/Chatterbox rejected (stress errors / non-commercial licences / unknown licences / quality).
- Stress: IPA phoneme via `+` marks (Boris confirmed variant 3 sounds right). Homograph guard added after Boris found "острова́/о́строва" errors.
- Visuals: real stock video (Pixabay; Pexels API keys are paused) + code graphics only for maps/numbers. AI/fantasy/3D clips filtered out; every query word must be in clip tags.
- Boris's verdict on pilot v1–v2: visuals made by Claude are weak → **ChatGPT owns visuals**, Claude Code owns engineering, Claude coordinates (decided 2026-11-09).
- Budget: everything free except OpenAI images, max $10/month.
- **Visual concept «ОКЕАН + НАЛОЖЕНИЯ» (Boris, 2026-11-09):** almost the whole video is real Pixabay ocean footage as background with animated graphics on top of what the narrator says (coordinates, depth, raft size, dates, scale, semi-transparent maps). Every shot is a different ocean clip (waves, horizon, aerial, sunset, storm, deep water); **no stock clip repeats within an episode**. Shots without ocean: only ChatGPT reconstruction images (1876, logbook, old charts) and real NASA photos. Must look good: dark gradient under text for legibility, smooth fade-in, number counters, slow motion. Style (palette, fonts PT Serif / IBM Plex Sans, margins 90/65 px, motion rules) comes from ChatGPT's visual direction v1 → `design/tokens.json`.
- **Templates (drawn over the ocean video):** `ocean-fact` (big number with counter), `ocean-coords` (coordinates + dot), `ocean-map` (semi-transparent area map with marker and scale), `ocean-timeline` (dates), `ocean-compare` (size comparison, e.g. raft 463×55 km vs island 25×5 km), `lower-third` (caption/source), `title-card` (chapter/final title). Plus shot type `image` (ChatGPT picture, Ken Burns, label РЕКОНСТРУКЦИЯ). Build order: ocean-fact, ocean-map, ocean-timeline → preview for Boris (one full pilot scene) → the rest.
- **Storyboard v2:** explicit `dur` per shot; the last shot of a scene may have `"dur": "rest"` (takes the remainder); sum tolerance ±1.5 s so that re-recording the narration does not break the build. Stock shot has optional `overlay`: template + data. Stock search returns 3 candidates per shot + a candidate sheet for ChatGPT to choose from; no pick → build stops. The ocean clip pool is cached; if there are not enough unique clips the build reports it instead of silently repeating.
- **Hand-over from ChatGPT: variant A** (through Boris/Claude, no repo access for ChatGPT).
- **QA rule (one hard rule at first):** no stock clip is used twice in an episode.

## Topics (approved, checked on YouTube 2026-11-07; RU best video views / EN best video views)
1. Остров Сэнди — phantom island, 136 years on maps (pilot) — 1.4k / 3.2M
2. Озеро Натрон — birds turned "to stone" (next; teased at the end of the pilot) — 7.8k / 21M
3. Флот Хубилая и «божественный ветер» + playing cards found on a Mongol wreck (news 2026-11-06) — 0.6k / 7.7M
4. Доггерленд — country under the North Sea — 15k / 4M
5. Снятся ли паукам сны — 27k / 3M
6. Бетельгейзе: hidden companion star — 9k / 2.5M
7. Дерево Тенере — none / 0.16M
8. Грейфрайерс Бобби — none / 0.1M
9. Огни Хессдалена — 13k / 0.23M
10. Кровь динозавра, 115 млн лет — 7.6k / 0.09M

## Pilot «Остров Сэнди» — `episodes/001-sandy-island/`
- `script.md` (reviewed by ChatGPT, facts checked against Seton et al., Eos 2013), `narration.txt` (TTS text, `@scene` markers, `//` dramatic pause, `+` stress), `storyboard.json`, `meta.json` (title, description with {CHAPTERS}, sources, music credits), `thumbnail.jpg` (ChatGPT, approved).
- Current upload (unlisted): see `build/youtube_url.txt`. Earlier version YYWb88h62Ws deleted with Boris's approval.
- Open from Boris's review: visual quality; check the new build's stress fixes.

## Pipeline
1. `scripts/narrate_azure.py EP` → `out/narration.wav` (48 kHz, loudnorm −16 LUFS) + `out/timeline.json` (scene start times). Stops on unmarked homographs.
2. `scripts/visuals_sandy.py frames` → code graphics (episode-specific; to be replaced by ChatGPT's designs/templates).
3. `scripts/stock.py storyboard.json stock` → Pixabay clips (film only, tag match), `stock/stock.json` with sources.
4. `scripts/render2.py ...` → shots (Ken Burns on stills, stock looped/cropped), 0.5 s cross-dissolves, music bed ducked under voice, storyboard sheet.
5. `scripts/fill_meta.py` → chapters from timeline. `scripts/yt_upload.py` → unlisted upload + thumbnail (`containsSyntheticMedia: true`).
- Workflow: **Produce episode v2** (`produce2.yml`, inputs: episode, visuals, upload yes/no). Others: `frame-review.yml`, `visuals-preview.yml` (kept until templates exist), `yt-check.yml`, `yt-delete.yml` (only with Boris's "да"), `azure-test.yml`, `azure-stress.yml` (test texts and outputs in `voices/tests/`).
- Old experiments removed in PR 1 (still in git history): `tts-bench`, `voice-*`, `narrate.yml`, `produce.yml`, `scripts/narrate.py` (Qwen), `scripts/render.py`, `bench/`, `casting/`, `samples/`. The narration.txt parser now lives in `scripts/narrate_azure.py`.

## Next steps
Engineering plan (approved 2026-11-09), small PRs, each: plan → Boris «да» → PR → green CI → merge.
1. **PR 1 — cleanup** (this PR).
2. **PR 2 — minimal CI** (`ci.yml`: pytest + ruff, offline tests: stress marks, homograph guard, shot timing, fill_meta, storyboard validation, tiny render smoke test).
3. **PR 3 — storyboard v2** (format above, converter for episode 001, 3-candidate stock search + candidate sheet, `docs/STORYBOARD.md` with the ChatGPT prompt).
4. **PR 4 — templates** + `design/tokens.json` (order above; preview for Boris before the rest).
5. **PR 5 — automatic QA** (frame sheet every 2 s as artifact, rule: no repeated stock clip; upload refused on failure).

Other:
- ChatGPT: visual direction for the pilot (choose clips from candidate sheet, images for scenes without footage: 1876 whaler, logbook, Admiralty chart, E.D., pumice raft, maps).
- Claude: rebuild pilot with the new visuals → frame review → link to Boris → publish date (avoid RESTHE Shorts times).
- Then episode 2 (Озеро Натрон), cadence every 2 days.
