#!/Users/wangtingwei/.venvs/whisper/bin/python
"""whisper_cli.py — drop-in CLI shim for auto_update.py's transcribe().

The historical pipeline shelled out to the `openai-whisper` CLI. That install
broke (numba fails to initialize under the x86_64/Rosetta anaconda Python on
this arm64 machine). This shim reproduces the *exact* subset of the openai-
whisper command line that auto_update.py uses, but is backed by faster-whisper
(CTranslate2) running on a native arm64 venv (~/.venvs/whisper) — no numba, no
torch.

auto_update.py invokes:
    <bin> <audio> --model small --language Chinese --task transcribe \
          --output_dir <dir> --output_format txt --fp16 False --verbose False

and then reads "<output_dir>/<audio-stem>.txt". We honor that contract:
write "<output_dir>/<stem>.<ext>" for txt/srt/vtt (txt is what the pipeline
reads). Unknown flags are accepted and ignored so future flag additions on the
caller side don't crash the shim.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

# openai-whisper accepts language names ("Chinese"); faster-whisper wants ISO
# codes ("zh"). Map the names auto_update.py might pass; fall back to lowercase.
_LANG = {
    "chinese": "zh", "zh": "zh",
    "english": "en", "en": "en",
    "japanese": "ja", "ja": "ja",
}


def _fmt_ts(seconds: float) -> str:
    """HH:MM:SS.mmm for srt/vtt."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("audio", help="path to audio file")
    ap.add_argument("--model", default="small")
    ap.add_argument("--language", default=None)
    ap.add_argument("--task", default="transcribe", choices=["transcribe", "translate"])
    ap.add_argument("--output_dir", default=".")
    ap.add_argument("--output_format", default="txt",
                    choices=["txt", "srt", "vtt", "all"])
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--compute_type", default="int8")
    ap.add_argument("--beam_size", type=int, default=5)
    # Accepted-and-ignored openai-whisper flags so the caller's command line
    # (which passes these) does not error.
    ap.add_argument("--fp16", default=None)
    ap.add_argument("--verbose", default=None)
    args, _unknown = ap.parse_known_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"[whisper_cli] audio not found: {audio_path}", file=sys.stderr)
        return 2

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = audio_path.stem

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        print(f"[whisper_cli] faster-whisper not installed in this interpreter: {e}",
              file=sys.stderr)
        return 3

    lang = None
    if args.language:
        lang = _LANG.get(args.language.strip().lower(), args.language.strip().lower())

    print(f"[whisper_cli] loading model={args.model} device={args.device} "
          f"compute_type={args.compute_type} …", flush=True)
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)

    print(f"[whisper_cli] transcribing {audio_path.name} (lang={lang or 'auto'}) …",
          flush=True)
    segments, info = model.transcribe(
        str(audio_path),
        language=lang,
        task=args.task,
        beam_size=args.beam_size,
        vad_filter=True,
    )

    # faster-whisper returns a lazy generator; materialize once.
    seg_list = []
    for seg in segments:
        seg_list.append((seg.start, seg.end, seg.text.strip()))
        # progress heartbeat every ~50 segments so the launchd log shows life
        if len(seg_list) % 50 == 0:
            print(f"[whisper_cli]   …{len(seg_list)} segments "
                  f"(t={_fmt_ts(seg.end)})", flush=True)

    formats = ["txt", "srt", "vtt"] if args.output_format == "all" else [args.output_format]

    if "txt" in formats:
        txt = "\n".join(t for _, _, t in seg_list if t) + "\n"
        (out_dir / f"{stem}.txt").write_text(txt, encoding="utf-8")
    if "srt" in formats:
        lines = []
        for i, (st, en, t) in enumerate(seg_list, 1):
            lines.append(f"{i}\n{_fmt_ts(st).replace('.', ',')} --> "
                         f"{_fmt_ts(en).replace('.', ',')}\n{t}\n")
        (out_dir / f"{stem}.srt").write_text("\n".join(lines), encoding="utf-8")
    if "vtt" in formats:
        lines = ["WEBVTT", ""]
        for st, en, t in seg_list:
            lines.append(f"{_fmt_ts(st)} --> {_fmt_ts(en)}\n{t}\n")
        (out_dir / f"{stem}.vtt").write_text("\n".join(lines), encoding="utf-8")

    total_chars = sum(len(t) for _, _, t in seg_list)
    print(f"[whisper_cli] done: {len(seg_list)} segments, {total_chars} chars "
          f"→ {out_dir / (stem + '.txt')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
