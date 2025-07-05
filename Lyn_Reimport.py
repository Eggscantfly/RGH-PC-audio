#!/usr/bin/env python3
import os
import struct
import argparse
import tempfile
import subprocess
import wave
import shutil

def reimport_lyn_audio(original_lyn_path, new_wav_path, output_lyn_path):
    # Read original LyN file
    with open(original_lyn_path, 'rb') as f:
        data = f.read()

    # Locate important chunks
    fmt_offset = data.find(b'fmt ')
    if fmt_offset == -1:
        raise ValueError("fmt chunk not found in original LyN file")
    fmt_size = struct.unpack_from('<I', data, fmt_offset + 4)[0]
    fmt_chunk = data[fmt_offset : fmt_offset + 8 + fmt_size]

    fact_offset = data.find(b'fact')
    if fact_offset == -1:
        raise ValueError("fact chunk not found in original LyN file")
    fact_size = struct.unpack_from('<I', data, fact_offset + 4)[0]
    fact_chunk = data[fact_offset : fact_offset + 8 + fact_size]

    data_offset = data.find(b'data')
    if data_offset == -1:
        raise ValueError("data chunk not found in original LyN file")
    data_size = struct.unpack_from('<I', data, data_offset + 4)[0]
    data_start = data_offset + 8

    # Preserve extra chunks
    fact_end = fact_offset + 8 + fact_size
    extra_chunks = data[fact_end:data_offset] if data_offset > fact_end else b''

    # Parse codec ID
    codec_id = struct.unpack_from('<H', data, fmt_offset + 8)[0]
    if codec_id not in (0x3156, 0x3157):
        raise ValueError("This script only supports Ogg Vorbis codec (codec ID 0x3156 or 0x3157)")
    
    interleave_size = struct.unpack_from('<I', data, data_start)[0]
    channels = struct.unpack_from('<H', data, fmt_offset + 10)[0]
    original_sample_rate = struct.unpack_from('<I', data, fmt_offset + 12)[0]

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Read new WAV properties
        with wave.open(new_wav_path, 'rb') as w:
            new_sample_rate = w.getframerate()
            new_channels = w.getnchannels()
            new_num_samples = w.getnframes()

        # Resample if necessary
        if new_sample_rate != original_sample_rate or new_channels != channels:
            print(f"Resampling WAV: {new_channels}ch/{new_sample_rate}Hz -> {channels}ch/{original_sample_rate}Hz")
            adjusted_wav_path = os.path.join(tmp_dir, 'adjusted.wav')
            ffmpeg_adjust_cmd = [
                'ffmpeg', '-y', '-i', new_wav_path,
                '-ar', str(original_sample_rate),
                '-ac', str(channels),
                adjusted_wav_path
            ]
            subprocess.run(ffmpeg_adjust_cmd, check=True)
            new_wav_path = adjusted_wav_path
            with wave.open(new_wav_path, 'rb') as w:
                new_num_samples = w.getnframes()
        else:
            print("WAV matches original format.")

        # Split channels
        mono_wavs = [os.path.join(tmp_dir, f'channel_{ch}.wav') for ch in range(channels)]
        for ch in range(channels):
            ffmpeg_split_cmd = [
                'ffmpeg', '-y', '-i', new_wav_path,
                '-filter_complex', f'[0:a]pan=mono|c0=c{ch}[a]',
                '-map', '[a]',
                mono_wavs[ch]
            ]
            subprocess.run(ffmpeg_split_cmd, check=True)

        # Encode to OGG
        ogg_files = [os.path.join(tmp_dir, f'channel_{ch}.ogg') for ch in range(channels)]
        vorbis_quality = 6  

        oggenc_exe = "oggenc2.exe"
        if shutil.which(oggenc_exe) is None:
            raise FileNotFoundError(f"{oggenc_exe} not found in PATH.")

        for ch in range(channels):
            oggenc_cmd = (
                f'{oggenc_exe} -q {vorbis_quality} --comment "ENCODER=SLib_encoder" '
                f'-o "{ogg_files[ch]}" "{mono_wavs[ch]}"'
            )
            subprocess.run(oggenc_cmd, check=True, shell=True)

        # Pad and interleave properly
        ogg_streams = []
        logical_sizes_new = []
        num_blocks_list = []

        for ch in range(channels):
            with open(ogg_files[ch], 'rb') as f:
                ogg_data = f.read()
            logical_size = len(ogg_data)
            logical_sizes_new.append(logical_size)
            num_blocks = (logical_size + interleave_size - 1) // interleave_size
            num_blocks_list.append(num_blocks)
            ogg_streams.append(ogg_data)

        max_blocks = max(num_blocks_list)
        padded_streams = []
        for ch in range(channels):
            padded_size = max_blocks * interleave_size
            padding_needed = padded_size - len(ogg_streams[ch])
            padded_stream = ogg_streams[ch] + b'\0' * padding_needed
            padded_streams.append(padded_stream)

        interleaved_data = b''
        for i in range(max_blocks):
            for ch in range(channels):
                start = i * interleave_size
                end = start + interleave_size
                interleaved_data += padded_streams[ch][start:end]

        # Build final file
        header = struct.pack('<I', interleave_size)
        for size in logical_sizes_new:
            header += struct.pack('<I', size)
        new_data_payload = header + interleaved_data

        # Update fact chunk (sample count)
        new_fact_chunk = fact_chunk[:8] + struct.pack('<I', new_num_samples) + fact_chunk[12:]

        out_chunks = b'WAVE' + fmt_chunk + new_fact_chunk + extra_chunks + b'data' + struct.pack('<I', len(new_data_payload)) + new_data_payload
        new_file_size = len(out_chunks)

        with open(output_lyn_path, 'wb') as f:
            f.write(b'RIFF')
            f.write(struct.pack('<I', new_file_size))
            f.write(out_chunks)

    print("Reimport finished successfully.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reimport audio into Ubisoft LyN files (proper interleave fix)')
    parser.add_argument('original_lyn', help='Original .sns/.lwav file')
    parser.add_argument('new_wav', help='New stereo WAV file to import')
    parser.add_argument('output_lyn', help='Output .sns/.lwav file with new audio')
    args = parser.parse_args()

    reimport_lyn_audio(args.original_lyn, args.new_wav, args.output_lyn)
