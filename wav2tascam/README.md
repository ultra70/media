[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# wav2tascam

Convert WAV files to a format compatible with Tascam Model 12/16/24.

## The Problem

Tascam Model 12/16/24 will not import WAV files that use the WAVE\_FORMAT\_EXTENSIBLE (0xFFFE) header format.  Both ffmpeg and SoX default to this format when encoding 24-bit audio.  The Tascam firmware only accepts standard PCM (format tag 0x0001), and presents a generic "File Error" on import with no further explanation.

## What This Script Does

Rewrites the WAV header to use standard PCM format tag (0x0001).  Sample rate, bit depth, and channel layout are preserved from the source file.

**Note:** This script is not required for 16-bit WAV files.  ffmpeg and SoX only default to WAVE\_FORMAT\_EXTENSIBLE for bit depths above 16.  A 16-bit WAV already uses format tag 0x0001 and imports to Tascam mixers without conversion.

## Usage

```
wav2tascam.py [-h] [-v] <input.wav> [output.wav]
```

If output is omitted, writes to `<input_basename>_tascam.wav` in the current directory.

### Examples

```
./wav2tascam.py drums.wav drums_out.wav
./wav2tascam.py vocals.wav
```

### Notes

- The Song sample rate on the Tascam Model 12/16/24 must match the file sample rate.
- Target tracks must be empty before import.
- Stereo files import to a track pair and require two empty tracks.
