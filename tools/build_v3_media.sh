#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
video_dir="$repo_dir/static/videos"
overview_dir="$video_dir/overview"
image_dir="$repo_dir/static/images/manuscript"
diagnostic_image="$image_dir/foretac_guidance_fig4_r12.png"
mode="${1:-all}"
if [[ $# -gt 1 || ( "$mode" != all && "$mode" != --diagnostics-only ) ]]; then
  echo "Usage: $0 [--diagnostics-only]" >&2
  exit 2
fi
build_dir="$(mktemp -d)"
trap 'rm -rf "$build_dir"' EXIT

mkdir -p "$overview_dir/segments"

ffmpeg_bin="${FFMPEG_BIN:-ffmpeg}"
if ! command -v "$ffmpeg_bin" >/dev/null 2>&1; then
  echo "ffmpeg was not found." >&2
  exit 1
fi

font_bold="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
font_regular="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

diagnostic_filter="[1:v]scale=1780:690:force_original_aspect_ratio=decrease,pad=1780:690:(ow-iw)/2:(oh-ih)/2:color=white[fig];[0:v]drawtext=fontfile=$font_bold:text='Offline guidance diagnostics':fontcolor=0x0f172a:fontsize=36:x=70:y=98,drawtext=fontfile=$font_regular:text='Scorer-margin changes and scaled quality gradients':fontcolor=0x475569:fontsize=22:x=72:y=140[bg];[bg][fig]overlay=70:246,format=yuv420p[out]"

cp -p "$diagnostic_image" "$overview_dir/source_foretac_guidance_fig4_r12.png"

if [[ "$mode" == --diagnostics-only ]]; then
  film="$overview_dir/foretac_overview.mp4"
  dimensions="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$film")"
  duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$film")"
  if [[ "$dimensions" != 1920,1080,30/1 || "$duration" != 45.000000 ]]; then
    echo "Diagnostics-only update requires the existing 45-second, 1920x1080, 30 fps Overview film." >&2
    exit 1
  fi
  "$ffmpeg_bin" -hide_banner -loglevel error -y \
    -f lavfi -i "color=c=0xf8fafc:s=1920x1080:r=30:d=1" \
    -i "$diagnostic_image" -filter_complex "$diagnostic_filter" \
    -map "[out]" -frames:v 1 "$build_dir/diagnostics.png"
  # Replace only the six-second diagnostic slide on one continuous timeline.
  "$ffmpeg_bin" -hide_banner -loglevel error -y \
    -i "$film" -loop 1 -framerate 30 -i "$build_dir/diagnostics.png" \
    -filter_complex "[0:v][1:v]overlay=0:0:enable='gte(t,32)*lt(t,38)',format=yuv420p[out]" \
    -map "[out]" -frames:v 1350 -an -c:v libx264 -preset medium -crf 20 \
    -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 \
    -movflags +faststart "$build_dir/foretac_overview.mp4"
  cp -p "$build_dir/foretac_overview.mp4" "$video_dir/foretac_overview.mp4"
  cp -p "$build_dir/foretac_overview.mp4" "$overview_dir/foretac_overview.mp4"
  echo "Updated Overview diagnostics at 32-38 seconds; Hero and task videos were not rebuilt."
  exit 0
fi

# The top-row source views contain a 76 px recording label strip.  Crop the
# label and extra lower margin from each source so the wiping tool/contact
# region sits inside the tile instead of hugging its top edge.  Both outputs
# remain exact 640x360 tiles, matching the bottom views.
"$ffmpeg_bin" -hide_banner -loglevel error -y \
  -ss 5 -t 12 -i "$video_dir/board_real.mp4" \
  -ss 3 -t 12 -i "$video_dir/vase_real.mp4" \
  -stream_loop -1 -ss 1 -t 12 -i "$video_dir/card_real.mp4" \
  -ss 2 -t 12 -i "$video_dir/chip_real.mp4" \
  -filter_complex "\
[0:v]setpts=PTS-STARTPTS,crop=996:560:142:76,scale=640:360:flags=lanczos[board];\
[1:v]setpts=PTS-STARTPTS,crop=996:560:142:76,scale=640:360:flags=lanczos[vase];\
[2:v]setpts=PTS-STARTPTS,crop=iw:ih-76:0:76,scale=640:360:force_original_aspect_ratio=increase,crop=640:360[card];\
[3:v]setpts=PTS-STARTPTS,crop=iw:ih-76:0:76,scale=640:360:force_original_aspect_ratio=increase,crop=640:360[chip];\
[board][vase]hstack=inputs=2[top];[card][chip]hstack=inputs=2[bottom];\
[top][bottom]vstack=inputs=2,setsar=1,format=yuv420p[out]" \
  -map "[out]" -t 12 -an -c:v libx264 -preset medium -crf 22 \
  -profile:v high -level:v 4.0 -pix_fmt yuv420p -r 24 -g 48 -keyint_min 48 \
  -sc_threshold 0 -movflags +faststart "$build_dir/hero.mp4"

hero="$build_dir/hero.mp4"

# Preserve the exact inputs and independently playable clips used by the
# opening four-tile montage beside the published Overview media.
for source in board vase card chip; do
  cp -p "$video_dir/${source}_real.mp4" "$overview_dir/source_${source}_real.mp4"
  if [[ -f "$video_dir/${source}_real_raw.mp4" ]]; then
    cp -p "$video_dir/${source}_real_raw.mp4" "$overview_dir/source_${source}_real_raw.mp4"
  fi
done
for source in foresight_prediction_board_episode6_tplus16.mp4; do
  if [[ -f "$video_dir/$source" ]]; then
    cp -p "$video_dir/$source" "$overview_dir/source_$source"
  fi
done
for source in foretac_teaser_fig1.webp foretac_method_fig2.webp foretac_tasks_fig3.webp; do
  if [[ -f "$image_dir/$source" ]]; then
    cp -p "$image_dir/$source" "$overview_dir/source_$source"
  fi
done
"$ffmpeg_bin" -hide_banner -loglevel error -y -ss 5 -t 12 -i "$video_dir/board_real.mp4" \
  -vf "crop=996:560:142:76,scale=640:360:flags=lanczos,setsar=1,format=yuv420p" \
  -an -c:v libx264 -preset medium -crf 22 -profile:v high -level:v 4.0 -pix_fmt yuv420p -r 24 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart "$overview_dir/hero_board_tile.mp4"
"$ffmpeg_bin" -hide_banner -loglevel error -y -ss 3 -t 12 -i "$video_dir/vase_real.mp4" \
  -vf "crop=996:560:142:76,scale=640:360:flags=lanczos,setsar=1,format=yuv420p" \
  -an -c:v libx264 -preset medium -crf 22 -profile:v high -level:v 4.0 -pix_fmt yuv420p -r 24 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart "$overview_dir/hero_vase_tile.mp4"
"$ffmpeg_bin" -hide_banner -loglevel error -y -stream_loop -1 -ss 1 -t 12 -i "$video_dir/card_real.mp4" \
  -vf "crop=iw:ih-76:0:76,scale=640:360:force_original_aspect_ratio=increase,crop=640:360,setsar=1,format=yuv420p" \
  -an -c:v libx264 -preset medium -crf 22 -profile:v high -level:v 4.0 -pix_fmt yuv420p -r 24 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart "$overview_dir/hero_card_tile.mp4"
"$ffmpeg_bin" -hide_banner -loglevel error -y -ss 2 -t 12 -i "$video_dir/chip_real.mp4" \
  -vf "crop=iw:ih-76:0:76,scale=640:360:force_original_aspect_ratio=increase,crop=640:360,setsar=1,format=yuv420p" \
  -an -c:v libx264 -preset medium -crf 22 -profile:v high -level:v 4.0 -pix_fmt yuv420p -r 24 -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart "$overview_dir/hero_chip_tile.mp4"

# Slide 01: clean four-task footage. Title elements belong in the editable PPT.
"$ffmpeg_bin" -hide_banner -loglevel error -y -i "$hero" \
  -vf "scale=1920:1080" \
  -t 5 -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 "$build_dir/01-title.mp4"

# Slide 02: the manuscript concept figure.
"$ffmpeg_bin" -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=0xf8fafc:s=1920x1080:r=30:d=6" \
  -loop 1 -i "$image_dir/foretac_teaser_fig1.webp" \
  -filter_complex "[1:v]scale=1740:840:force_original_aspect_ratio=decrease,pad=1740:840:(ow-iw)/2:(oh-ih)/2:color=white[fig];[0:v][fig]overlay=90:174,drawtext=fontfile=$font_bold:text='Predict the contact before it happens':fontcolor=0x0f172a:fontsize=34:x=90:y=112,drawtext=fontfile=$font_regular:text='Anticipate the tactile consequence of a candidate action':fontcolor=0x475569:fontsize=22:x=92:y=148,format=yuv420p[out]" \
  -map "[out]" -t 6 -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 "$build_dir/02-concept.mp4"

# Slide 03: the manuscript method figure.
"$ffmpeg_bin" -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=0xf8fafc:s=1920x1080:r=30:d=8" \
  -loop 1 -i "$image_dir/foretac_method_fig2.webp" \
  -filter_complex "[1:v]scale=1780:790:force_original_aspect_ratio=decrease,pad=1780:790:(ow-iw)/2:(oh-ih)/2:color=white[fig];[0:v][fig]overlay=70:196,drawtext=fontfile=$font_bold:text='Represent - predict - evaluate - guide':fontcolor=0x0f172a:fontsize=34:x=70:y=112,drawtext=fontfile=$font_regular:text='Frozen models guide the evolving generative sampling state':fontcolor=0x475569:fontsize=22:x=72:y=150,format=yuv420p[out]" \
  -map "[out]" -t 8 -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 "$build_dir/03-method.mp4"

# Slide 04: the manuscript platform and task summary.
"$ffmpeg_bin" -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=0xf8fafc:s=1920x1080:r=30:d=6" \
  -loop 1 -i "$image_dir/foretac_tasks_fig3.webp" \
  -filter_complex "[1:v]scale=1780:610:force_original_aspect_ratio=decrease,pad=1780:610:(ow-iw)/2:(oh-ih)/2:color=white[fig];[0:v][fig]overlay=70:258,drawtext=fontfile=$font_bold:text='Four real-robot contact regimes':fontcolor=0x0f172a:fontsize=36:x=70:y=112,drawtext=fontfile=$font_regular:text='Board wiping - vase wiping - card swiping - fragile chip grasping':fontcolor=0x475569:fontsize=22:x=72:y=154,format=yuv420p[out]" \
  -map "[out]" -t 6 -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 "$build_dir/04-tasks.mp4"

# Slide 05: preserve a clean video for native editable headings in PowerPoint.
"$ffmpeg_bin" -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=0xf8fafc:s=1920x1080:r=30:d=7" \
  -ss 2 -t 7 -i "$video_dir/foresight_prediction_board_episode6_tplus16.mp4" \
  -filter_complex "[1:v]setpts=PTS-STARTPTS,drawbox=x=0:y=0:w=iw:h=86:color=white:t=fill,drawbox=x=170:y=124:w=370:h=36:color=white:t=fill,drawbox=x=600:y=124:w=370:h=36:color=white:t=fill,drawbox=x=1030:y=124:w=390:h=36:color=white:t=fill,crop=iw:570:0:0,scale=1760:760:force_original_aspect_ratio=decrease,pad=1760:760:(ow-iw)/2:(oh-ih)/2:color=white[fig];[0:v][fig]overlay=80:184,format=yuv420p,split=2[clean][film];[film]drawtext=fontfile=$font_bold:text='Action-conditioned tactile foresight':fontcolor=0x0f172a:fontsize=36:x=70:y=98,drawtext=fontfile=$font_regular:text='Ground-truth future - predicted future - error (qualitative, H=16)':fontcolor=0x475569:fontsize=22:x=72:y=140[out]" \
  -map "[out]" -t 7 -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 "$build_dir/05-foresight.mp4" \
  -map "[clean]" -t 7 -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 -movflags +faststart "$overview_dir/segments/05_foresight_clean.mp4"
"$ffmpeg_bin" -hide_banner -loglevel error -y -i "$overview_dir/segments/05_foresight_clean.mp4" \
  -frames:v 1 -q:v 2 "$overview_dir/segments/05_foresight_clean_poster.jpg"

# Slide 06: the current manuscript's offline guidance diagnostics.
"$ffmpeg_bin" -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=0xf8fafc:s=1920x1080:r=30:d=6" \
  -loop 1 -i "$diagnostic_image" \
  -filter_complex "$diagnostic_filter" \
  -map "[out]" -t 6 -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 "$build_dir/06-diagnostics.mp4"

# Slide 07: only current v3 headline numbers and supported backbones.
"$ffmpeg_bin" -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=0x0f172a:s=1920x1080:r=30:d=7" \
  -vf "drawtext=fontfile=$font_bold:text='ForeTac on four real-robot tasks':fontcolor=white:fontsize=52:x=120:y=100,drawtext=fontfile=$font_regular:text='DP 36.3 / 20.0  ->  DP + ForeTac 71.3 / 66.3   (SR / CSR)':fontcolor=0xf1f5f9:fontsize=26:x=140:y=232,drawtext=fontfile=$font_regular:text='20 trials per task; averages over four tasks':fontcolor=0x94a3b8:fontsize=22:x=142:y=272,drawtext=fontfile=$font_regular:text='Average task success rate (SR)':fontcolor=0xcbd5e1:fontsize=28:x=140:y=360,drawtext=fontfile=$font_bold:text='71.3%':expansion=none:fontcolor=0xfb923c:fontsize=76:x=140:y=415,drawtext=fontfile=$font_regular:text='Average contact success rate (CSR)':fontcolor=0xcbd5e1:fontsize=28:x=700:y=360,drawtext=fontfile=$font_bold:text='66.3%':expansion=none:fontcolor=0xa78bfa:fontsize=76:x=700:y=415,drawtext=fontfile=$font_regular:text='vs RDP  +12.5 / +17.5 pp (SR / CSR)':fontcolor=0xf1f5f9:fontsize=28:x=140:y=620,drawtext=fontfile=$font_regular:text='pi0.5 46.3 / 36.3  ->  + ForeTac 67.5 / 62.5   (SR / CSR)':fontcolor=0xcbd5e1:fontsize=25:x=140:y=700,drawtext=fontfile=$font_regular:text='Diffusion Policy and flow-matching backbones':fontcolor=0x94a3b8:fontsize=22:x=142:y=744,drawtext=fontfile=$font_regular:text='Predict contact. Guide action. Execute and replan.':fontcolor=white:fontsize=30:x=140:y=900" \
  -t 7 -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 "$build_dir/07-results.mp4"

printf "file '%s'\n" "$build_dir/01-title.mp4" "$build_dir/02-concept.mp4" "$build_dir/03-method.mp4" "$build_dir/04-tasks.mp4" "$build_dir/05-foresight.mp4" "$build_dir/06-diagnostics.mp4" "$build_dir/07-results.mp4" > "$build_dir/slides.txt"
"$ffmpeg_bin" -hide_banner -loglevel error -y -f concat -safe 0 -i "$build_dir/slides.txt" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 \
  -movflags +faststart "$video_dir/foretac_overview.mp4"

"$ffmpeg_bin" -hide_banner -loglevel error -y -ss 2.5 -i "$video_dir/foretac_overview.mp4" \
  -frames:v 1 -q:v 2 "$video_dir/foretac_overview_poster.jpg"

cp -p "$video_dir/foretac_overview.mp4" "$overview_dir/foretac_overview.mp4"
cp -p "$video_dir/foretac_overview_poster.jpg" "$overview_dir/foretac_overview_poster.jpg"

"$ffmpeg_bin" -hide_banner -loglevel error -y -i "$build_dir/hero.mp4" \
  -c copy -movflags +faststart "$video_dir/foretac_hero_loop.mp4"
"$ffmpeg_bin" -hide_banner -loglevel error -y -ss 3 -i "$video_dir/foretac_hero_loop.mp4" \
  -frames:v 1 -q:v 2 "$video_dir/foretac_hero_poster.jpg"

cp -p "$video_dir/foretac_hero_loop.mp4" "$overview_dir/hero_montage_no_title.mp4"
cp -p "$video_dir/foretac_hero_poster.jpg" "$overview_dir/hero_montage_no_title_poster.jpg"

echo "Generated paper-aligned Hero and overview media."
for media in "$video_dir/foretac_hero_loop.mp4" "$video_dir/foretac_overview.mp4"; do
  ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate \
    -of default=nw=1 "$media"
done
