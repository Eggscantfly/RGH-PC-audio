import os
import struct
import argparse
import tempfile
import subprocess

def parse_lyn_file(input_path):
    with open(input_path, 'rb') as f:
        data = f.read()

    print(f"\n=== File Analysis ===")
    print(f"Total file size: {len(data)} bytes")

    fmt_offset = data.find(b'fmt ')
    data_offset = data.find(b'data')
    
    print(f"\n=== Chunk Offsets ===")
    print(f"fmt chunk found at: 0x{fmt_offset:04x}")
    print(f"data chunk found at: 0x{data_offset:04x}")

    if fmt_offset == -1 or data_offset == -1:
        raise ValueError("Not a valid LyN file - missing critical chunks")

    
    chunk_size = struct.unpack_from('<I', data, fmt_offset + 4)[0]
    codec_id = struct.unpack_from('<H', data, fmt_offset + 8)[0]
    channels = struct.unpack_from('<H', data, fmt_offset + 10)[0]
    sample_rate = struct.unpack_from('<I', data, fmt_offset + 12)[0]

    print(f"\n=== fmt Chunk Details ===")
    print(f"Chunk size: 0x{chunk_size:04x} ({chunk_size} bytes)")
    print(f"Codec ID: 0x{codec_id:04x}")
    print(f"Channels: {channels}")
    print(f"Sample rate: {sample_rate} Hz")

    
    data_size = struct.unpack_from('<I', data, data_offset + 4)[0]
    data_start = data_offset + 8
    remaining_data = len(data) - data_start

    print(f"\n=== data Chunk Details ===")
    print(f"Data size claimed: 0x{data_size:04x} ({data_size} bytes)")
    print(f"Actual data available: 0x{remaining_data:04x} ({remaining_data} bytes)")
    print(f"Data starts at: 0x{data_start:04x}")

    interleave_size = 0
    if codec_id in (0x3156, 0x3157):  
        interleave_size = struct.unpack_from('<I', data, data_start)[0]
        print(f"\n=== Ogg Vorbis Header ===")
        print(f"Interleave size: 0x{interleave_size:04x}")
        
        
        logical_sizes = []
        for ch in range(channels):
            offset = data_start + 4 + (4 * ch)
            size = struct.unpack_from('<I', data, offset)[0]
            logical_sizes.append(size)
            print(f"Channel {ch} logical size: 0x{size:04x}")
            
        data_start += 4 + (4 * channels)
        
    elif codec_id == 0x0001:  
        interleave_size = 2 * channels  
        print(f"\n=== PCM Configuration ===")
        print(f"Calculated interleave size: {interleave_size} bytes")
    else:
        print("\n!!! WARNING: Unhandled codec structure !!!")
        print("Trying to continue with basic extraction...")
        interleave_size = 0x8000  

    print(f"\n=== Extraction Parameters ===")
    print(f"Using interleave size: 0x{interleave_size:04x}")
    print(f"Final data start offset: 0x{data_start:04x}")
    print(f"Data to extract: {len(data[data_start:data_start+data_size])} bytes")

    return {
        'data': data[data_start:data_start+data_size],
        'channels': channels,
        'interleave_size': interleave_size,
        'codec_id': codec_id,
        'sample_rate': sample_rate
    }

def extract_lyn_audio(input_path, output_path):
    try:
        file_info = parse_lyn_file(input_path)
        
        print(f"\n=== Extraction Process ===")
        print(f"Processing {file_info['channels']}-channel audio")
        print(f"Codec: 0x{file_info['codec_id']:04x}")
        print(f"Interleave size: 0x{file_info['interleave_size']:04x}")

        if file_info['interleave_size'] == 0:
            raise ValueError("Invalid interleave size (0) detected")

        
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_files = []
            for ch in range(file_info['channels']):
                temp_files.append(os.path.join(tmp_dir, f'channel_{ch}.ogg'))

            print(f"\n=== Temporary Files ===")
            print(f"Using temp directory: {tmp_dir}")
            for tf in temp_files:
                print(f"Will create: {tf}")

            
            interleave = file_info['interleave_size']
            data = file_info['data']
            
            print(f"\n=== Data Splitting ===")
            print(f"Total data to split: {len(data)} bytes")
            print(f"Channels: {file_info['channels']}")
            print(f"Interleave block size: {interleave} bytes")

            for ch in range(file_info['channels']):
                print(f"\n-- Processing channel {ch} --")
                with open(temp_files[ch], 'wb') as f:
                    pos = ch * interleave
                    written = 0
                    while pos < len(data):
                        end = pos + interleave
                        block = data[pos:end]
                        f.write(block)
                        written += len(block)
                        print(f"Wrote block @ 0x{pos:04x}-0x{end:04x} ({len(block)} bytes)")
                        pos += file_info['channels'] * interleave
                    print(f"Total written for channel {ch}: {written} bytes")

            
            print(f"\n=== FFmpeg Processing ===")
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',
                '-hide_banner',
                '-loglevel', 'error'
            ]

            for tf in temp_files:
                ffmpeg_cmd.extend(['-i', tf])

            if file_info['channels'] == 1:
                ffmpeg_cmd.extend([
                    '-ar', str(file_info['sample_rate']),
                    '-c:a', 'pcm_s16le',
                    output_path
                ])
            else:
                inputs = ''.join(f'[{i}:a]' for i in range(file_info['channels']))
                filter_complex = f'{inputs}amerge=inputs={file_info["channels"]}[a]'
                ffmpeg_cmd.extend([
                    '-filter_complex', filter_complex,
                    '-map', '[a]',
                    '-ac', str(file_info['channels']),
                    '-ar', str(file_info['sample_rate']),
                    '-c:a', 'pcm_s16le',
                    output_path
                ])
            
            print("Running FFmpeg command:")
            print(' '.join(ffmpeg_cmd))
            
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print("\n!!! FFmpeg Error !!!")
                print(f"Exit code: {result.returncode}")
                print(f"Error output:\n{result.stderr}")
                raise subprocess.CalledProcessError(result.returncode, ffmpeg_cmd)

    except Exception as e:
        print(f"\n!!! Critical Error !!!")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        if hasattr(e, 'errno'):
            print(f"Error number: {e.errno}")
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract audio from Ubisoft LyN files')
    parser.add_argument('input', help='Input .sns/.lwav file')
    parser.add_argument('output', help='Output .wav file')
    args = parser.parse_args()

    try:
        extract_lyn_audio(args.input, args.output)
        print(f"\n=== Success ===")
        print(f"Created {args.output}")
    except Exception as e:
        print(f"\n=== Extraction Failed ===")
        exit(1)
