# RGH-PC-Audio
Python scripts designed for extracting and reimporting custom audio for RGH.

# LyN_Extractor
Usage: Run the script and select an input `.sns` file via file explorer. It will export a WAV file.

# LyN_Reimport (V2)
Usage: Run the script and select a `.wav` file when prompted. The new SNS will be saved using file explorer.

Note: `Lyn_Reimport.py` V2 now uses a fixed header layout and no longer requires an original input `.sns` file.
It currently supports only Ogg Vorbis-encoded SNS files (codec IDs `0x3156` and `0x3157`).

I will be keeping the old version (`V1`) for anyone who still wants or needs the original method that uses a reference `.sns`.

# Requirements
Ensure that ffmpeg and oggenc2 are in your system's PATH for these scripts to function properly.

# Features
You can successfully play custom SNS files with vgmstream. However, further work is needed to enable them for in-game use.

# Contributions
Feel free to update and improve the original code, especially if you're able to make it work for in-game use or fix any issues.
