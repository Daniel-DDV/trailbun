"""Render the README demo GIF and its final frame from a retained `trailbun demo` receipt.

The frames show the same text that `trailbun demo` prints (see trailbun.cli.render),
so the GIF and the command match. Two beats: the check that reports the detour, then
the receipt. Requires FFmpeg with drawtext and an explicitly supplied monospace font.
Source: https://ffmpeg.org/ffmpeg-filters.html#drawtext
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trailbun.cli import render  # noqa: E402

WIDTH, HEIGHT, FPS = 1200, 600, 10
BEATS = ((0.0, 4.0), (4.0, 8.0))  # seconds
FONT_SIZE, LINE_HEIGHT, MARGIN = 34, 48, 48
INK, ACCENT, CANVAS = "0xF4EDDE", "0xD2ED73", "0x291F30"


def screens(data):
    if data.get("kind") != "deterministic-demonstration" or data.get("agent_run") is not False:
        raise ValueError("Expected an actual deterministic demo receipt.")
    steps = {step["event"]: step for step in data["steps"]}
    check = render("check", steps["detect-detour"]).splitlines()
    receipt = render("verify", steps["verify-result"]).splitlines()
    first = ["$ trailbun check", *check[:5]]
    # The receipt path is useful in a terminal and noise in a 1200-pixel frame.
    second = ["$ trailbun verify", *(line.split("  <")[0] for line in receipt[:4])]
    return [first, second]


def drawtext(index, number, line, start, end, color):
    return (f"drawtext=fontfile=mono.ttf:textfile={index}-{number}.txt:expansion=none:fontcolor={color}"
            f":fontsize={FONT_SIZE}:x={MARGIN}:y={MARGIN + number * LINE_HEIGHT}:enable='gte(t,{start})*lt(t,{end})'")


def build(receipt, output, final, font):
    data = json.loads(receipt.read_text(encoding="utf-8"))
    output, final = output.resolve(), final.resolve()
    with tempfile.TemporaryDirectory(prefix="trailbun-render-") as temporary:
        root = Path(temporary)
        shutil.copyfile(font, root / "mono.ttf")
        filters = []
        for index, (screen, (start, end)) in enumerate(zip(screens(data), BEATS, strict=True)):
            lines = [wrapped for line in screen for wrapped in (textwrap.wrap(line, width=52) or [""])]
            if len(lines) * LINE_HEIGHT + 2 * MARGIN > HEIGHT - 60:
                raise ValueError("Demo screen exceeds available height.")
            for number, line in enumerate(lines):
                if not line.strip():
                    continue
                (root / f"{index}-{number}.txt").write_text(line, encoding="utf-8")
                color = ACCENT if ("VIOLATION" in line or "outside scope:" in line and "none" not in line
                                   or line.startswith("  receipt")) else INK
                filters.append(drawtext(index, number, line, start, end, color))
        (root / "footer.txt").write_text("DETERMINISTIC DEMO  /  NO LIVE MODEL  /  REPLAY: trailbun demo", encoding="utf-8")
        filters.append(f"drawtext=fontfile=mono.ttf:textfile=footer.txt:fontcolor={ACCENT}:fontsize=20:x={MARGIN}:y={HEIGHT - 44}")
        duration = BEATS[-1][1]
        graph = ",".join(filters)
        base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                "-i", f"color=c={CANVAS}:s={WIDTH}x{HEIGHT}:r={FPS}:d={duration}"]
        subprocess.run([*base, "-filter_complex", graph + ",split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=none",
                        "-loop", "0", str(output)], cwd=root, check=True)
        subprocess.run([*base, "-filter_complex", graph, "-ss", str(duration - 0.2), "-frames:v", "1", str(final)],
                       cwd=root, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("output", type=Path, help="GIF path")
    parser.add_argument("--final", type=Path, required=True, help="PNG path for the static final frame")
    parser.add_argument("--font", required=True, type=Path)
    args = parser.parse_args()
    build(args.receipt, args.output, args.final, args.font)
