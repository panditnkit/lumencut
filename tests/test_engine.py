import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from engine import _candidates, _score, _write_srt, process_media


def test_score_rewards_speech_and_emphasis():
    ordinary = _score("A short sentence.", 8)
    emphatic = _score("Wait! That was an insane clutch!", 20)

    assert emphatic > ordinary


def test_candidates_are_non_overlapping_and_ranked():
    segments = [
        SimpleNamespace(start=2, end=12, text="A quiet introduction."),
        SimpleNamespace(start=18, end=35, text="Wait! That was an insane clutch!"),
        SimpleNamespace(start=54, end=77, text="This is an unbelievable final play!"),
        SimpleNamespace(start=84, end=98, text="An ordinary closing sentence."),
    ]

    clips = _candidates(segments, duration=110, clip_seconds=30)

    assert clips
    assert len(clips) <= 3
    assert all(
        left["end"] <= right["start"]
        for left, right in zip(clips, clips[1:])
    )
    assert clips[0]["start"] <= clips[-1]["start"]


def test_srt_uses_clip_relative_timestamps(tmp_path: Path):
    segments = [
        SimpleNamespace(start=12.5, end=15, text="  Hello   world! "),
    ]
    target = tmp_path / "captions.srt"
    _write_srt(
        {"segments": segments, "start": 10, "end": 40},
        target,
    )

    assert target.read_text(encoding="utf-8") == (
        "1\n00:00:02,500 --> 00:00:05,000\nHello world!\n"
    )


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is required")
def test_process_media_renders_vertical_video_with_transcript(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-y",
            "-f", "lavfi",
            "-i", "testsrc=size=320x240:rate=25:duration=4",
            "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=4",
            "-shortest",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-c:a", "aac",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    whisper = ModuleType("faster_whisper")

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            return iter(
                [SimpleNamespace(start=0.25, end=3.5, text="Wait! That is an amazing play.")]
            ), SimpleNamespace(language="en")

    whisper.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", whisper)

    result = process_media(
        source_path=source,
        job_id="test-job",
        output_dir=tmp_path / "clips",
        language="auto",
        layout="crop",
        caption_style="minimal",
        max_seconds=60,
        update=lambda progress, phase: None,
    )

    assert len(result) == 1
    rendered = Path(result[0]["file_path"])
    probe = subprocess.run(
        [
            shutil.which("ffprobe"),
            "-v", "error",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(rendered),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    dimensions = json.loads(probe.stdout)["streams"][0]
    assert (dimensions["width"], dimensions["height"]) == (1080, 1920)
    assert "amazing play" in rendered.with_suffix(".srt").read_text(encoding="utf-8")
