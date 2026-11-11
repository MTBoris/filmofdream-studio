# CLAUDE.md — Film of Dream studio

Read this first, then `docs/HANDOFF.md` (current state, decisions, next steps).

## Project
- YouTube channel **Film of Dream** (@FilmOfDream, ~60k subscribers, Russian). Google account: shuttleride25.
- Goal: get monetization back with original 8–15 min videos made by code. Owner: Boris (not a developer; give him step-by-step instructions, copyable text in code blocks).
- This repo is **public** (free GitHub Actions). Never commit secrets. Scripts become public — fine.
- **Separate project.** Never mix code, keys, accounts, names or data with GiftMorrow (mtirallc/giftmorrow) or RESTHE (MTBoris/resthe).

## Roles (Boris's decision 2026-11-11)
| Who | Does |
|---|---|
| Claude (coordinator, claude.ai project "Film of Dream") | topics, script and narration text, stress marks, fact-checking against sources, `meta.json` |
| Claude Code (session on this repo) | storyboard, automatic stock selection (filters + stock profile), maps/overlays/thumbnail by code, build, QA with frame-sheet review, **unlisted** upload, pipeline engineering (scripts, tests, CI) |
| ChatGPT | **only on request** (e.g. a reconstruction image or a second opinion on visuals); not in the default loop |
| Boris | approves topics; watches the unlisted video; **sets the public status himself** |

## Workflow
- Claude writes `narration.txt` / `script.md` / `meta.json` → Claude Code: small PR → green CI → merge (Claude Code merges its own PRs after green CI).
- Claude Code makes `storyboard.json` from `script.md`, picks stock automatically, builds, reviews the frame sheets, uploads **unlisted** and writes the link to `build/youtube_url.txt` and `docs/HANDOFF.md`.
- Public status: only Boris, by hand. Deleting a video only after Boris's "да".
- Before a link goes to Boris: frame-sheet review (frame every 2 s) and the homograph guard must pass.

## Money
- $0 by default: Azure Speech F0 (free 0.5M chars/month, no billing on F0), Pixabay (free), GitHub Actions (public repo).
- OpenAI images are not needed by default (visuals are stock + code). If ChatGPT images are requested: **max $10/month**. Anything else that costs money needs Boris's "да".

## Content rules
- Russian, 8+ minutes, hook in first 10 s, answer at the end, moods rotate (amazing / funny / mysterious / touching / eerie).
- No tragedies, no other people's films/music, no AI-generated stock that looks fake, no faces of real private people, no copyrighted characters.
- Every fact checked against a source; sources go into the description.
- Audiobooks, kids content and tragic news are excluded (bad for monetization).

## Technical facts
- Voice: Azure `ru-RU-DmitryNeural`, rate -5%. Stress: `+` before the stressed vowel in narration.txt → IPA `<phoneme>` (the only method that worked). Dictionary: `voices/pronunciations.json`. Meaning-dependent words: `voices/homographs.json` — the build stops if one is unmarked.
- Secrets (GitHub Actions): `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` (Google Cloud project `filmofdream-studio`, OAuth app in production), `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `PIXABAY_API_KEY`.
- Music: `music/ghost-1.mp3`, `music/ghost-2.mp3` (Boris's), `music/light-awash-kevin-macleod.mp3` (CC BY 4.0 — credit in every description).
