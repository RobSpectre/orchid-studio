"""Readable sound and Perform maps; no MIDI or plugin access."""
import json
from importlib.resources import files

CLASSIC={
 'off':('Chord','Play held notes together; no generated rhythm.'),
 'strum':('Strum','Sweep upward across held chord notes over spread_beats; sustain until release.'),
 'strum2':('Strum 2','Upward strum across the chord plus an octave above.'),
 'slop':('Slop','A strum with seeded timing variation; slop controls looseness.'),
 'arp':('Arp','Cycle upward through held notes at the note division; gate controls length.'),
 'arp2':('Arp 2','Cycle upward through chord notes across two octaves.'),
 'pattern':('Pattern','Apply the selected repeating four-beat rhythm to held chord notes.'),
 'harp':('Harp','One upward sweep over harp_octaves; each note has a short gated lifetime.'),
}
PATTERN_DESCRIPTIONS={
 'pulse':'Full chord on each beat.', 'offbeat':'Full chord on every offbeat eighth.',
 'backbeat':'Lowest note on beats 1 and 3, full chord on 2 and 4.',
 'tresillo':'Full chord with a 3–3–2 eighth-note grouping.',
 'shuffle':'Swing pairs in triplet timing, moving through chord notes.',
 'rising':'Ascending chord tones on eighth notes.',
 'falling':'Descending chord tones on eighth notes.',
 'pendulum':'Back-and-forth chord-tone sequence on eighth notes.',
}


def sounds():
    return json.loads(files('orchid_studio').joinpath('sound_catalog.json').read_text())


def perform_map(modes, melodies):
    result={}
    for mode in modes:
        if mode in CLASSIC:
            label,description=CLASSIC[mode]
            result[mode]={'label':label,'description':description,'bank':'classic'}
        else:
            m=melodies[mode]
            result[mode]={'label':m.get('label',mode.title()),'title':m.get('title',mode.title()),
                         'description':m['description'],'bank':m.get('bank','melodies'),
                         'harmony':m['harmony'],'phrase_units':m.get('phrase_units',32),
                         'trigger':'Hold note/chord; release stops (sustain applies)',
                         'pitch_rule':'C4 reproduces source; other keys transpose' if 'source_file' in m else 'Lowest held note is root; chord third chooses major/minor'}
    return result
