# First real GPU results — 23 November 2026

The production `ComfyClient` and `Worker` ran Wan 2.1 T2V 1.3B on a free Colab Tesla T4 session. These are model outputs, not the protocol fixture or FFmpeg color clips. The source checkout was `a89a7bb63c746336c983f645a02140f0c2d20fa1`; the engine's core files were unchanged from the earlier running checkout. Model revisions and file hashes are retained in [the measurement record](benchmarks/2026-11-23-wan21-t4.json).

## Environment and results

- Tesla T4, 15,637,086,208 bytes device memory; 13,605,818,368 bytes system RAM.
- NVIDIA driver 580.82.07, Python 3.13.16, PyTorch 2.14.1+cu130, ComfyUI 0.44.0.
- Native loaders, `--lowvram`, loopback-only engine, offline mode, custom nodes disabled.
- First courtyard shot from the example chapter: seed 41201, requested 3D style, CFG 5, `uni_pc` / `simple`, sampling shift 8. No reference image, generated sound or dialogue.
- Colab displayed no subscription and zero compute units. No purchase, rental, public tunnel or paid API was used. Free resource availability remains variable.

| Run | Settings | Actual MP4 | Generation time | Observed whole-device peak |
| --- | --- | --- | --- | --- |
| First successful smoke | 320×192, 8 steps, 16 fps | H.264, 17 frames, 1.0625 s | 41.20 s | 10,421 MiB |
| Longer shot | 320×192, 20 steps, 16 fps | H.264, 81 frames, 5.0625 s | 54.18 s | 10,389 MiB |
| Additional short repeat | 320×192, 8 steps, 16 fps | H.264, 17 frames, 1.0625 s | 5.09 s | 10,389 MiB |

The longer shot and repeat reused a warm engine and cached graph inputs. These numbers are not cold-start throughput or a promise for longer films. Memory was sampled with `nvidia-smi` across the whole device, not PyTorch allocation inside one process. Installation, model downloading and hashing are excluded from generation time.

An extra one-second command remained in a temporary notebook cell during editing, causing the additional repeat. The duplicate command was removed and the cell's complete contents were checked before any further execution. This was not an automatic retry by the studio or portable runner.

## Failures corrected by the real test

The initial CPU-text-encoder attempt completed sampling and decoding, then failed at `SaveVideo` after about 245.54 seconds. The submitted API graph incorrectly supplied a nested format dictionary. ComfyUI's dynamic inputs require flattened API fields: `format="mp4"` and `format.codec="h264"`; the node reconstructs the nested dictionary itself. No output from this failed attempt is counted as a successful video.

The graph now uses that native input contract and the text encoder's `default` placement, allowing ComfyUI to use the GPU and its own offloading policy. The existing Windows CPU smoke job now submits `EmptyImage → CreateVideo → SaveVideo` using the production graph's saving nodes, downloads the actual result through `ComfyClient`, and decodes H.264 with PyAV. This native test passed locally in the Colab engine and on GitHub's Windows CPU runner. The lightweight HTTP fixture cannot replace this contract check.

## Review and remaining gates

The 5.0625-second video loaded and played in the browser. Its appearance is a small, flat cartoon-like scene with a man and teacup; it has not passed the intended cinematic 3D visual standard or character approval. No identity continuity, Arabic speech, lip sync, 720p output, Wan 2.2 I2V or long-film quality has passed acceptance.

The full portable ZIP export/render/import cycle still needs a real GPU acceptance pass; its current end-to-end transfer tests use the labelled protocol fixture. These GPU results validate the shared production worker and Wan 2.1 text-video graph, not every preset or transport path.

The files and original reports were packaged in the Colab runtime as `Rafiq_GPU_Results_2026-11-23.zip`. Automated download did not complete; fetching the embedded media was rejected by the browser's URL policy. No workaround was used to transfer the blocked media. At this record's publication, user download is pending and the MP4 bytes are not archived with this repository. The engine process was stopped, while the notebook runtime was retained temporarily for user download. Its files are ephemeral: download them before disconnecting/deleting the runtime.

Next: retain the videos, review an approved character design and scene reference, then evaluate a higher-resolution native I2V shot before expanding the chapter sequence. Price estimates for a future paid GPU still require its actual rate and a user-approved budget.
