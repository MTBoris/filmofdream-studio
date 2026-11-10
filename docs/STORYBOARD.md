# Storyboard v2 (ChatGPT → pipeline)

One JSON file per episode: `episodes/NNN-name/storyboard.json`. ChatGPT writes it; Boris/Claude commit it
(ChatGPT has no repo access). Images go to `episodes/NNN-name/assets/<asset_id>.png|jpg`.

```json
{
  "version": 2,
  "assets": {
    "whaler_1876": {"label": "РЕКОНСТРУКЦИЯ"},
    "gavre_modis_2012": {
      "page": "https://earthobservatory.nasa.gov/images/78863",
      "credit": "NASA image courtesy Jeff Schmaltz, LANCE/EOSDIS MODIS Rapid Response Team, GSFC"
    }
  },
  "scenes": [
    {
      "scene": "coral_sea",
      "duration": 38.0,
      "shots": [
        {"id": "coral-1", "type": "stock", "query": "ocean waves aerial", "queries": ["sea waves drone"],
         "dur": 7, "pick": "pix:123456",
         "overlay": {"template": "ocean-coords", "data": {"lat": "19°13′ ю. ш.", "lon": "159°55′ в. д."},
                     "cue": "Коралловое море"}},
        {"id": "coral-2", "type": "image", "asset_id": "whaler_1876", "dur": "rest", "motion": "push-in"}
      ]
    }
  ]
}
```

## Fields
- `scene` – must match an `@scene` name in `narration.txt`. Every narration scene needs an entry and vice versa.
- `duration` (scene) – ChatGPT's estimate, informational only; the real scene length comes from the narration.
- Shot `type`:
  - `stock` – Pixabay footage. `query` is English; optional `queries` are alternatives when the first gives too few clips.
    `pick` is `"pix:<id>"`, chosen from the **candidate sheet** (below). **No pick → the build stops.**
  - `image` – a picture made by ChatGPT, `asset_id` = file name in `assets/` (≥ 1280 px wide, 16:9 preferred).
    If the asset has a `label` (e.g. `РЕКОНСТРУКЦИЯ`) it is stamped in the top-left corner.
  - `external-image` – a real photo (NASA). The asset must be declared in `assets` with `url` or `page` (NASA Earth Observatory
    page) and a `credit`; the credit is added to the video description. No logos are added.
- `dur` – seconds, or `"rest"` on the **last** shot of a scene (takes what is left, at least 1 s).
  If no shot is `"rest"`, the sum must be within ±1.5 s of the real scene length (the shots are then stretched to fit exactly).
  So re-recording the voice does not break the build.
- `motion` (images) – `push-in` (default), `pull-out`, `pan-left`, `pan-right`, `none`.
- `overlay` – graphics on top of the shot: `template` + `data` (see the template list in `docs/HANDOFF.md`).
  Timing follows the voice: `cue` is a phrase **as written in narration.txt** that must be inside this scene; the overlay appears
  when Azure says the first word of the phrase (`nth` = which occurrence, default 1). Without `cue`: `at` seconds after the shot
  start (default 0.4). `dur` optional (default: until the shot ends).

## Rules the validator enforces
1. No stock clip is used twice in an episode (candidates are unique across shots; two equal picks are an error).
2. Unique ids for shots; known types and motions; valid `pick` format.
3. Every narration scene is in the storyboard and the other way round.
4. A cue that is not found in the scene, or is spoken outside its shot, is an error (with the words that were heard).

## Choosing clips (3 candidates per shot)
1. Boris/Claude run **Stock candidates (3 per shot)** (GitHub Actions). It writes
   `episodes/NNN/build/candidates/sheet-01.jpg …` (each shot: 3 candidates × 3 frames, with `pix:<id>`, length, tags)
   and `candidates.json`. Searches are cached in `pool.json`.
2. ChatGPT looks at the sheets and returns the `pick` for every stock shot.
3. If a shot got fewer than 3 unique clips, the log says `NOT ENOUGH UNIQUE CLIPS` – nothing is repeated silently.
   Fix by adding `queries` or changing the query, and run the candidates again.

## Prompt for ChatGPT (copy)
```
Ты делаешь storyboard.json для эпизода Film of Dream по формату docs/STORYBOARD.md.
Правила: сцены строго как в narration.txt (@scene). Стоковые шоты — только разные клипы океана/подходящие сцене, ни один клип
не повторяется в эпизоде. Для каждого stock-шота: id, query (английский), dur. После листа кандидатов вернёшь pick для каждого шота.
Наложения: overlay.template + data, cue — фраза из narration.txt, на которой наложение появляется. Картинки-реконструкции:
type "image", asset_id, label "РЕКОНСТРУКЦИЯ". Реальные снимки: type "external-image" + запись в assets (page/url + credit).
У последнего шота сцены можно поставить "dur": "rest". Верни только JSON.
```
