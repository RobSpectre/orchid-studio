"""Generate an original Hydrogen pattern song using an installed kit's metadata.

Sample audio stays in Hydrogen's own kit directory; it is never copied here.
"""

import copy
from pathlib import Path
import xml.etree.ElementTree as ET

from .sequencer import number


def write_song(destination, kit_directory, bpm, title, pattern_data):
    number(bpm, 30, 300, "bpm")
    kit = ET.parse(Path(kit_directory) / "drumkit.xml").getroot()
    for node in kit.iter():
        node.tag = node.tag.split("}")[-1]
    kit_name = kit.findtext("name")
    instruments = kit.find("instrumentList")
    if not kit_name or instruments is None:
        raise ValueError("invalid Hydrogen drumkit metadata")
    ids = {i.findtext("name"): i.findtext("id") for i in instruments}
    required = {n["instrument"] for p in pattern_data for n in p["notes"]}
    if not required <= ids.keys():
        raise ValueError("kit is missing instruments: " + ", ".join(sorted(required - ids.keys())))

    def add(parent, name, value):
        ET.SubElement(parent, name).text = str(value)

    song = ET.Element("song")
    for key, value in {
        "version": "1.2.0", "bpm": bpm, "volume": 0.3,
        "metronomeVolume": 0, "name": title,
        "author": "Orchid Studio", "notes": "Original patterns. Samples remain in the installed Hydrogen kit.",
        "license": "Pattern data: CC0; drumkit samples retain their original license.",
        "loopEnabled": "true", "patternModeMode": "true", "mode": "pattern",
        "humanize_time": 0, "humanize_velocity": 0, "swing_factor": 0,
        "isMuted": "false", "playbackTrackFilename": "", "playbackTrackEnabled": "false",
        "playbackTrackVolume": 0, "action_mode": 0, "pan_law_type": "RATIO_STRAIGHT_POLYGONAL",
        "pan_law_k_norm": 1.33333,
    }.items():
        add(song, key, value)
    components = kit.find("componentList")
    if components is not None:
        song.append(copy.deepcopy(components))
    instrument_list = copy.deepcopy(instruments)
    for instrument in instrument_list:
        add(instrument, "drumkit", kit_name)
        add(instrument, "drumkitLookup", 2)
        midi_out = instrument.find("midiOutChannel")
        if midi_out is None:
            add(instrument, "midiOutChannel", -1)
        else:
            midi_out.text = "-1"
    song.append(instrument_list)
    patterns = ET.SubElement(song, "patternList")
    for data in pattern_data:
        pattern = ET.SubElement(patterns, "pattern")
        for key, value in {"name": data["name"], "size": data["size"], "denominator": 4,
                           "category": data["category"], "info": data["info"]}.items():
            add(pattern, key, value)
        notes = ET.SubElement(pattern, "noteList")
        for hit in data["notes"]:
            note = ET.SubElement(notes, "note")
            for key, value in {"position": hit["position"], "leadlag": 0,
                               "velocity": hit["velocity"], "pan": hit.get("pan", 0),
                               "pitch": 0, "probability": 1, "key": "C0", "length": -1,
                               "instrument": ids[hit["instrument"]], "note_off": "false"}.items():
                add(note, key, value)
    sequence = ET.SubElement(song, "patternSequence")
    for _ in range(4):
        add(ET.SubElement(sequence, "group"), "patternID", pattern_data[0]["name"])
    for tag in ("virtualPatternList", "ladspa", "BPMTimeLine", "tagTimeLine"):
        ET.SubElement(song, tag)
    ET.indent(song, space=" ")
    destination = Path(destination)
    with destination.open("xb") as handle:
        ET.ElementTree(song).write(handle, encoding="utf-8", xml_declaration=True)
    return {"status": "written", "path": str(destination.resolve()), "kit": kit_name,
            "patterns": [p["name"] for p in pattern_data], "samples_copied": False}


def write_demo_song(destination, kit_directory, bpm=96):
    patterns = []
    for name, kicks, snares in (("Studio Groove", (0, 2), (1, 3)),
                                ("Studio Variation", (0, 1.5, 2.5), (1, 3, 3.75))):
        notes = [{"instrument": instrument, "position": round(beat * 48), "velocity": velocity}
                 for instrument, beats, velocity in (("Kick", kicks, .7), ("Snare", snares, .55),
                    ("Hat Closed", [i / 2 for i in range(8)], .35)) for beat in beats]
        patterns.append({"name": name, "size": 192, "category": "Orchid Studio",
                         "info": "Original four-beat loop", "notes": notes})
    return write_song(destination, kit_directory, bpm, "Orchid Studio — First Groove", patterns)


def write_electronic_song(destination, kit_directory, bpm=124):
    from .beats import BANK_NAME, patterns
    return write_song(destination, kit_directory, bpm, BANK_NAME, patterns())


def validate_beat_bank(path):
    from .beats import BANK_NAME, catalog
    path = Path(path).expanduser().resolve()
    if path.suffix != ".h2song" or not path.is_file():
        raise ValueError("bank must be an existing .h2song file")
    try:
        song = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError("invalid Hydrogen song XML") from exc
    actual = [(p.findtext("name"), p.findtext("size")) for p in song.findall("patternList/pattern")]
    expected = [(b["name"], "2304") for b in catalog()]
    if song.findtext("name") != BANK_NAME or actual != expected:
        raise ValueError("song is not the ordered 12-arrangement Orchid Studio electronic bank")
    return str(path)
