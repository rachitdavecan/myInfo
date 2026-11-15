#!/usr/bin/env bash
# Thanos x "Kabhi Kabhi Mere Dil Mein" reel maker
#
# usage:
#   ./make_reel.sh <scene.mp4> <song.mp3> [out.mp4]
#
# Edit the TIMINGS below once you've found your moments (all in seconds).
set -euo pipefail

SCENE=${1:?scene video missing}
SONG=${2:?song audio missing}
OUT=${3:-thanos_reel.mp4}

# ---------- TIMINGS (edit these) ----------
CLIP_START=${CLIP_START:-0}     # where the reel starts in the scene video
CLIP_LEN=${CLIP_LEN:-15}        # reel length
SCENE_HIT=${SCENE_HIT:-4}       # moment Thanos sits down / looks at the sunrise (time in scene video)
SONG_DROP=${SONG_DROP:-20}      # moment "Kabhi kabhi..." starts in the song file
ORIG_VOL=${ORIG_VOL:-0.0}       # 0 = mute movie audio, 0.15 = keep a little ambience

# ---------- TEXT (edit these) ----------
TOP1=${TOP1:-"Thanos after wiping out"}
TOP2=${TOP2:-"half the universe:"}
LYRIC1=${LYRIC1:-"kabhi kabhi mere dil mein..."}
LYRIC2=${LYRIC2:-"khayal aata hai..."}   # (add emoji later in CapCut/IG; ffmpeg fonts show them as boxes)
LYRIC2_DELAY=${LYRIC2_DELAY:-3} # seconds after the hit when line 2 appears

FONT=${FONT:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}
# ------------------------------------------

calc() { awk "BEGIN{printf \"%.3f\", $1}"; }
SONG_START=$(calc "$SONG_DROP - ($SCENE_HIT - $CLIP_START)")
HIT_T=$(calc "$SCENE_HIT - $CLIP_START")          # hit time inside the reel
L2_T=$(calc "$HIT_T + $LYRIC2_DELAY")
FADE_OUT=$(calc "$CLIP_LEN - 1.2")

if awk "BEGIN{exit !($SONG_START < 0)}"; then
  echo "ERROR: song would start at ${SONG_START}s. Increase CLIP_START or use a later SONG_DROP." >&2
  exit 1
fi

# text goes through files so quotes/emoji don't break ffmpeg escaping
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
printf '%s' "$TOP1" > "$TMP/top1.txt"
printf '%s' "$TOP2" > "$TMP/top2.txt"
printf '%s' "$LYRIC1"   > "$TMP/l1.txt"
printf '%s' "$LYRIC2"   > "$TMP/l2.txt"

TXT="fontfile=$FONT:fontcolor=white:borderw=4:bordercolor=black@0.8:x=(w-text_w)/2"

# Video: blurred full-frame background + sharp 16:9 movie in the middle (keeps Thanos fully in frame),
# warm sunset grade, fade in/out, captions.
VF="[0:v]split[a][b];\
[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:2,eq=brightness=-0.15[bg];\
[b]scale=1080:-2,colorbalance=rs=0.08:gs=0.02:bs=-0.08,eq=saturation=1.1:contrast=1.05[fg];\
[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,\
drawtext=$TXT:textfile=$TMP/top1.txt:fontsize=54:y=h*0.20,\
drawtext=$TXT:textfile=$TMP/top2.txt:fontsize=54:y=h*0.20+70,\
drawtext=$TXT:textfile=$TMP/l1.txt:fontsize=60:y=h*0.72:enable='gte(t,$HIT_T)',\
drawtext=$TXT:textfile=$TMP/l2.txt:fontsize=60:y=h*0.72+80:enable='gte(t,$L2_T)',\
fade=t=in:d=0.4,fade=t=out:st=$FADE_OUT:d=1.2[v]"

# Audio: song aligned so the hook lands on SCENE_HIT, optional movie ambience under it.
if awk "BEGIN{exit !($ORIG_VOL > 0)}"; then
  AF="[1:a]afade=t=in:d=0.3,afade=t=out:st=$FADE_OUT:d=1.2[s];[0:a]volume=$ORIG_VOL[o];[s][o]amix=inputs=2:duration=first:normalize=0[aout]"
else
  AF="[1:a]afade=t=in:d=0.3,afade=t=out:st=$FADE_OUT:d=1.2[aout]"
fi

echo "Song starts at ${SONG_START}s, hook lands at ${HIT_T}s into the reel."
ffmpeg -hide_banner -loglevel warning -y \
  -ss "$CLIP_START" -t "$CLIP_LEN" -i "$SCENE" \
  -ss "$SONG_START" -t "$CLIP_LEN" -i "$SONG" \
  -filter_complex "$VF;$AF" -map "[v]" -map "[aout]" \
  -c:v libx264 -crf 19 -preset medium -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -movflags +faststart -shortest "$OUT"
echo "Done -> $OUT"
