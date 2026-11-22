"""Open-source transcription, highlight selection, and vertical rendering."""

from __future__ import annotations

import re
import shutil
import subprocess
import os
from pathlib import Path
from uuid import uuid4


EMPHASIS_WORDS = {
    "amazing", "awesome", "crazy", "insane", "clutch", "win", "won", "fail",
    "no way", "oh my god", "what", "wait", "look", "bhai", "dekho", "kya",
    "unbelievable", "incredible", "finally", "actually", "secret", "mistake",
}


def _run(command: list[str], timeout: int = 7200) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "Media command failed.")[-1200:])
    return result.stdout


def _duration(path: Path) -> float:
    ffprobe = os.getenv("FFPROBE_PATH") or shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("FFprobe is missing. Install FFmpeg and make ffprobe available in PATH.")
    output = _run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        timeout=120,
    )
    try:
        return float(output.strip())
    except ValueError as exc:
        raise RuntimeError("Could not read the video's duration.") from exc


def _score(text: str, speech_seconds: float) -> float:
    lowered = text.lower()
    emphatic = sum(1 for word in EMPHASIS_WORDS if word in lowered)
    punctuation = min(text.count("!") + text.count("?"), 8)
    density = min(speech_seconds / 25, 1)
    return density * 4 + min(emphatic, 5) * 1.2 + punctuation * 0.18 + min(len(text) / 400, 1)


def _candidates(segments: list, duration: float, clip_seconds: int = 45) -> list[dict]:
    if duration <= clip_seconds:
        starts = [0.0]
    else:
        step = max(10, clip_seconds // 3)
        starts = [float(start) for start in range(0, max(1, int(duration - clip_seconds) + 1), step)]
        if not starts:
            starts = [0.0]
    candidates = []
    for start in starts:
        end = min(duration, start + clip_seconds)
        selected = [
            item for item in segments
            if float(item.start) < end and float(item.end) > start and str(item.text).strip()
        ]
        if not selected:
            continue
        text = " ".join(str(item.text).strip() for item in selected)
        speech_seconds = sum(max(0, min(float(item.end), end) - max(float(item.start), start)) for item in selected)
        candidates.append(
            {
                "start": start,
                "end": end,
                "text": text,
                "score": _score(text, speech_seconds),
                "segments": selected,
            }
        )
    chosen: list[dict] = []
    for item in sorted(candidates, key=lambda value: value["score"], reverse=True):
        if all(item["end"] <= other["start"] or item["start"] >= other["end"] for other in chosen):
            chosen.append(item)
        if len(chosen) == 3:
            break
    return sorted(chosen, key=lambda value: value["start"])


def _escape_filter_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return value.replace(":", r"\:").replace("'", r"\'").replace(",", r"\,")


def _write_srt(candidate: dict, target: Path) -> None:
    def timestamp(seconds: float) -> str:
        millis = max(0, round(seconds * 1000))
        hours, remainder = divmod(millis, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        whole_seconds, milliseconds = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"

    lines = []
    for index, segment in enumerate(candidate["segments"], 1):
        start = max(0, float(segment.start) - candidate["start"])
        end = min(candidate["end"] - candidate["start"], float(segment.end) - candidate["start"])
        text = re.sub(r"\s+", " ", str(segment.text)).strip()
        if text and end > start:
            lines.extend([str(index), f"{timestamp(start)} --> {timestamp(end)}", text, ""])
    target.write_text("\n".join(lines), encoding="utf-8")


def process_media(
    source_path: Path,
    job_id: str,
    output_dir: Path,
    language: str,
    layout: str,
    caption_style: str,
    max_seconds: int,
    update,
) -> list[dict]:
    ffmpeg = os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is missing. Install FFmpeg and make it available in PATH.")
    if not source_path.is_file():
        raise RuntimeError("The uploaded or downloaded source video is missing.")
    duration = _duration(source_path)
    if duration <= 0 or duration > max_seconds:
        raise RuntimeError(f"Video must be between 1 second and {max_seconds // 60} minutes long.")

    update(10, "Transcribing speech with open-source Whisper")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed. Install the requirements first.") from exc
    model_name = os.getenv("WHISPER_MODEL", "small")
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments_iter, info = model.transcribe(
        str(source_path),
        language=None if language == "auto" else language,
        vad_filter=True,
        word_timestamps=False,
    )
    segments = list(segments_iter)
    if not segments:
        raise RuntimeError("Whisper did not detect speech. Try a video with clear spoken audio.")
    update(30, "Ranking transcript windows with speech density and emphasis cues")
    candidates = _candidates(segments, duration)
    if not candidates:
        raise RuntimeError("Could not find a speech segment suitable for a clip.")

    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for index, candidate in enumerate(candidates, 1):
        update(35 + round(index / len(candidates) * 55), f"Rendering vertical clip {index} of {len(candidates)}")
        clip_id = uuid4().hex
        basename = f"{job_id}-{clip_id}"
        subtitles = output_dir / f"{basename}.srt"
        target = output_dir / f"{basename}.mp4"
        _write_srt(candidate, subtitles)
        if layout == "blur":
            video_filter = (
                "split[bg][fg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,boxblur=20:10[blur];[fg]scale=1080:1920:force_original_aspect_ratio=decrease[small];"
                "[blur][small]overlay=(W-w)/2:(H-h)/2"
            )
        else:
            video_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        styles = {
            "neon-glow": "FontName=Arial,FontSize=48,PrimaryColour=&H0000FF87,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2",
            "hormozi": "FontName=Arial,FontSize=48,PrimaryColour=&H0000A5FF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2",
            "cyber-yellow": "FontName=Arial,FontSize=48,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2",
            "minimal": "FontName=Arial,FontSize=44,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2",
        }
        video_filter += (
            f",subtitles='{_escape_filter_path(subtitles)}'"
            f":force_style='{styles[caption_style]}'"
        )
        _run(
            [
                ffmpeg, "-y", "-ss", f"{candidate['start']:.3f}", "-i", str(source_path),
                "-t", f"{candidate['end'] - candidate['start']:.3f}",
                "-vf", video_filter, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(target),
            ],
            timeout=7200,
        )
        title = re.sub(r"\s+", " ", candidate["text"]).strip()[:92]
        if len(candidate["text"]) > 92:
            title = title.rsplit(" ", 1)[0] + "…"
        rendered.append(
            {
                "id": clip_id,
                "title": title or f"Highlight {index}",
                "transcript": candidate["text"][:5000],
                "start": round(candidate["start"], 2),
                "end": round(candidate["end"], 2),
                "score": max(1, min(100, round(candidate["score"] * 8))),
                "file_path": str(target),
            }
        )
    update(95, f"Speech detected in {info.language}; clips and captions rendered")
    return rendered
