# Overview Media

This folder keeps the source and derived media used by the Overview section and the opening Hero montage.

For the complete file-selection and re-encoding rules, see [`视频使用指导.md`](视频使用指导.md).

- `source_*_real.mp4`: web-normalized task recordings used to build the four-tile montage.
- `source_*_real_raw.mp4`: preserved source copies when available.
- `hero_*_tile.mp4`: the four independently playable 640x360 clips used in the opening montage.
- `hero_montage_no_title.mp4`: the 12-second four-tile montage without title overlays. This is the Hero video source.
- `foretac_overview.mp4`: the 45-second Overview film. Its first five seconds show the clean montage without a title or translucent panel; subsequent sections retain their presentation text.
- `foretac_overview_poster.jpg`: a clean montage frame, without a title or translucent panel.
- `foretac_overview_embedded.pptx`: a seven-slide 16:9 editable reconstruction, with a clean video-only opening slide.
- `foretac_overview_editable_cover.pptx`: the same deck with an optional cover. The translucent rectangle and three text boxes are independent native PowerPoint objects above the clean video.
- `segments/05_foresight_clean.mp4`: foresight footage without the presentation heading, used below editable text in the PPT.
- `source_foresight_prediction_board_episode6_tplus16.mp4`: source foresight visualization used by the Overview build.
- `source_foretac_guidance_fig4_r12.png`: current manuscript Figure 4 used by the film and both PPT decks.
- `source_board_guidance_panels_v3.png`: preserved older diagnostic figure; not used by the current builds.

The page references the copies in this folder for the Hero and Overview players. The task demonstration videos remain in `static/videos/` because they are also used by the synchronized task rows.

## Editing and Rebuilding

Both decks embed the opening montage and foresight video for offline use. Headings, cover elements, and result values are editable objects. Figures remain images, and video pixels remain video; their internal annotations are not editable text. Slide notes identify the corresponding Overview film intervals. The deck is not a timed, frame-identical export of the 45-second film; its opening video contains the full 12-second montage.

From the repository root, with FFmpeg, Pillow and python-pptx installed:

```bash
bash tools/build_v3_media.sh
python3 tools/make_overview_ppt.py --output static/videos/overview/foretac_overview_embedded.pptx
python3 tools/make_overview_ppt.py --output static/videos/overview/foretac_overview_editable_cover.pptx --editable-cover
```

To update only Figure 4 in the existing 45-second film, use
`bash tools/build_v3_media.sh --diagnostics-only` and then rebuild both decks
with the commands above. This replaces the diagnostic slide at 32-38 seconds
on a continuous 30 fps timeline; the other film sections retain their content.
The Hero montage, task videos, and poster files are not rebuilt in this mode.
