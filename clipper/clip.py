#!/usr/bin/env python3
"""
lowsticks clipper - turns a long video / stream VOD into ready-to-post vertical clips.

    python clipper/clip.py "https://www.twitch.tv/videos/123456789" --count 5
    python clipper/clip.py my_stream.mp4 --count 3 --section 1:00:00-1:45:00

Pipeline
  1. get the video (yt-dlp for links: YouTube, Twitch, Kick, X, direct .mp4 ...)
  2. find the hype moments from the audio (loudness spikes vs. the stream's own normal level)
  3. transcribe only those moments (faster-whisper, runs on CPU)
  4. score them (loudness + hype words + how fast people talk) and pick the best ones
  5. cut each one on sentence boundaries and render a 1080x1920 clip with
     word-by-word captions
  6. write clips.json / clips.md with timestamps, transcript and a suggested title

Everything is local / free. Needs ffmpeg on PATH.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FONTS_DIR = HERE / "fonts"

HYPE_WORDS = {
    # phrase -> weight
    "oh my god": 2.0, "omg": 1.5, "no way": 2.0, "let's go": 2.0, "lets go": 2.0,
    "what the": 1.5, "wtf": 1.5, "holy": 1.5, "insane": 1.5, "crazy": 1.2,
    "bro": 0.6, "yo": 0.6, "wait": 0.8, "dude": 0.6, "chat": 0.6, "bruh": 0.8,
    "oh no": 1.5, "help": 0.8, "run": 0.6, "stop": 0.6, "what": 0.4,
    "haha": 1.0, "laugh": 1.2, "screams": 1.5, "scream": 1.2, "shut up": 1.0,
    "are you serious": 1.5, "i can't": 1.0, "no no no": 1.5, "yes": 0.4,
}

# --------------------------------------------------------------------------- utils


def log(msg: str) -> None:
    print(f"[clipper] {msg}", flush=True)


def run(cmd: list[str], cwd: Path | None = None, quiet: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, cwd=cwd, capture_output=quiet, text=True)
    if res.returncode != 0:
        if quiet:
            sys.stderr.write(res.stderr[-3000:] if res.stderr else "")
        raise SystemExit(f"command failed ({res.returncode}): {' '.join(cmd[:6])} ...")
    return res


def need(tool: str) -> None:
    if shutil.which(tool) is None:
        raise SystemExit(f"'{tool}' not found. Install it first (see clipper/README.md).")


def hms(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(int(round(t)), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_time(s: str) -> float:
    parts = [float(p) for p in s.strip().split(":")]
    sec = 0.0
    for p in parts:
        sec = sec * 60 + p
    return sec


def probe_duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)]).stdout.strip()
    return float(out)


def probe_size(path: Path) -> tuple[int, int]:
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height", "-of", "csv=p=0", str(path)]).stdout.strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


# --------------------------------------------------------------------------- 1. acquire


def acquire(src: str, work: Path, section: str | None, cookies: str | None) -> tuple[Path, dict]:
    p = Path(src)
    if p.exists():
        log(f"using local file {p}")
        return p.resolve(), {"title": p.stem, "uploader": "", "url": str(p)}

    log(f"downloading {src}")
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-progress",
           "-f", "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
           "--merge-output-format", "mp4",
           "-o", str(work / "source.%(ext)s"),
           "--write-info-json"]
    if section:
        a, b = section.split("-", 1)
        cmd += ["--download-sections", f"*{a.strip()}-{b.strip()}", "--force-keyframes-at-cuts"]
    if cookies:
        cmd += ["--cookies", cookies]
    cmd.append(src)
    res = subprocess.run(cmd, capture_output=True, text=True)
    lines: list[str] = []
    vids = [f for f in work.glob("source*") if f.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")]
    if lines:
        path = Path(lines[-1].strip())
    elif vids:
        path = vids[0]
    else:
        err = (res.stderr or res.stdout or "").strip()[-1500:]
        hint = ""
        if "Sign in to confirm" in err or "bot" in err.lower():
            hint = ("\nYouTube blocked this server. Use a Twitch/Kick/direct link, or add your YouTube "
                    "cookies (see clipper/README.md).")
        raise SystemExit(f"download failed:\n{err}{hint}")
    info = {"title": "", "uploader": "", "url": src}
    info_file = next(work.glob("source*.info.json"), None)
    if info_file:
        meta = json.loads(info_file.read_text(encoding="utf-8"))
        info.update(title=meta.get("title") or "", uploader=meta.get("uploader") or meta.get("channel") or "",
                    url=meta.get("webpage_url") or src)
    return path, info


# --------------------------------------------------------------------------- 2. audio energy

HOP = 0.5  # seconds per loudness frame


def extract_audio(video: Path, wav: Path) -> None:
    run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(wav)])


def loudness_curve(wav: Path) -> np.ndarray:
    with wave.open(str(wav), "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    hop = int(sr * HOP)
    n = len(data) // hop
    if n == 0:
        return np.zeros(1)
    frames = data[: n * hop].reshape(n, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-10)
    return 20 * np.log10(rms + 1e-10)


def excitement(db: np.ndarray) -> np.ndarray:
    """How much louder than this stream's own normal level each moment is (robust z-score)."""
    win = int(60 / HOP)  # compare against the surrounding minute
    pad = np.pad(db, (win // 2, win // 2), mode="edge")
    view = np.lib.stride_tricks.sliding_window_view(pad, win)[: len(db)]
    base = np.median(view, axis=1)
    dev = db - base
    mad = np.median(np.abs(dev - np.median(dev))) + 1e-6
    z = dev / (1.4826 * mad)
    k = int(3 / HOP)  # smooth over 3 seconds
    z = np.convolve(z, np.ones(k) / k, mode="same")
    z[db < -50] = 0  # silence is never a highlight
    return np.clip(z, -5, 12)


def find_peaks(z: np.ndarray, n: int, min_gap_s: float) -> list[float]:
    order = np.argsort(z)[::-1]
    gap = int(min_gap_s / HOP)
    taken: list[int] = []
    for i in order:
        if z[i] <= 0.5:
            break
        if all(abs(i - j) >= gap for j in taken):
            taken.append(int(i))
            if len(taken) >= n:
                break
    return [i * HOP for i in taken]


# --------------------------------------------------------------------------- 3. transcription


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Candidate:
    peak: float
    start: float = 0.0
    end: float = 0.0
    words: list[Word] = field(default_factory=list)
    score: float = 0.0
    text: str = ""
    title: str = ""


_MODEL = None


def get_model(name: str):
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        log(f"loading speech model '{name}' (first run downloads it)")
        _MODEL = WhisperModel(name, device="cpu", compute_type="int8")
    return _MODEL


def transcribe_region(wav: Path, start: float, end: float, model: str, language: str | None) -> list[Word]:
    with wave.open(str(wav), "rb") as w:
        sr = w.getframerate()
        w.setpos(int(start * sr))
        raw = w.readframes(int((end - start) * sr))
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    segs, _ = get_model(model).transcribe(audio, language=language or None, word_timestamps=True,
                                          vad_filter=True, condition_on_previous_text=False)
    words: list[Word] = []
    for s in segs:
        for wd in (s.words or []):
            t = wd.word.strip()
            if t:
                words.append(Word(start + wd.start, start + wd.end, t))
    return words


# --------------------------------------------------------------------------- 4. choose windows

SENT_END = re.compile(r"[.!?]$")


def shape_window(c: Candidate, z: np.ndarray, min_len: float, max_len: float, duration: float) -> None:
    """Pick start/end around the peak, snapped to sentence/pause boundaries."""
    ws = c.words
    lead = min(max_len * 0.55, 18.0)  # context before the moment
    if not ws:
        c.start = max(0.0, c.peak - min_len * 0.6)
        c.end = min(duration, c.start + min_len)
        return
    # start: a word that begins a sentence (or follows a pause) near peak-lead
    target = c.peak - lead
    starts = [0] + [i for i in range(1, len(ws))
                    if SENT_END.search(ws[i - 1].text) or ws[i].start - ws[i - 1].end > 0.6]
    si = min(starts, key=lambda i: abs(ws[i].start - target))
    if ws[si].start > c.peak - 3:  # never start after the moment itself
        earlier = [i for i in starts if ws[i].start <= c.peak - 3]
        si = earlier[-1] if earlier else 0
    c.start = max(0.0, ws[si].start - 0.25)
    # end: first sentence end after the peak that gives at least min_len, at most max_len
    ends = [i for i in range(si, len(ws))
            if SENT_END.search(ws[i].text) or i == len(ws) - 1
            or (i + 1 < len(ws) and ws[i + 1].start - ws[i].end > 0.7)]
    ei = None
    for i in ends:
        length = ws[i].end - c.start
        if ws[i].end >= c.peak + 2 and length >= min_len:
            ei = i
            break
    if ei is None:
        ok = [i for i in ends if ws[i].end - c.start <= max_len]
        ei = ok[-1] if ok else len(ws) - 1
    c.end = min(duration, ws[ei].end + 0.4)
    if c.end - c.start > max_len:
        c.end = c.start + max_len
    if c.end - c.start < min_len:
        c.end = min(duration, c.start + min_len)
    c.words = [w for w in ws if w.start >= c.start - 0.05 and w.end <= c.end + 0.05]


def score(c: Candidate, z: np.ndarray) -> None:
    a, b = int(c.start / HOP), max(int(c.start / HOP) + 1, int(c.end / HOP))
    seg = z[a:b]
    loud_peak = float(seg.max()) if len(seg) else 0.0
    loud_mean = float(np.clip(seg, 0, None).mean()) if len(seg) else 0.0
    text = " ".join(w.text for w in c.words)
    low = text.lower()
    hype = sum(wt * low.count(k) for k, wt in HYPE_WORDS.items())
    dur = max(1.0, c.end - c.start)
    wps = len(c.words) / dur
    talk = min(wps, 3.5) / 3.5  # people talking fast and a lot = engaging
    punct = text.count("!") * 0.3 + text.count("?") * 0.15
    c.score = round(loud_peak * 1.0 + loud_mean * 1.5 + min(hype, 6) * 0.6 + talk * 1.5 + punct, 3)
    c.text = text


def make_title(c: Candidate) -> str:
    """A short hook: the most excited sentence in the clip."""
    sentences = re.split(r"(?<=[.!?])\s+", c.text.strip())
    sentences = [s for s in sentences if 3 <= len(s.split()) <= 14] or sentences or [""]
    def hype(s: str) -> float:
        l = s.lower()
        return sum(w for k, w in HYPE_WORDS.items() if k in l) + s.count("!") + s.count("?") * 0.5
    best = max(sentences, key=hype)
    best = best.strip().strip('"')
    return (best[:77] + "...") if len(best) > 80 else best


# --------------------------------------------------------------------------- 5. captions + render


def ass_escape(t: str) -> str:
    return t.replace("\\", "").replace("{", "(").replace("}", ")")


def ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(c: Candidate, out: Path, font: str, upper: bool, title_text: str | None,
              words_per_line: int = 3) -> None:
    hl = "&H0000E5FF&"   # yellow (BGR)
    white = "&H00FFFFFF&"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,70,70,560,1
Style: Title,{font},62,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,18,0,8,90,90,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [head]
    if title_text:
        tt = ass_escape(title_text.upper() if upper else title_text)
        lines.append(f"Dialogue: 1,{ass_time(0)},{ass_time(3.5)},Title,,0,0,0,,{tt}\n")
    # group words into short chunks (break on punctuation / pauses)
    ws = c.words
    chunks: list[list[Word]] = []
    cur: list[Word] = []
    for i, w in enumerate(ws):
        cur.append(w)
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        brk = (len(cur) >= words_per_line or re.search(r"[.!?,]$", w.text)
               or (nxt is not None and nxt.start - w.end > 0.5) or nxt is None)
        if brk:
            chunks.append(cur)
            cur = []
    for ci, ch in enumerate(chunks):
        nxt_start = chunks[ci + 1][0].start if ci + 1 < len(chunks) else ch[-1].end + 0.6
        chunk_end = min(nxt_start, ch[-1].end + 0.6)
        for wi, w in enumerate(ch):
            st = w.start
            en = ch[wi + 1].start if wi + 1 < len(ch) else chunk_end
            parts = []
            for k, x in enumerate(ch):
                word = ass_escape(x.text.upper() if upper else x.text)
                col = hl if k == wi else white
                scale = r"\fscx108\fscy108" if k == wi else ""
                parts.append(f"{{\\c{col}{scale}}}{word}{{\\fscx100\\fscy100}}")
            lines.append(f"Dialogue: 0,{ass_time(st - c.start)},{ass_time(en - c.start)},Cap,,0,0,0,,"
                         + " ".join(parts) + "\n")
    out.write_text("".join(lines), encoding="utf-8")


def render(src: Path, c: Candidate, out_mp4: Path, ass: Path, layout: str) -> None:
    sw, sh = probe_size(src)
    vertical = sh >= sw * 1.5
    if layout == "crop" or vertical:
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:  # blur: full frame in the middle, blurred copy as background
        vf = ("split=2[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              "gblur=sigma=28,eq=brightness=-0.10[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    fonts = f":fontsdir={FONTS_DIR.name}" if FONTS_DIR.exists() else ""
    # run from the clip folder so the subtitle path has no drive letters / backslashes
    filt = f"[0:v]{vf},fps=30[base];[base]subtitles={ass.name}{fonts}[v]"
    if FONTS_DIR.exists():
        tmp_fonts = ass.parent / FONTS_DIR.name
        if not tmp_fonts.exists():
            shutil.copytree(FONTS_DIR, tmp_fonts)
    tmp = ass.parent / (out_mp4.stem + ".part.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{c.start:.3f}", "-i", str(src), "-t", f"{c.end - c.start:.3f}",
         "-filter_complex", filt, "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-movflags", "+faststart", tmp.name], cwd=ass.parent)
    tmp.replace(out_mp4)


# --------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description="Make vertical clips from a long video or stream VOD.")
    ap.add_argument("source", help="link (YouTube, Twitch, Kick, X, direct .mp4) or a local video file")
    ap.add_argument("--count", type=int, default=3, help="how many clips to make (default 3)")
    ap.add_argument("--min", dest="min_len", type=float, default=20, help="shortest clip in seconds (default 20)")
    ap.add_argument("--max", dest="max_len", type=float, default=55, help="longest clip in seconds (default 55)")
    ap.add_argument("--section", help="only look at part of the video, e.g. 1:00:00-1:45:00")
    ap.add_argument("--layout", choices=["blur", "crop"], default="blur",
                    help="blur = whole frame + blurred background (safe), crop = fill the screen")
    ap.add_argument("--language", default="en", help="spoken language code, e.g. en, ar, fr (blank = detect)")
    ap.add_argument("--model", default="base", help="speech model: tiny, base, small (bigger = better, slower)")
    ap.add_argument("--font", default="Poppins ExtraBold", help="caption font")
    ap.add_argument("--no-caps", action="store_true", help="keep captions in normal case")
    ap.add_argument("--title-overlay", action="store_true", help="show the suggested hook at the top for 3.5s")
    ap.add_argument("--cookies", help="cookies.txt for sites that need a login (e.g. YouTube bot check)")
    ap.add_argument("--out", default="clips_out", help="output folder (default clips_out)")
    ap.add_argument("--keep-source", action="store_true", help="keep the downloaded video")
    args = ap.parse_args()

    need("ffmpeg")
    need("ffprobe")
    out = Path(args.out).resolve()
    work = out / "_work"
    work.mkdir(parents=True, exist_ok=True)

    src, info = acquire(args.source, work, args.section, args.cookies)
    duration = probe_duration(src)
    log(f"video: {hms(duration)} long")
    if duration < args.min_len + 2:
        raise SystemExit("video is shorter than one clip")

    wav = work / "audio.wav"
    extract_audio(src, wav)
    db = loudness_curve(wav)
    z = excitement(db)

    # more candidates than needed, transcribe them, keep the best
    n_cand = max(args.count * 3, args.count + 2)
    peaks = find_peaks(z, n_cand, min_gap_s=args.max_len * 0.8)
    if not peaks:  # flat audio: fall back to evenly spaced moments
        step = duration / (n_cand + 1)
        peaks = [step * (i + 1) for i in range(n_cand)]
    log(f"found {len(peaks)} loud moments, transcribing them")

    cands: list[Candidate] = []
    for i, pk in enumerate(sorted(peaks)):
        a = max(0.0, pk - args.max_len * 0.75)
        b = min(duration, pk + args.max_len * 0.75)
        c = Candidate(peak=pk)
        c.words = transcribe_region(wav, a, b, args.model, args.language or None)
        shape_window(c, z, args.min_len, args.max_len, duration)
        score(c, z)
        c.title = make_title(c)
        cands.append(c)
        log(f"  moment {i + 1}/{len(peaks)} at {hms(pk)}: score {c.score}")

    # best first, no overlaps
    chosen: list[Candidate] = []
    for c in sorted(cands, key=lambda x: x.score, reverse=True):
        if all(c.end <= o.start or c.start >= o.end for o in chosen):
            chosen.append(c)
        if len(chosen) >= args.count:
            break

    results = []
    for rank, c in enumerate(chosen, 1):
        name = f"clip_{rank:02d}"
        ass = work / f"{name}.ass"
        build_ass(c, ass, args.font, not args.no_caps, c.title if args.title_overlay else None)
        mp4 = out / f"{name}.mp4"
        log(f"rendering {name}: {hms(c.start)}-{hms(c.end)} ({c.end - c.start:.0f}s)")
        render(src, c, mp4, ass, args.layout)
        tags = ["#shorts", "#clips"]
        if info.get("uploader"):
            tags.insert(0, "#" + re.sub(r"\W+", "", info["uploader"]).lower())
        results.append({
            "file": mp4.name, "rank": rank, "score": c.score,
            "start": round(c.start, 2), "end": round(c.end, 2),
            "start_hms": hms(c.start), "end_hms": hms(c.end), "seconds": round(c.end - c.start, 1),
            "suggested_title": c.title, "hashtags": tags, "transcript": c.text,
        })

    meta = {"source": info, "video_seconds": round(duration, 1), "clips": results}
    (out / "clips.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    md = [f"# Clips from: {info.get('title') or info.get('url')}\n",
          f"Source: {info.get('url')}  \nCreator: {info.get('uploader') or '-'}\n"]
    for r in results:
        md.append(f"\n## {r['file']}  ({r['start_hms']} - {r['end_hms']}, {r['seconds']}s, score {r['score']})\n"
                  f"**Title:** {r['suggested_title']}  \n**Tags:** {' '.join(r['hashtags'])}\n\n> {r['transcript']}\n")
    (out / "clips.md").write_text("".join(md), encoding="utf-8")

    if not args.keep_source and src.parent == work:
        src.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)
    log(f"done: {len(results)} clips in {out}")


if __name__ == "__main__":
    main()
