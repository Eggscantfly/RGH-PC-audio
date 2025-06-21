# RGH-PC-Audio
Python scripts designed for extracting and reimporting custom audio for RGH.

# LyN_Extractor
Usage: Python Lyn_Extractor.py input.sns output.wav

# LyN_Reimport
Usage: Python Lyn_Reimport.py input.sns input.wav output.sns
Note: `Lyn_Reimport.py` currently supports only Ogg Vorbis-encoded SNS files
(codec IDs `0x3156` and `0x3157`).

# Requirements
Ensure that ffmpeg and oggenc2 are in your system's PATH for these scripts to function properly.

# Features
You can successfully play custom SNS files with vgmstream. However, further work is needed to enable them for in-game use.

# Contributions
Feel free to update and improve the original code, especially if you're able to make it work for in-game use or fix any issues.
