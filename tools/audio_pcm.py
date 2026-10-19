"""PCM WAV handling and reproducible local game-cue preparation (Python 3.12)."""
import io
import struct
import warnings
import wave


def read_pcm(path):
    raw = path.read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("Expected a PCM RIFF WAV source")
    offset = 12
    format_data = None
    samples = None
    while offset+8 <= len(raw):
        kind, length = struct.unpack_from("<4sI", raw, offset)
        block = raw[offset+8:offset+8+length]
        if len(block) != length:
            raise ValueError("Truncated WAV chunk")
        if kind == b"fmt ":
            format_data = block
        elif kind == b"data":
            samples = block
        offset += 8+length+length%2
    if format_data is None or samples is None:
        raise ValueError("WAV has no format or sample data")
    tag, channels, rate, _, align, bits = struct.unpack_from("<HHIIHH", format_data)
    if tag == 65534 and len(format_data) >= 40:
        tag = struct.unpack_from("<H", format_data, 24)[0]
    if tag != 1 or channels not in (1,2) or bits not in (16,24,32) or align != channels*bits//8:
        raise ValueError("Expected mono/stereo integer PCM WAV")
    if len(samples)%align:
        raise ValueError("PCM frame data is incomplete")
    return samples, channels, bits//8, rate


def mono48(path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import audioop
    data, channels, width, rate = read_pcm(path)
    if channels == 2:
        data = audioop.tomono(data,width,.5,.5)
    if width != 2:
        data = audioop.lin2lin(data,width,2)
    if rate != 48000:
        data,_ = audioop.ratecv(data,2,1,rate,48000,None)
    return data


def wav_bytes(data, channels=1, width=2, rate=48000):
    output = io.BytesIO()
    with wave.open(output,"wb") as writer:
        writer.setparams((channels,width,rate,0,"NONE","not compressed"))
        writer.writeframes(data)
    return output.getvalue()
