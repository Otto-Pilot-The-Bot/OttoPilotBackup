#!/bin/sh
# Transcribe a video/audio file locally (nothing is uploaded): ./tools/transcribe.sh path/to/video.mp4 > transcript.txt
set -e
cd "$(dirname "$0")/.."
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
ffmpeg -loglevel error -i "$1" -ar 16000 -ac 1 -c:a pcm_s16le "$tmp/a.wav"
whisper-cli -m tools/whisper/ggml-base.en.bin -f "$tmp/a.wav" -nt 2>/dev/null
