import re
import json
import os
from pathlib import Path

SONGDATA_FILE = "songdata.json"


def load_existing_songs():
    """Safely load existing songs from JSON."""
    if os.path.exists(SONGDATA_FILE):
        try:
            with open(SONGDATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except json.JSONDecodeError:
            pass
    return {}


def parse_song_entry(lines, author=None):
    """Parse a single song entry block into a dictionary."""
    header = lines[0].strip()
    header_match = re.match(
        r"\[\s*([^\-]+?)\s*-\s*([^\-\]]+?)\s*(?:-\s*([^\]]+))?\]:\s*(.+)", header
    )
    if not header_match:
        raise ValueError(f"Could not parse header from: {header}")

    main_bpm = header_match.group(1).strip()
    main_key = header_match.group(2).strip()
    extra = header_match.group(3)
    song_name = header_match.group(4).strip()

    # Normalize main key
    if main_key == "/":
        main_key = None
    elif main_key == "?":
        main_key = "?"

    time_signature = extra.strip() if extra and "/" in extra else None

    changes = []
    for line in lines[1:]:
        line = line.strip()
        change_match = re.match(r">\s*([\d:]+)\s*:\s*(.+)", line)
        if change_match:
            time_str = change_match.group(1)
            value = change_match.group(2).strip()

            # Detect BPM
            bpm_match = re.match(r"~?(\d+(\.\d+)?)", value)
            if bpm_match:
                bpm_value = float(bpm_match.group(1))
                changes.append({"time": time_str, "bpm": bpm_value})
            else:
                # Treat everything else as key change
                key_change = value
                if key_change == "/":
                    key_change = None
                elif key_change == "?":
                    key_change = "?"
                changes.append({"time": time_str, "key": key_change})

    song_data = {"bpm": main_bpm, "key": main_key}
    if time_signature:
        song_data["time_signature"] = time_signature
    if changes:
        song_data["changes"] = changes
    if author:
        song_data["author"] = author

    return song_name, song_data


def parse_song_list(raw_text):
    """Parse multiple songs from raw text input with authors."""
    lines = raw_text.strip().splitlines()
    songs = {}
    buffer = []
    current_author = None

    for i, line in enumerate(lines):
        line = line.strip()

        if i % 50 == 0:
            print(f"Processing line {i}/{len(lines)}")

        # Detect author lines (dashed separators)
        author_match = re.match(r"-{5,}\s*(.+?)\s*-{5,}", line)
        if author_match:
            # Flush previous song before changing author
            if buffer:
                try:
                    name, data = parse_song_entry(buffer, current_author)
                    songs[name] = data
                except Exception as e:
                    print(f"Error parsing song: {buffer[0]} -> {e}")
                buffer = []
            current_author = author_match.group(1).strip()
            continue

        # Detect new song entry
        if re.match(r"\[\s*.*?\s*-\s*.*?\s*(?:-\s*.*)?\]:", line):
            if buffer:
                try:
                    name, data = parse_song_entry(buffer, current_author)
                    songs[name] = data
                except Exception as e:
                    print(f"Error parsing song: {buffer[0]} -> {e}")
            buffer = [line]
        elif line:
            buffer.append(line)

    # Process last song
    if buffer:
        try:
            name, data = parse_song_entry(buffer, current_author)
            songs[name] = data
        except Exception as e:
            print(f"Error parsing song: {buffer[0]} -> {e}")

    return songs



if __name__ == "__main__":
    # replace the filenames here!!!
    with Path("GD.txt").open(encoding="utf-8") as f:
        gd_keychart = f.read()
    with Path("HITS + OTHER.txt").open(encoding="utf-8") as f:
        hits_keychart = f.read()
    raw_input_text = gd_keychart + hits_keychart

    print("Parsing songs...")
    new_songs = parse_song_list(raw_input_text)
    print(f"Parsed {len(new_songs)} new songs.")

    # Load existing songs safely
    existing_songs = load_existing_songs()

    # Merge new songs (overwrite duplicates)
    existing_songs.update(new_songs)

    # Save back to JSON
    with open(SONGDATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_songs, f, indent=4, ensure_ascii=False)

    print(f"Saved {len(existing_songs)} total songs to {SONGDATA_FILE}")
