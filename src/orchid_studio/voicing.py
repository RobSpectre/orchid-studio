"""The researched Orchid chord-voicing setter only; no general hardware output API."""
from .midi import backend, exact_port
from .sequencer import integer


def chord_voicing_packet(value):
    # Research CLI protocol.voicing_packet('chord', value): vendor command 0x45.
    # This is not outgoing CC115; that dial report is not an incoming setter.
    body = [0x00, 0x22, 0x0C, 0x01, 0x45, integer(value, 1, 60, 'voicing value')]
    return [0xF0, *body, (-sum(body)) & 0x7F, 0xF7]


def set_chord_voicing(value, output='Orchid'):
    message = chord_voicing_packet(value)
    if not isinstance(output, str) or not output.strip() or 'orchid' not in output.lower() or output.startswith('Orchid Studio'):
        raise ValueError('output must be an exact Orchid hardware MIDI port name')
    port = backend().MidiOut()
    try:
        port.open_port(exact_port(port.get_ports(), output))
        port.send_message(message)
        return {'value': value, 'output': output, 'confirmed': False,
                'evidence': 'sent; not a hardware readback'}
    finally:
        try:
            port.close_port()
        finally:
            port.delete()
