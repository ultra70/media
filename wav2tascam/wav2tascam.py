#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""wav2tascam - Convert WAV files to Tascam Model series compatible format.

Tascam Model 12/16/24 will not import WAV files that use the
WAVE_FORMAT_EXTENSIBLE (0xFFFE) header, which is the default output
of ffmpeg and SoX for 24-bit audio.  This script rewrites the WAV
header to use the standard PCM format tag (0x0001) that the Tascam
firmware requires.  Sample rate, bit depth, and channel layout are
preserved from the source file.

This script is not required for 16-bit WAV files.  ffmpeg and SoX only
default to WAVE_FORMAT_EXTENSIBLE for bit depths above 16.  A 16-bit
WAV already uses format tag 0x0001 and imports to Tascam Model 12/16/24
without conversion.

"""

import argparse
import os
import struct
import sys

VERSION = "2.0.0"

WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

KSDATAFORMAT_SUBTYPE_PCM = (
    b"\x01\x00\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
)


def die(msg):
    print(f"wav2tascam: error: {msg}", file=sys.stderr)
    sys.exit(1)


def read_chunks(f):
    """Yield (chunk_id, chunk_data) pairs from a RIFF WAV file."""
    riff_id = f.read(4)
    if riff_id != b"RIFF":
        die("not a valid WAV file (missing RIFF header)")

    riff_size = struct.unpack("<I", f.read(4))[0]
    wave_id = f.read(4)
    if wave_id != b"WAVE":
        die("not a valid WAV file (missing WAVE identifier)")

    bytes_read = 0
    while bytes_read < riff_size - 4:
        chunk_id = f.read(4)
        if len(chunk_id) < 4:
            break

        chunk_size = struct.unpack("<I", f.read(4))[0]
        chunk_data = f.read(chunk_size)

        # WAV chunks are word-aligned; skip padding byte if odd size.
        if chunk_size % 2 != 0:
            pad = f.read(1)
            bytes_read += 1

        bytes_read += 8 + chunk_size
        yield chunk_id, chunk_data


def parse_fmt(fmt_data):
    """Parse a fmt chunk and return audio properties."""
    if len(fmt_data) < 16:
        die("fmt chunk too short")

    format_tag, channels, sample_rate, byte_rate, block_align, bits_per_sample = (
        struct.unpack("<HHIIHH", fmt_data[:16])
    )

    if format_tag == WAVE_FORMAT_PCM:
        pass
    elif format_tag == WAVE_FORMAT_EXTENSIBLE:
        if len(fmt_data) < 40:
            die("WAVE_FORMAT_EXTENSIBLE fmt chunk too short")

        cb_size = struct.unpack("<H", fmt_data[16:18])[0]
        if cb_size < 22:
            die(f"unexpected cbSize in extensible format: {cb_size}")

        valid_bits = struct.unpack("<H", fmt_data[18:20])[0]
        subformat = fmt_data[24:40]

        if subformat != KSDATAFORMAT_SUBTYPE_PCM:
            die("input is not PCM audio (unsupported subformat GUID)")

        if valid_bits > 0:
            bits_per_sample = valid_bits
    else:
        die(f"unsupported WAV format tag: 0x{format_tag:04X}")

    return {
        "channels": channels,
        "sample_rate": sample_rate,
        "bits_per_sample": bits_per_sample,
    }


def write_pcm_wav(output_path, raw_data, channels, sample_rate, bits_per_sample):
    """Write a standard PCM WAV file with format tag 0x0001."""
    block_align = channels * (bits_per_sample // 8)
    byte_rate = sample_rate * block_align
    data_size = len(raw_data)

    with open(output_path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVEfmt ")
        f.write(struct.pack("<I", 16))
        f.write(struct.pack("<H", WAVE_FORMAT_PCM))
        f.write(struct.pack("<H", channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(raw_data)


def convert(input_path, output_path):
    """Read a WAV file and write a Tascam-compatible copy."""
    fmt_info = None
    raw_data = None

    with open(input_path, "rb") as f:
        for chunk_id, chunk_data in read_chunks(f):
            if chunk_id == b"fmt ":
                fmt_info = parse_fmt(chunk_data)
            elif chunk_id == b"data":
                raw_data = chunk_data

    if fmt_info is None:
        die("no fmt chunk found in input file")
    if raw_data is None:
        die("no data chunk found in input file")
    if len(raw_data) == 0:
        die("data chunk is empty")

    ch = fmt_info["channels"]
    sr = fmt_info["sample_rate"]
    bps = fmt_info["bits_per_sample"]
    ch_label = "mono" if ch == 1 else "stereo" if ch == 2 else f"{ch}ch"

    print(f"Converting: {input_path}")
    print(f"Output:     {output_path}")
    print(f"Format:     {bps}-bit / {sr} Hz / {ch_label}")

    write_pcm_wav(output_path, raw_data, ch, sr, bps)

    size = os.path.getsize(output_path)
    print(f"Done:       {output_path} ({size} bytes)")


def main():
    parser = argparse.ArgumentParser(
        prog="wav2tascam",
        description="Convert WAV files to Tascam Model series compatible format.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    parser.add_argument(
        "input",
        help="input WAV file",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="output WAV file (default: <input_basename>_tascam.wav)",
    )

    args = parser.parse_args()

    input_path = args.input
    output_path = args.output

    if not os.path.isfile(input_path):
        die(f"input file not found: {input_path}")

    if output_path is None:
        base = os.path.splitext(os.path.basename(input_path))[0]
        output_path = f"{base}_tascam.wav"

    if os.path.exists(output_path):
        die(f"output file already exists: {output_path}")

    convert(input_path, output_path)


if __name__ == "__main__":
    main()
