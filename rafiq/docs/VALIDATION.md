# Validation record — 22 November 2026

## Passed in the development environment

- 16 unittest cases covering project persistence and revisions, local session/origin/host checks, expiring revision-bound cost approval, repeat-safe submissions, missing-weight/CPU/API-node rejection, output failure handling, image binding, project asset isolation, JSON imports and restart/cancellation behavior.
- Real FFmpeg/ffprobe processing in integration tests: imported MP4, normalized WAV, H.264/AAC assembly, held last frames, readable output and persistence after reopening the store.
- JavaScript syntax and Python compilation.
- Comparison of the Wan 2.2 workflow against the official native template and node input definitions.

The ComfyUI HTTP round-trip tests deliberately use a labelled protocol fixture that returns a real FFmpeg diagnostic clip. The fixture's device field explicitly says it is not a real GPU. These tests validate integration behavior and playable media handling; they do not validate diffusion, video quality, peak model memory, identity continuity or speech.

## Browser checks passed

Using the actual FastAPI server and browser:

1. Loaded the Arabic first-chapter project and reviewed its layout.
2. Switched to English, edited a shot, saved, reloaded, confirmed persistence and restored its title.
3. Opened cost review with no ComfyUI engine: unknown cost stayed unknown, connection failure was shown, execution approval was disabled.
4. Created a separate diagnostic project, uploaded two one-second color clips through file inputs, selected both and exported through the actual job API.
5. Downloaded the resulting MP4 and inspected the exported file with ffprobe: H.264 video, AAC audio, 640×352, duration 2.021333 seconds. The color clips are diagnostic media, not AI-generated film scenes.
6. Returned the browser to the Arabic chapter project.

This confirms technical assembly of a short sample. Long-film throughput and interruption during long exports have not been benchmarked. Responsive CSS is included; a dedicated mobile browser acceptance pass remains pending. Browser-extension telemetry errors were observed outside the application; no claim is made about extension behavior.

## GPU and speech limits

The development machine has no exposed NVIDIA GPU or model weights. The user's laptop reports Intel HD Graphics 520, AMD Radeon R5 M330 and about 7.4GiB usable system RAM, which is not a practical target for these video presets. Separate Colab T4 execution passed on 23 November, as recorded below.

The first Colab notebook reuses the production graph/worker and now has a real Wan 2.1 T4 benchmark with playable outputs and measured hashes. This establishes only the recorded low-resolution settings. Wan 2.2, I2V, the complete portable ZIP path on GPU, higher resolution and long-film throughput remain unverified.

The optional offline Arabic speech adapter has not been run with weights. No generated voice, lip sync or character-identity guarantee has passed acceptance. No paid service, GPU rental, paid cloud machine or paid API was started.

## Version 0.2 checks — 23 November 2026

All 28 unittest cases pass locally. The suite now includes portable scene export, real MP4 result packaging/import through a labelled ComfyUI protocol fixture, exact I2V reference binding, result replay without duplicate assets, retained project edits, request/video tamper rejection, cross-project isolation, ZIP member/size/link checks, missing-GPU blocking, revision checks, and no automatic resubmission after a recorded failure. Successful output can be repackaged with the GPU engine unavailable. Notebook code compilation and the downloadable notebook endpoint are checked as well.

Browser acceptance passed on the actual application: exported and downloaded a scene ZIP, processed that downloaded request using the labelled protocol fixture and an FFmpeg clip marked `PROTOCOL TEST`, imported the result ZIP through the file input, reviewed the completed job, explicitly selected the take, and checked the English transfer controls. The selected video loaded with readyState 4 and duration 1 second. This was done in a separate diagnostic project; the chapter project has no generated takes. The interface was restored to Arabic and the chapter project. JavaScript syntax, Python compilation and whitespace checks pass locally.

These checks validate transfer and recovery, not neural inference. The subsequent, separate T4 execution is recorded below; it does not turn the transfer fixture into a GPU test.

## Real GPU acceptance — 23 November 2026

Wan 2.1 T2V 1.3B produced real H.264 videos on a free Tesla T4: 17 frames / 1.0625 seconds in 41.20 seconds and 81 frames / 5.0625 seconds in 54.18 seconds, both at 320×192 and 16fps. The longer video loaded and played in the browser. Model hashes, driver, source commit, whole-device memory observations and a separate additional short repeat are retained in [the benchmark record](GPU_BENCHMARK_2026-11-23.md).

The real test found a SaveVideo API mismatch hidden by the HTTP fixture: dynamic inputs must be flattened in the submitted graph. This was corrected, and text encoding now uses ComfyUI's native default device placement. All 28 local tests still pass. GitHub's updated Windows CPU smoke job also passed real CreateVideo/SaveVideo generation, download and H.264 decoding without model weights; Ruff, Pylint and the studio integration checks passed for source commit `a89a7bb63c746336c983f645a02140f0c2d20fa1`.

The visual result is a small flat cartoon, not approved cinematic 3D footage. No speech or identity continuity has been validated. The engine process was stopped after testing. Original clips and reports remain in the Colab runtime pending user download: the automated download did not complete, and embedded-media transfer was rejected by the browser's URL policy. MP4 bytes have not been archived here. No paid resources or purchases were used.
