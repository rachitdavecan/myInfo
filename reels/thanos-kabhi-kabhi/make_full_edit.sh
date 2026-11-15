#!/usr/bin/env bash
# Full-scene edit in the style of the Batman reference:
#   movie audio muted -> "Kabhi Kabhie" plays over the Endgame garden scene
#   -> song cuts dead on Thor's chop -> original audio returns ("What did you do?")
# Produces a 16:9 version (like the reference) and a 9:16 Reels version.
#
# usage: ./make_full_edit.sh <thanos.mp4> <song.mp3> [out_prefix]
set -euo pipefail
SCENE=${1:?scene}; SONG=${2:?song}; OUT=${3:-thanos_kabhi_kabhi}

START=${START:-78.5}       # garden reveal (cut point in thanos.mp4)
CHOP=${CHOP:-243.9}        # Thor's swing: song stops here
END=${END:-288.5}          # end of clip
SONG_IN=${SONG_IN:-12.6}   # where the song's music starts in the mp3 (skips the silent gap)
ORIG_BOOST=${ORIG_BOOST:-14dB}  # movie audio is quiet; lift it after the chop
FONT=${FONT:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}

calc(){ awk "BEGIN{printf \"%.3f\", $1}"; }
SONG_LEN=$(calc "$CHOP - $START")
TOTAL=$(calc "$END - $START")
FADE_OUT=$(calc "$TOTAL - 1.5")

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
printf '%s' "Thanos after wiping out half the universe:" > "$TMP/t.txt"
printf '%s' "Thanos after wiping out" > "$TMP/t1.txt"
printf '%s' "half the universe:" > "$TMP/t2.txt"
TXT="fontfile=$FONT:fontcolor=white:borderw=4:bordercolor=black@0.8:x=(w-text_w)/2:enable='lt(t,6)'"
GRADE="colorbalance=rs=0.05:bs=-0.05,eq=saturation=1.1:contrast=1.05"

# audio: song (muted movie) until the chop, hard cut, then boosted original audio
AF="[1:a]atrim=start=$SONG_IN:duration=$SONG_LEN,asetpts=PTS-STARTPTS,afade=t=in:d=1.5,aresample=48000,aformat=channel_layouts=stereo[s];\
[0:a]atrim=start=$CHOP:end=$END,asetpts=PTS-STARTPTS,volume=$ORIG_BOOST,alimiter=limit=0.9,afade=t=out:st=$(calc "$END-$CHOP-1.5"):d=1.5,aresample=48000,aformat=channel_layouts=stereo[o];\
[s][o]concat=n=2:v=0:a=1[a]"
VTRIM="[0:v]trim=start=$START:end=$END,setpts=PTS-STARTPTS,$GRADE"
FADES="fade=t=in:d=1.5,fade=t=out:st=$FADE_OUT:d=1.5"

echo "Song plays ${SONG_LEN}s, total ${TOTAL}s"

# 16:9 (like the reference): scale to 1920 wide, letterbox to 1080, caption in the top bar
ffmpeg -hide_banner -loglevel warning -y -i "$SCENE" -i "$SONG" -filter_complex \
"$VTRIM,scale=1920:-2:flags=lanczos,pad=1920:1080:0:(oh-ih)/2:black,setsar=1,\
drawtext=$TXT:textfile=$TMP/t.txt:fontsize=48:y=(h-806)/4-text_h/2,$FADES[v];$AF" \
  -map "[v]" -map "[a]" -c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart "${OUT}_16x9.mp4"
echo "-> ${OUT}_16x9.mp4"

# 9:16 Reels: blurred fill background + sharp movie in the middle + caption on top
ffmpeg -hide_banner -loglevel warning -y -i "$SCENE" -i "$SONG" -filter_complex \
"$VTRIM,split[a][b];\
[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:2,eq=brightness=-0.2[bg];\
[b]scale=1080:-2:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,\
drawtext=$TXT:textfile=$TMP/t1.txt:fontsize=56:y=h*0.25,\
drawtext=$TXT:textfile=$TMP/t2.txt:fontsize=56:y=h*0.25+75,$FADES[v];$AF" \
  -map "[v]" -map "[a]" -c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -movflags +faststart "${OUT}_9x16.mp4"
echo "-> ${OUT}_9x16.mp4"
