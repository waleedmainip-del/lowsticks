# lowsticks clipper

Turns a long video or stream VOD into vertical clips (1080x1920) with word-by-word captions,
ready for TikTok / Reels / Shorts clipping campaigns.

How it picks moments: it listens for the parts that are much louder than the stream's own
normal level (screaming, laughing, hype), writes down what is said there, scores each moment
(loudness + hype words + how much is being said) and cuts the best ones on sentence boundaries.

## Option A - run it on GitHub (nothing to install)

1. Open the repo on GitHub -> **Actions** tab -> **Make clips** -> **Run workflow**.
2. Paste the video link, set how many clips, press **Run workflow**.
3. When the run is green, open it and download **clips-N** at the bottom (a zip with the
   clips, `clips.md` and `clips.json` with timestamps, transcript and a suggested title).

Long VOD? Fill **section** (e.g. `2:10:00-2:40:00`) so it only downloads that part - faster.

YouTube sometimes blocks GitHub's servers ("Sign in to confirm you're not a bot").
Twitch, Kick and direct .mp4 links work without that. For YouTube, export cookies from a
logged-in browser (cookies.txt format) and save them as a repository secret called
`YT_COOKIES` (Settings -> Secrets and variables -> Actions).

## Option B - run it on your computer

Windows: double-click `clipper/install.bat` once. Then, in that folder:

```
python clip.py "https://www.twitch.tv/videos/123456789" --count 3
python clip.py my_video.mp4 --count 5 --min 25 --max 45
python clip.py "LINK" --section 1:00:00-1:30:00 --title-overlay
```

Mac/Linux: `bash clipper/install.sh`, then the same commands with `python3`.

Clips land in `clips_out/`.

## Options

| option | what it does |
| --- | --- |
| `--count 3` | number of clips |
| `--min 20 --max 55` | clip length range in seconds |
| `--section A-B` | only use part of the video |
| `--layout blur` / `crop` | whole frame with blurred background (default) or fill the screen |
| `--language en` | spoken language (`ar`, `fr`, `ur` ...) or blank to detect |
| `--model base` | `tiny` fastest, `small` most accurate |
| `--title-overlay` | puts the suggested hook at the top for the first 3.5 s |
| `--no-caps` | captions in normal case instead of CAPS |
| `--keep-source` | keep the downloaded video |

## Campaign rules

Each campaign (Content Rewards etc.) has its own rules: which creator's content is allowed,
minimum length, required tags, no watermarks, etc. Check the campaign page before posting.
The clipper only processes the links you give it.
