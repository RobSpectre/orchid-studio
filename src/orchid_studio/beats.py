"""Original 12-bar electronic arrangements for synthesized TR-808 sounds (CC0 patterns)."""
BANK_NAME = "Orchid Studio — Electronic Vol. 1"
KIT_NAME = "TR808EmulationKit"
# ID, name, genre, suggested BPM, kick offsets in a two-bar phrase.
_SPECS = (
    ("liquid-circuit", "Liquid Circuit", "drum-and-bass", 172, (0, 1.75, 2.5, 4, 5.5, 6.75)),
    ("neon-breaks", "Neon Breaks", "drum-and-bass", 174, (0, .75, 2.5, 3.75, 4, 6.25)),
    ("subway-steps", "Subway Steps", "drum-and-bass", 170, (0, 2.5, 4, 4.75, 6.5, 7.75)),
    ("night-runner", "Night Runner", "drum-and-bass", 176, (0, 1.5, 2.75, 4, 5.75, 6.5)),
    ("velvet-floor", "Velvet Floor", "house", 122, tuple(range(8))),
    ("glass-house", "Glass House", "house", 124, tuple(range(8))),
    ("after-hours", "After Hours", "house", 126, tuple(range(8))),
    ("warehouse-glow", "Warehouse Glow", "house", 128, tuple(range(8))),
    ("aurora-drive", "Aurora Drive", "trance", 132, tuple(range(8))),
    ("prism-lift", "Prism Lift", "trance", 136, tuple(range(8))),
    ("orbital-pulse", "Orbital Pulse", "trance", 138, tuple(range(8))),
    ("daybreak-rush", "Daybreak Rush", "trance", 140, tuple(range(8))),
)


def catalog():
    return [{"id": s[0], "name": s[1], "genre": s[2], "suggested_bpm": s[3],
             "pattern": i, "length_beats": 48, "bars": 12, "kit": KIT_NAME,
             "feel": {"drum-and-bass": "syncopated electronic breaks", "house": "four-on-the-floor",
                      "trance": "driving sixteenth-note pulse"}[s[2]]}
            for i, s in enumerate(_SPECS)]


def get_beat(identifier):
    if not isinstance(identifier, str):
        raise ValueError("beat must be a catalog ID")
    for beat in catalog():
        if beat["id"] == identifier:
            return beat
    raise ValueError("unknown beat; use beats-list for available IDs")


def patterns():
    result = []
    for index, (_, name, genre, bpm, kicks) in enumerate(_SPECS):
        base = {}
        def hit(voice, beat, velocity, late=0, pan=0):
            position = max(0, min(383, round(beat * 48) + late))
            base[(position, voice)] = {"instrument": voice, "position": position,
                                       "velocity": round(velocity, 3), "pan": pan}
        kick = "Kick Short" if genre == "drum-and-bass" else "Kick Long"
        for i, beat in enumerate(kicks):
            hit(kick, beat, .78 if beat in (0, 4) else .65 + .025 * (i % 3))
        for beat in (1, 3, 5, 7):
            hit("Snare 1" if genre == "drum-and-bass" else "Clap", beat, .62)
            if genre == "trance":
                hit("Snare 2", beat, .32)
        if genre == "drum-and-bass":
            for beat in (.75, 2.75, 4.75, 6.75):
                hit("Snare 2", beat + (index % 2) * .25, .23 + .025 * (index % 3))
        hat_step = .25 if genre == "trance" or index % 2 else .5
        for i in range(round(8 / hat_step)):
            # Distinguish trance grooves with hat spacing, without tuned accents.
            if genre == "trance":
                rests = ((), (3, 11, 19, 27), (1, 3, 9, 11, 17, 19, 25, 27), (7, 15, 23, 31))[index % 4]
                if i in rests:
                    continue
            beat = i * hat_step
            late = (index % 3 + 1) if genre == "house" and i % 2 else 0
            hit("Closed Hat", beat, (.34, .18, .27, .21)[i % 4], late=late, pan=-.1)
        for beat in ((1.5, 3.5, 5.5, 7.5) if genre == "drum-and-bass" else tuple(i + .5 for i in range(8))):
            hit("Open Hat", beat, .26 if genre == "drum-and-bass" else .37, pan=.1)
        arrangement = {}
        for phrase in range(6):
            # 2-bar intro, core, variation, lift, 2-bar drop, 2-bar return/fill.
            for source in base.values():
                local, voice = source["position"], source["instrument"]
                if phrase == 0 and (voice == "Open Hat" or
                                    (voice == "Closed Hat" and local % 48 > 12)):
                    continue
                if phrase == 4 and local < 192 and voice not in (kick, "Snare 1", "Clap"):
                    continue
                note = {**source, "position": phrase * 384 + local}
                note["velocity"] = round(source["velocity"] * (.88 if phrase in (0, 4) else 1), 3)
                arrangement[(note["position"], voice)] = note
            if phrase in (2, 5) and genre == "drum-and-bass":
                position = phrase * 384 + 324 + index % 3 * 6
                arrangement[(position, kick)] = {"position": position, "instrument": kick,
                                                "velocity": .58, "pan": 0}
            if phrase in (3, 5):
                # Two quiet sixteenth-grid taps replace tuned toms and busy rolls.
                for j, position in enumerate((360, 372)):
                    voice = "Snare 2"
                    absolute = phrase * 384 + position
                    arrangement[(absolute, voice)] = {"position": absolute, "instrument": voice,
                                                       "velocity": (.16, .20)[j], "pan": 0}
        result.append({"name": name, "size": 2304, "category": "Orchid Studio " + genre,
                       "info": f"Original 12-bar {genre} arrangement; synthesized 808 core drums, restrained fills, no tuned accents; suggested {bpm} BPM",
                       "notes": sorted(arrangement.values(), key=lambda h: (h["position"], h["instrument"]))})
    return result
