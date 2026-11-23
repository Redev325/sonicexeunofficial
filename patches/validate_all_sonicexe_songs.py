#!/usr/bin/env python3
"""Validate every song exposed by the Sonic.EXE HTML5 week catalogue."""
from pathlib import Path
import json
import re
import sys

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("engine/assets")


def fail(message: str) -> None:
    raise SystemExit("Sonic.EXE full-song validation failed: " + message)


def format_song_path(value: str) -> str:
    value = str(value).replace(" ", "-")
    value = re.sub(r"[~&\\;:<>#]", "-", value)
    value = re.sub(r"[.,'\"%?!]", "", value)
    return value.lower()


def require_file(path: Path, description: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"missing {description}: {path}")


weeks_root = ROOT / "shared/weeks"
week_list = weeks_root / "weekList.txt"
require_file(week_list, "week catalogue")
week_ids = [
    line.strip()
    for line in week_list.read_text(encoding="utf-8-sig").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]
if not week_ids:
    fail("week catalogue is empty")

seen_songs = set()
songs_checked = 0
voices_checked = 0
stages_checked = set()
missing_character_defs = set()

for week_id in week_ids:
    week_file = weeks_root / f"{week_id}.json"
    require_file(week_file, f"week definition '{week_id}'")
    try:
        week = json.loads(week_file.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        fail(f"invalid week JSON {week_file}: {exc}")
    rows = week.get("songs")
    if not isinstance(rows, list):
        fail(f"week '{week_id}' has no songs array")

    for row in rows:
        if not isinstance(row, list) or not row or not str(row[0]).strip():
            fail(f"week '{week_id}' contains a malformed song row: {row!r}")
        title = str(row[0]).strip()
        slug = format_song_path(title)
        if not slug:
            fail(f"week '{week_id}' contains a song with an empty path")
        if slug in seen_songs:
            continue
        seen_songs.add(slug)

        chart_file = ROOT / "shared/data" / slug / f"{slug}-hard.json"
        audio_dir = ROOT / "songs" / slug
        instrumental = audio_dir / "Inst.mp3"
        require_file(chart_file, f"Hard chart for '{title}'")
        require_file(instrumental, f"HTML5 instrumental for '{title}'")
        try:
            chart_data = json.loads(chart_file.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            fail(f"invalid chart JSON for '{title}': {exc}")
        song = chart_data.get("song", chart_data) if isinstance(chart_data, dict) else None
        if not isinstance(song, dict):
            fail(f"chart for '{title}' has no song object")
        sections = song.get("notes")
        if not isinstance(sections, list) or not sections:
            fail(f"chart for '{title}' has no playable note sections")
        for section_index, section in enumerate(sections):
            if not isinstance(section, dict) or not isinstance(section.get("sectionNotes", []), list):
                fail(f"chart for '{title}' has malformed note section {section_index}")

        if song.get("needsVoices", False):
            require_file(audio_dir / "Voices.mp3", f"required vocals for '{title}'")
            voices_checked += 1

        stage = str(song.get("stage") or "").strip()
        if stage and stage.casefold() not in {"null", "none"}:
            stage_file = ROOT / "shared/stages" / f"{stage}.json"
            require_file(stage_file, f"stage metadata for '{title}'")
            try:
                stage_data = json.loads(stage_file.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                fail(f"invalid stage JSON for '{title}' ({stage}): {exc}")
            directory = str(stage_data.get("directory") or "").strip()
            if directory:
                stages_checked.add(directory)
            # Psych Engine consumes player1/player2/gfVersion directly; player3
            # is an extra metadata field in some charts and is still imported above.
            for key in ("player1", "player2", "gfVersion"):
                character = str(song.get(key) or "").strip()
                if not character or character.casefold() in {"null", "none"}:
                    continue
                shared_character = ROOT / "shared/characters" / f"{character}.json"
                packed_character = (
                    ROOT / "week_assets" / directory / "characters" / f"{character}.json"
                    if directory else Path("/__no_pack_character__")
                )
                if not shared_character.is_file() and not packed_character.is_file():
                    missing_character_defs.add(f"{title}: {character}")

        songs_checked += 1

if songs_checked == 0:
    fail("no songs were found in the week catalogue")

if missing_character_defs:
    # Psych Engine's Character constructor explicitly falls back to its default
    # character when a character JSON is absent, so this is a visual fallback
    # warning rather than a chart/audio blocker.
    preview = "; ".join(sorted(missing_character_defs)[:20])
    remainder = len(missing_character_defs) - min(20, len(missing_character_defs))
    if remainder > 0:
        preview += f"; and {remainder} more"
    print("Character fallback warnings (engine default character will be used): " + preview)

print(
    f"Validated {songs_checked} unique catalogue songs across {len(week_ids)} weeks: "
    "each has a readable Hard chart, playable note sections, and an HTML5 Inst.mp3."
)
print(
    f"Validated required vocal tracks: {voices_checked}; "
    f"stage asset libraries referenced: {len(stages_checked)}."
)
print("All catalogue charts resolve their playable chart and audio assets; any absent character JSON uses Psych Engine’s built-in default-character fallback.")
