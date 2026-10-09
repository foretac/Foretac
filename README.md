# ForeTac Project Website

Project website for **ForeTac: Predictive Contact Guidance for Generative Robot Policies**.

- Website: <https://foretac.github.io/>
- GitHub Pages repository: <https://github.com/foretac/foretac.github.io>
- Project repository: <https://github.com/foretac/Foretac>

ForeTac uses a frozen tactile representation, an action-conditioned foresight transformer, a contact-quality objective, and gradient guidance during generative action formation. The website presents the method, the current SR/CSR results, paper-backed diagnostics, and real-robot demonstrations for board wiping, vase wiping, card swiping, and fragile chip grasping.

## Local Preview

Serve the repository over HTTP so that browser media behavior matches deployment more closely:

```bash
cd /path/to/foretac_web
python -m http.server 8000
```

Then open <http://localhost:8000>. Opening `index.html` directly is also supported, but an HTTP preview is preferred for media behavior. Python's simple server may answer Range requests with `200` rather than `206`, so validate partial-content seeking against the deployment host or another Range-capable server.

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

The page uses the paper submission figures copied to `static/images/manuscript/`:

- `foretac_teaser_fig1.webp` for the conceptual overview;
- `foretac_method_fig2.webp` for the method architecture;
- `foretac_tasks_fig3.webp` for the robot platform and four-task benchmark;
- `foretac_guidance_fig4_r12.png` for the two-panel offline guidance diagnostic, matching the current submission Fig. 4 with panel labels and a complete color scale.

Main results and the structural ablation remain visible in `index.html`; reconstruction, prediction, scorer-transfer, guidance diagnostics, and efficiency use expandable subsections that are open by default. Readers can collapse them individually. The displayed results use SR/CSR terminology and were transcribed from `foretac_v3/main.tex`.

## Video Assets

The Overview section embeds `static/videos/overview/ForeTac_1008.mp4`,
the current approximately 2-minute-11-second film. The older
`ForeTac_video_keyframes_v2 - czy1007_x264_v3.mp4`, `foretac_overview-1007.mp4`,
and `foretac_overview.mp4` are retained as separate exports and are not the
current page source. The complete source and derived media for the Overview
assets and the opening montage live
under `static/videos/overview/`, including the four independently playable
opening tiles and `hero_montage_no_title.mp4`. It is
an independent native-controls player; its progress bar is not intercepted by
the task-pair synchronization code, and its native `loop` behavior restarts the
film after playback reaches the end. Its first five seconds and poster show
the clean montage without a title panel. A seven-slide editable PowerPoint
with embedded montage and foresight videos is available as
`static/videos/overview/foretac_overview_embedded.pptx`. Its opening slide has
no overlay. The alternate `foretac_overview_editable_cover.pptx` adds a native
editable translucent rectangle and text. Headings and result values are
editable; figures remain images. This is an editable reconstruction, not a
timed export of the film. See [the media README](static/videos/overview/README.md)
for editing limits and rebuild commands.
`tools/build_v3_media.sh` reproduces the Hero, legacy 45-second overview film,
and poster files
from the checked-in assets; `tools/make_overview_ppt.py` rebuilds the PPTX.

The older 117-second promotional export is retained only as
`foretac_overview_legacy_117s.mp4` (and the duplicate legacy copy is explicitly
named with the same duration). It is not referenced by the page because it
contains obsolete terminology and experiments.

Each real-robot task uses a synchronized pair:

| Task | Real execution | Tactile/marker visualization |
| --- | --- | --- |
| Board wiping | `board_real.mp4` | `board_viz.mp4` |
| Vase wiping | `vase_real.mp4` | `vase_viz.mp4` |
| Card swiping | `card_real.mp4` | `card_viz.mp4` |
| Chip grasping | `chip_real_1x4x.mp4` | `chip_viz_1x4x.mp4` |

The demonstrations also include the visual-perturbation generalization pair
(`generalization_visual_perturb_real.mp4` and
`generalization_visual_perturb_viz.mp4`). The final foresight prediction
visualization (`foresight_prediction_board_episode6_tplus16.webm` with MP4
fallback) is an independent t+16 diagnostic from the same Board episode; its
reference execution and prediction diagnostic use native video controls and are
not treated as a synchronized task pair.

The standalone foresight visualization and the diagnostic figures are retained
as local assets for reference. The embedded overview film labels the foresight
clip as a qualitative H=16 visualization and keeps offline diagnostics separate
from the task-level SR/CSR claims.

### Playback Behavior

- A task pair starts only after both videos are playable.
- Both sides pause, resume, restart, and resynchronize together.
- Clicking either video pauses or resumes the pair.
- Videos loop after reaching the end.
- Media is activated near the viewport instead of loading every video eagerly.
- Reduced-motion preferences disable automatic playback; clicking either panel still starts the pair.
- A spinner is shown during initial loading, seeking, and buffering.
- On narrow screens the Hero keeps the complete 16:9 four-task montage in a dark letterbox so the moving video region is not confused with a static poster.
- On very wide screens the Hero preserves the complete four-tile montage in the foreground and fills the side areas with a synchronized, softly blurred copy of the same video; intermediate desktop widths use centered cover cropping.

The five task visualizations contain synchronized tactile images and marker offsets, Score and Force curves, and phase annotations. Their media and posters match the approved v2 demo bundle.

### Web and Raw Files

The task videos referenced by `index.html` are the approved web-ready v2 files. Older pre-optimization versions remain beside them with the `_raw.mp4` suffix, for example:

```text
board_real.mp4       Web version used by the page
board_real_raw.mp4   Historical source retained for reference
```

Do not point the webpage at `_raw` files. When replacing a task pair:

1. Preserve the approved source bundle and its verification records locally.
2. Copy the matching real execution and visualization from the same task folder.
3. Keep the left and right outputs at exactly the same duration; normalize frame rate when the source permits and record any source-cadence exception.
4. Regenerate their `*_preview.jpg` posters.
5. Test initial playback, buffering recovery, click pause/resume, looping, and synchronization.

Detailed investigation and verification results are retained in the local workspace operation log under `midocx/`; source-path-bearing audit metadata is kept out of the public web tree.

## Task Video Encoding

Current task videos use the following web profile:

| Property | Value |
| --- | --- |
| Container / codec | MP4 / H.264 High Profile, Level 4.0 |
| Resolution | Real views: 1280x720; visualization views: 1920x1080 |
| Frame rate | Board/Vase/Card and Chip real: 24 fps; Chip visualization: 3947/250 (about 15.79 fps); Visual Perturbation: 30 fps |
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
6. Exercise the Hero, the Overview native controls/seek/loop, and all task pairs through loading, pause/resume, buffering, and loop transitions.
7. Confirm that every publication target points to the same reviewed commit.

Remote names and internal publication procedures are intentionally kept out of this public README because they depend on each collaborator's local Git and SSH configuration.
