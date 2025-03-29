import os
import struct
import argparse
import tempfile
import subprocess
import wave
import shutil

def reimport_lyn_audio(original_lyn_path, new_wav_path, output_lyn_path):
    
    
    with open(original_lyn_path, 'rb') as f:
        data = f.read()

    
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

    
    fact_end = fact_offset + 8 + fact_size
    extra_chunks = b''
    if data_offset > fact_end:
        extra_chunks = data[fact_end:data_offset]

    
    codec_id = struct.unpack_from('<H', data, fmt_offset + 8)[0]
    if codec_id not in (0x3156, 0x3157):
        raise ValueError("This script only supports Ogg Vorbis codec (codec ID 0x3156 or 0x3157)")
    
    interleave_size = struct.unpack_from('<I', data, data_start)[0]
    channels = struct.unpack_from('<H', data, fmt_offset + 10)[0]
    original_sample_rate = struct.unpack_from('<I', data, fmt_offset + 12)[0]

    with tempfile.TemporaryDirectory() as tmp_dir:
        
        with wave.open(new_wav_path, 'rb') as w:
            new_sample_rate = w.getframerate()
            new_channels = w.getnchannels()
            new_num_samples = w.getnframes()

        if new_sample_rate != original_sample_rate or new_channels != channels:
            print(f"Original LyN: {channels} channels, {original_sample_rate} Hz")
            print(f"New WAV: {new_channels} channels, {new_sample_rate} Hz")
            print("Adjusting new WAV file to match original properties...")
            adjusted_wav_path = os.path.join(tmp_dir, 'adjusted.wav')
            ffmpeg_adjust_cmd = [
                'ffmpeg', '-y', '-i', new_wav_path,
                '-ar', str(original_sample_rate),
                '-ac', str(channels),
                adjusted_wav_path
            ]
            try:
                subprocess.run(ffmpeg_adjust_cmd, check=True)
                print("Adjustment complete.")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to adjust WAV file: {e}")
            new_wav_path = adjusted_wav_path
            with wave.open(new_wav_path, 'rb') as w:
                new_num_samples = w.getnframes()
        else:
            print("New WAV file matches original properties.")

        
        mono_wavs = [os.path.join(tmp_dir, f'channel_{ch}.wav') for ch in range(channels)]
        for ch in range(channels):
            ffmpeg_split_cmd = [
                'ffmpeg', '-y', '-i', new_wav_path,
                '-filter_complex', f'[0:a]pan=mono|c0=c{ch}[a]',
                '-map', '[a]',
                mono_wavs[ch]
            ]
            try:
                subprocess.run(ffmpeg_split_cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to split channel {ch}: {e}")

        
        ogg_files = [os.path.join(tmp_dir, f'channel_{ch}.ogg') for ch in range(channels)]
        vorbis_quality = 6  

        
        oggenc_exe = "oggenc2.exe"
        if shutil.which(oggenc_exe) is None:
            raise FileNotFoundError(f"{oggenc_exe} not found in PATH. Please ensure it is installed and available.")

        for ch in range(channels):
            
            oggenc_cmd = (
                f'{oggenc_exe} -q {vorbis_quality} --comment "ENCODER=SLib_encoder" '
                f'-o "{ogg_files[ch]}" "{mono_wavs[ch]}"'
            )
            try:
                subprocess.run(oggenc_cmd, check=True, shell=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to encode channel {ch} with {oggenc_exe}: {e}")

        
        ogg_streams = []
        logical_sizes_new = []
        for ch in range(channels):
            with open(ogg_files[ch], 'rb') as f:
                ogg_data = f.read()
            logical_size = len(ogg_data)
            logical_sizes_new.append(logical_size)
            num_blocks = (logical_size + interleave_size - 1) // interleave_size
            padded_size = num_blocks * interleave_size
            padded_ogg = ogg_data + b'\0' * (padded_size - logical_size)
            ogg_streams.append(padded_ogg)

        num_blocks = len(ogg_streams[0]) // interleave_size
        interleaved_data = b''
        for i in range(num_blocks):
            for ch in range(channels):
                start = i * interleave_size
                end = start + interleave_size
                block = ogg_streams[ch][start:end]
                interleaved_data += block

        
        
        header = struct.pack('<I', interleave_size)
        for size in logical_sizes_new:
            header += struct.pack('<I', size)
        new_data_payload = header + interleaved_data

        
        
        
        
        new_fact_chunk = fact_chunk[:8] + struct.pack('<I', new_num_samples) + fact_chunk[12:]

        
        
        out_chunks = b'WAVE' + fmt_chunk + new_fact_chunk + extra_chunks + b'data' + struct.pack('<I', len(new_data_payload)) + new_data_payload
        new_file_size = len(out_chunks)  

        with open(output_lyn_path, 'wb') as f:
            f.write(b'RIFF')
            f.write(struct.pack('<I', new_file_size))
            f.write(out_chunks)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reimport audio into Ubisoft LyN files')
    parser.add_argument('original_lyn', help='Original .sns/.lwav file')
    parser.add_argument('new_wav', help='New stereo WAV file to import')
    parser.add_argument('output_lyn', help='Output .sns/.lwav file with new audio')
    args = parser.parse_args()

    reimport_lyn_audio(args.original_lyn, args.new_wav, args.output_lyn)
