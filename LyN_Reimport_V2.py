import os
import struct
import tempfile
import subprocess
import wave
import shutil
from tkinter import Tk, filedialog


def build_fixed_sns():
    # Select input WAV file
    Tk().withdraw()
    wav_path = filedialog.askopenfilename(title="Select WAV File", filetypes=[("WAV files", "*.wav")])
    if not wav_path:
        print("No input WAV selected.")
        return

    # Select output path for SNS file
    output_path = filedialog.asksaveasfilename(defaultextension=".sns", filetypes=[("SNS files", "*.sns")])
    if not output_path:
        print("No output path selected.")
        return

    # Interleave block size expected by the engine
    interleave_size = 0x401F4

    with tempfile.TemporaryDirectory() as tmp_dir:
        adjusted_wav = os.path.join(tmp_dir, "adjusted.wav")

        # Read WAV properties
        with wave.open(wav_path, 'rb') as w:
            channels = w.getnchannels()
            sample_rate = w.getframerate()
            frames = w.getnframes()

        # Copy WAV (resampling is not needed unless required by game)
        shutil.copy(wav_path, adjusted_wav)

        # Split multi-channel WAV into individual mono WAV files
        mono_wavs = []
        for i in range(channels):
            out_path = os.path.join(tmp_dir, f"ch{i}.wav")
            subprocess.run([
                "ffmpeg", "-y", "-i", adjusted_wav,
                "-filter_complex", f"[0:a]pan=mono|c0=c{i}[a]",
                "-map", "[a]", out_path
            ], check=True)
            mono_wavs.append(out_path)

        # Encode each mono channel to OGG using oggenc2 with encoder metadata
        ogg_paths = []
        for i, mono in enumerate(mono_wavs):
            ogg_out = os.path.join(tmp_dir, f"ch{i}.ogg")
            subprocess.run(
                f'oggenc2.exe -q 6 --comment "ENCODER=SLib_encoder" -o "{ogg_out}" "{mono}"',
                shell=True, check=True
            )
            ogg_paths.append(ogg_out)

        # Pad OGG files and calculate interleaved layout
        logical_sizes = []
        padded_streams = []
        max_blocks = 0

        for path in ogg_paths:
            with open(path, 'rb') as f:
                ogg = f.read()
            logical_sizes.append(len(ogg))
            blocks = (len(ogg) + interleave_size - 1) // interleave_size
            padded = ogg + b'\x00' * (blocks * interleave_size - len(ogg))
            padded_streams.append(padded)
            max_blocks = max(max_blocks, blocks)

        # Interleave OGG streams
        interleaved = b''
        for block in range(max_blocks):
            for stream in padded_streams:
                start = block * interleave_size
                interleaved += stream[start:start + interleave_size]

        # Construct fmt chunk (26 bytes total)
        fmt_chunk = (
            b'fmt \x12\x00\x00\x00' +           # Chunk header and size
            b'V1' +                             # Codec ID (0x3156 = 'V1')
            struct.pack('<H', channels) +       # Channel count
            struct.pack('<I', sample_rate) +    # Sample rate
            b'\xf4\x01\x00\x04' +               # Byte rate (copied from reference)
            b'\x00\x10' +                       # Block align
            b'\x00\x00\x00\x00'                 # Padding (4 bytes to ensure alignment)
        )

        # Construct fact chunk with dynamic sample count (24 bytes total)
        fact_chunk = (
            b'fact\x10\x00\x00\x00' +
            struct.pack('<I', frames) +         # Total number of samples
            b'LyN \x03\x00\x00\x00\x07\x00\x00\x00'
        )

        # Construct data chunk (includes interleave header and encoded data)
        data_header = struct.pack('<I', interleave_size)
        for size in logical_sizes:
            data_header += struct.pack('<I', size)
        data_payload = data_header + interleaved
        data_chunk = b'data' + struct.pack('<I', len(data_payload)) + data_payload

        # Assemble RIFF structure
        full_data = b'WAVE' + fmt_chunk + fact_chunk + data_chunk
        riff_header = b'RIFF' + struct.pack('<I', len(full_data)) + full_data

        # Write final SNS file
        with open(output_path, 'wb') as out:
            out.write(riff_header)

        print(f"SNS file created at: {output_path}")


build_fixed_sns()
