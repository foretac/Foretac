# ForeTac Project Website

Project website for **ForeTac: Steering Robot Actions with Predicted Contact Consequences**.

- Website: <https://foretac.github.io/>
- GitHub Pages repository: <https://github.com/foretac/foretac.github.io>
- Project repository: <https://github.com/foretac/Foretac>

ForeTac steers robot actions using predicted contact consequences. Its inference pipeline combines a frozen TacVAE encoder, a tactile foresight transformer, a contact-quality energy model, and trust-region action refinement. The website presents the method, quantitative results, diagnostics, and real-robot demonstrations for board wiping, vase wiping, card swiping, and chip grasping.

## Local Preview

Serve the repository over HTTP so that browser media behavior matches deployment more closely:

```bash
cd /path/to/foretac_web
python -m http.server 8000
```

Then open <http://localhost:8000>. Opening `index.html` directly is also supported, but an HTTP preview is preferred when validating video loading and byte-range requests.

## Repository Structure

```text
foretac_web/
|-- index.html                         Main page and video playback logic
|-- static/
|   |-- css/style.css                  Layout and visual styles
|   |-- images/                        Method, diagnostics, and results assets
|   `-- videos/                        Web videos, previews, and raw backups
|-- tools/                             Media rendering and plotting utilities
|-- .nojekyll                          Disables Jekyll on GitHub Pages
|-- .gitlab-ci.yml                     GitLab Pages configuration
`-- README.md
```

The main image assets are:

- `teaser.svg`, `architecture.svg`, `training_pipeline.svg`, and `guidance_mechanism.svg`
- `board_guidance_diagnostics_overview.png`
- `foresight_prediction_quality_horizons.png` and its metrics JSON

Main-comparison and ablation results are rendered as responsive HTML tables in `index.html`. Their unfinished measurements are marked `TBD`; they are not pending PNG files.

## Video Assets

Each real-robot task uses a synchronized pair:

| Task | Real execution | Inference visualization |
| --- | --- | --- |
| Board wiping | `board_real.mp4` | `board_viz.mp4` |
| Vase wiping | `vase_real.mp4` | `vase_viz.mp4` |
| Card swiping | `card_real.mp4` | `card_viz.mp4` |
| Chip grasping | `chip_real.mp4` | `chip_viz.mp4` |

The standalone foresight visualization uses:

- `foresight_prediction_board_episode6_tplus16.webm`
- `foresight_prediction_board_episode6_tplus16.mp4` as a browser fallback
- `foresight_prediction_board_episode6_tplus16_preview.jpg` as its poster

### Playback Behavior

- A task pair starts only after both videos are playable.
- Both sides pause, resume, restart, and resynchronize together.
- Clicking either video pauses or resumes the pair.
- Videos loop after reaching the end.
- Media is activated near the viewport instead of loading every video eagerly.
- A spinner is shown during initial loading, seeking, and buffering.

The standalone foresight video also loops and supports click-to-pause/resume.

### Web and Raw Files

The task videos referenced by `index.html` are web-optimized files. Their exact pre-optimization sources are retained beside them with the `_raw.mp4` suffix, for example:

```text
board_real.mp4       Web version used by the page
board_real_raw.mp4   Original source retained for future re-encoding
```

Do not point the webpage at `_raw` files. When replacing a task pair:

1. Preserve each new source as the corresponding `*_raw.mp4` file.
2. Generate the web files from those raw sources.
3. Keep the left and right outputs at exactly the same duration and frame rate.
4. Regenerate their `*_preview.jpg` posters.
5. Test initial playback, buffering recovery, click pause/resume, looping, and synchronization.

Detailed investigation and verification results are recorded in [`static/videos/video_loading_optimization_record.md`](static/videos/video_loading_optimization_record.md).

## Task Video Encoding

Current task videos use the following web profile:

| Property | Value |
| --- | --- |
| Container / codec | MP4 / H.264 High Profile, Level 4.0 |
| Resolution | 1280x720 |
| Frame rate | Constant 24 fps |
| Pixel format | `yuv420p` |
| Quality | CRF 23 |
| Rate control | 1200 kbps max rate, 2400 kb buffer |
| Keyframes | GOP 48, approximately one keyframe every 2 seconds |
| Streaming | MP4 Fast Start enabled |
| Audio | Removed |

Reference command:

```bash
ffmpeg -i INPUT_RAW.mp4 \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24" \
  -c:v libx264 -preset medium -crf 23 \
  -profile:v high -level:v 4.0 -pix_fmt yuv420p \
  -maxrate 1200k -bufsize 2400k \
  -g 48 -keyint_min 48 -sc_threshold 0 \
  -movflags +faststart -an OUTPUT_WEB.mp4
```

Pair duration must be normalized before or during encoding; applying the command independently does not guarantee synchronized endpoints when the two sources have different durations.

## Maintenance Checks

Before publishing a website update:

1. Inspect `git status` and the actual diff.
2. Fetch every shared remote and check whether collaborators added commits.
3. Stage only the intended paths; avoid blanket staging commands.
4. Preview through a local HTTP server.
5. Check desktop and mobile layouts for overflow or overlap.
6. Exercise all video pairs and the standalone video through loading, pause/resume, buffering, and loop transitions.
7. Confirm that every publication target points to the same reviewed commit.

Remote names and internal publication procedures are intentionally kept out of this public README because they depend on each collaborator's local Git and SSH configuration.
