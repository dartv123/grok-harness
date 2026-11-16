# Video references in Ref2VA

Read this when the user wires `ref_videos` / `ref_video_audios`, complains the source performer won, or wants to chain clips.

## What a video ref actually donates

- Motion, camera path, cadence, depth changes, handheld shake.
- Paired `ref_video_audio_N` donates **soundtrack**, not visual rhythm.
- Audio `fully_copy` is a 1:1 track lock. It does not lipsync the body. If they want the hip/head clock, that is `<Video N>` + `attribute_transfer`.

Output is locked at 24 fps. Changing Create Video fps only remuxes frames and drifts audio.

## Specs that will load

- Frames as an IMAGE batch. Min 5 frames (~0.2 s at 24 fps) or the node errors.
- Official clip length 2-15 s each, total video ≤ 15 s, max 3 clips.
- Other fps is drop/duplicated onto 24. 25 fps is fine. Do **not** load a 5 s action at 2 fps — that becomes held poses and H3 invents a different performance.
- Frames past the requested `length` are trimmed. A 15 s file into a 10 s job keeps roughly the first 10 s.
- Audio shorter than output + `fully_copy` dies or gibbers after the file ends. Loop the wav or use `partially_copy`.

## Cost

Video tokens ride every sampler step. Expect ~2-3× wall time vs still-only; unresized 720p/1080p can go worse. `ref_image_size: max` is another multiplier.

Starve a competing face in the clip: downscale the **video** (short edge ~512-640) and keep identity stills on `max`.

## Aspect

A 16:9 landscape performance teaching a 2:3 portrait canvas leaks set and framing (tripod, walls). Crop the ref toward the output aspect when the sides start directing the shot.

## Identity leak (the main failure)

A close face-filling performance clip outvotes a standing identity plate. The model picks the face that already lives in the shot.

Do **not** fix this with more adjectives alone.

Pipeline that works:

1. Make an **in-scene still** of the target person in the target camera/act. Build it **without** the motion video (image edit / face swap onto a paused frame, or T2I). If that still already shows the dummy, throw it away.
2. Wire that still as Picture 1 (`fully_preserved`, in-scene look).
3. Wire the original face close-up as Picture 2 (tie-break).
4. Drop or weaken the standing full-body plate if the in-scene still already has wardrobe.
5. Name a **motion dummy** Subject extracted from Video N with zero identity. `attribute_transfer` kinematics only. Explicitly discard dummy face, hair, and wardrobe.
6. Keep `detailed_description` thin on choreography. Restating the clip stroke-for-stroke fights the video. Map the same beats and timestamps. Let Video N drive motion.

Priority sentence in retention: if identity conflicts with Video N, Picture 1 / Picture 2 wins.

## Do not over-prompt motion

When a full-rate video is wired, shots should say "follow Video N for this phrase" plus who is on screen. Extra invented motion is a second dance.

Sparse / low-fps video refs are not keyframes. Real keyframes are stills on Add Guide at output timestamps, or Pictures marked as frame anchors.

## One clip vs many executes

- One execute, one video, duration matches the file when possible (5 / 10 / 15 s → 124 / 243 / 362 frames).
- Three 5 s videos in **one** 15 s execute is legal (total 15 s) but heavier. Tags are Video 1/2/3 in connection order; audios play in sequence if each is `fully_copy`.
- Three **separate** 5 s executes are independent samples. Same stills, same seed. Expect a splice. Stitch in ffmpeg after.

## Continuation across executes

Not a warm latent. Soft handoff only.

- Clip B may take the last ≥2 s (≥5 frames, 24 fps) of clip A as Video 1 (state/camera) and the next dummy phrase as Video 2.
- Prefix includes `video continuation`.
- Only do this if clip A's face already held. A leaked tail cements the leak.
- New audio per execute. Crossfade after.

## Comfy sockets

On MiniMaxH3ReferenceToVideo, growable names are `ref_videos.ref_video_0` and `ref_video_audios.ref_video_audio_0` (1-based tags in the prompt). Collapsed autogrow is why users "don't see" a video input.

Lightning / 4-step turbo is a wiring test. It is sloppy on identity and cadence. Turn it off for a lock pass.

## Duration math (24 fps, 17k+5)

- 5 s → 124 frames
- 10 s → 243 frames
- 15 s → 362 frames
