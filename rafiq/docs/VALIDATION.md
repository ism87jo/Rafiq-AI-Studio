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

## GPU and speech milestone still open

The development machine has no exposed NVIDIA GPU, PyTorch, model weights or running ComfyUI service. Neural inference was not run. The user's laptop reports Intel HD Graphics 520, AMD Radeon R5 M330 and about 7.4GiB available system RAM, which is not a practical target for these video presets.

The Colab notebook's code cells compile, and it reuses the production graph/worker. It still requires a real free GPU session, dependency/model installation and a passing output. It must not be described as GPU-tested until a benchmark report and playable output exist.

The optional offline Arabic speech adapter has not been run with weights. No generated voice, lip sync or character-identity guarantee has passed acceptance. No paid service, GPU rental, cloud machine or paid API was started.
