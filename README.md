# Shorts Factory

Faceless tech Shorts, end to end:

```
RSS/arXiv sources ─▶ pick fresh item ─▶ Claude writes script (one of 9 formats)
   ─▶ neural voiceover + word timings ─▶ 1080x1920 render (captions, your logo) ─▶ YouTube upload
```

Sources: Towards Data Science, Medium (AI / software-eng / LLM tags), Netflix TechBlog, Amazon Science,
AWS ML blog, Microsoft Research, Microsoft Engineering blog, Google Research, arXiv (cs.AI / cs.LG / cs.SE).
Edit `config.yaml` to add or remove feeds.

Formats (`--format`): `concept_explainer`, `ask_question`, `research_opinion`, `myth_vs_fact`, `analogy`,
`interview_question`, `hot_take`, `quick_news`, `this_vs_that`. Add more in `src/formats.py`.

## Setup

```bash
cd shorts-factory
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY
```

1. **Logo**: replace `assets/logo.png` with yours (square PNG, transparent background). Set channel name/handle in `config.yaml`.
2. **Optional music**: drop royalty-free `.mp3` files in `assets/music/` (mixed in at 6% volume).
3. **YouTube** (one time):
   - Google Cloud Console → new project → enable *YouTube Data API v3*.
   - OAuth consent screen (External, add yourself as a test user) → Credentials → *OAuth client ID* → *Desktop app*.
   - Download the JSON as `client_secret.json` in this folder, then `python main.py auth`.

## Use

```bash
python main.py sources                       # preview ranked candidates
python main.py run --mock --n 1              # test render + voice with no API key
python main.py run --n 3                     # make 3 videos into output/
python main.py run --n 3 --publish           # make and upload (privacy from config.yaml)
python main.py run --format research_opinion --source netflix --n 1
python main.py upload output/<folder> --privacy public
```

Each video gets a folder in `output/` with `script.json`, `voice.wav`, `video.mp4`. Used source URLs are
tracked in `data/factory.db` so nothing is made twice.

Daily automation (cron, 3 videos at 09:00):

```
0 9 * * * cd /path/to/shorts-factory && .venv/bin/python main.py run --n 3 --publish >> data/cron.log 2>&1
```

## Things to know before publishing

- **Upload limits**: a `videos.insert` costs 1,600 quota units of the default 10,000/day (~6 uploads/day).
  Uploads from a *new, unverified* API project are forced private until you pass Google's API audit
  (request it via the YouTube API Services compliance form). Until then, publish by flipping the video to public in Studio.
- **Start with `privacy: private`** and review a few batches. The script writer is told not to invent facts,
  but a human skim of `script.json` is the real safety net, especially for `research_opinion` and `hot_take`.
- **Monetisation**: YouTube's "inauthentic / mass-produced content" policy targets repetitive, low-effort
  automated channels. Original commentary, varied formats, and your own opinion in the prompts help; pure
  summaries of other people's articles do not. Each video credits and links its source.
- **Synthetic media label**: `contains_synthetic_media` is off since the voice narrates abstract content, not a
  realistic person. Turn it on if you'd rather disclose.
- **Voice**: `edge-tts` is free (unofficial Microsoft endpoint, can change). For production, swap `src/tts.py`
  for ElevenLabs/Azure/OpenAI TTS; it only needs to return per-scene audio plus word timings.

## Music, memes and clips

- **Background music**: `python main.py music add song.mp3 --mood upbeat` (moods: calm, chill, upbeat, tense, funny, any).
  Each format has preferred moods; a track is picked automatically, ducked under the voice and faded out.
  Pin one track with `video.music.fixed`, or disable with `video.music.mode: off`. Use music you hold the licence for.
- **Memes**: the `meme_explainer` format picks an Imgflip template that fits the joke and draws the caption itself.
- **Stock video**: set `PEXELS_API_KEY` in `.env` (free) and Claude can add portrait b-roll to scenes.
- **Your own clips (series moments, screen recordings)**:
  `python main.py library add clip.mp4 --id my-clip --start 12 --duration 6 --tags scaling --desc "what happens" --credit "Show name"`.
  `series_moment` uses only clips listed there, as short illustrations (max 8s) under your commentary.
  Rights are your call: unlicensed show/film clips can trigger Content ID claims or strikes even with commentary.
  Prefer clips you own or have licensed, and check results while videos are still private.

## Daily schedule

`./schedule.sh install` adds a cron job (09:00, 3 videos, `--publish`); `./schedule.sh remove` deletes it.
The Mac must be awake at that time (or use `pmset repeat wakeorpoweron`). Requires `.env`, `client_secret.json`
and `token.json` to exist first.
