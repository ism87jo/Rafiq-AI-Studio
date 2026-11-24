# Implementation plan and repository audit

Review date: 22 November 2026. Owner: مؤسسة رفيق البصيرة للتكنولوجيا والحلول الذكية.

## Existing repository

The repository is a ComfyUI codebase, not a finished Rafiq product. The clone contained 635 remote refs, mostly inherited ComfyUI development branches. The product comparison focused on these branches:

| Branch | Reviewed commit | Existing product contribution |
| --- | --- | --- |
| `master` | `1332fabfcc507aa7c548cd5152071ed494c207e8` | Upstream engine, nodes, server and existing frontend. |
| `rafiq/foundation` | `881a11953ca81dcfcdf2052128e1fd90fd5929a0` | Five files: Windows CPU setup/start, CPU smoke check, CI and bilingual foundation notes. |
| `develop` | `8c6547ad5dcdc3ece085a0058186138610272c70` | Merged foundation; same file tree as `rafiq/foundation`. |

Reuse the engine and native workflow editor. Keep the new production UI, persistence, job handling and media editing under `rafiq/`, outside upstream core. The feature branch targets `develop`; no existing branch is overwritten or merged automatically.

## First architecture

| Layer | Choice | Why |
| --- | --- | --- |
| Browser | HTML/CSS/JavaScript, Arabic RTL and English LTR | No frontend build or heavy framework needed for a local production workspace. |
| Application API | FastAPI, separate lightweight environment | Existing Python ecosystem and explicit project/job interfaces. |
| Persistence | SQLite WAL plus UUID media files | Durable local work, revision conflict detection, inspectable backups. |
| Execution | One worker, serial jobs | Avoid competing model loads on one GPU and uncontrolled retries. |
| Generation | Loopback ComfyUI prompt/history/upload/view APIs | Uses our own model execution and retains the original workflow editor. |
| Editing | FFmpeg / ffprobe | Real MP4 assembly with consistent codecs, resolution and audio tracks. |
| Speech | Optional separate offline Chatterbox process; recorded audio import | Keeps large/fragile speech dependencies outside the studio environment. |

Quotes contain immutable project/scene snapshots, expire after ten minutes and bind to a revision. Approval consumes a quote once, with repeated approvals returning the same job. Worker claim and waiting-job cancellation use transactional state changes. Restarted jobs become interrupted; no unseen duplicate inference is submitted.

Generated takes require explicit selection before film assembly. Manifests preserve seed, graph, project snapshot, prompt ID, timing, outcome and provenance. A failed engine never substitutes a synthetic preview. Render-time measurements inform later similar estimates; energy prices and whole-system watts are user inputs.

## Stages and acceptance gates

| Stage | Deliverable / acceptance gate | Status |
| --- | --- | --- |
| First workspace | Persistent bilingual app, example chapter opening, real imports/exports, no paid services | Implemented; API and browser checks passed. |
| First neural shot | A real 1-second smoke shot, then a 5-second 20-step shot; record model hashes, hardware, runtime and review output | Wan 2.1 passed both on a free T4 at 320×192 on 23 November. Visual quality is not approved; see the benchmark record. |
| Identity continuity | Approve character/location sheets; compare individual, two-person and group takes; evaluate model-specific references/LoRAs and multi-shot LTX workflow | Pending approved references and independent continuity tests. |
| Arabic dialogue | Listen to every speaker, test pronunciation and voice similarity, fit duration, then evaluate lip sync | Recorded import works; experimental speech adapter awaits weights and listening tests. |
| Chapter sequence | Accept several short takes, assemble one minute, review cuts/audio, then extend to the complete chapter | Technical MP4 assembly verified; artistic/neural production pending. |
| Commercial service | Authentication, tenant storage, encrypted secrets, GPU queue, per-user quotas, payment limits and operational monitoring | Architecture follow-up, not implemented in local MVP. |

For commercial growth, replace SQLite with PostgreSQL, media paths with object storage, and the single executor with a durable queue plus GPU workers. Keep project versions and render manifests stable during that change. Add authenticated worker leases, idempotent submissions and reconciliation before introducing a paid provider. A cloud worker should be our ComfyUI/model runtime, with runtime/idle/shutdown costs included in a quote and a user-approved spending ceiling before provisioning. No provisioning/billing adapter exists in the MVP.

The laptop can remain the studio/editing client while a future approved GPU machine handles generation. Do not expose this single-user local server as a commercial multiuser site. A static frontend publication would not provide its Python backend, model execution or media processing, so this iteration is delivered as a runnable repository application.

## First chapter production

The seed project contains six draft shots totaling 33 planned seconds: courtyard, Hamza's entrance, the bird, the father's answer, Othman/Nizar's entrance, and the group. It is an opening treatment based on the saved first-chapter draft, not an adaptation of the entire chapter. Appearance/wardrobe are editable fictional production choices. The seed does not contain the complete unpublished book.

The first real GPU gate uses a single character without dialogue. Next comes two characters conditioned on one approved composed reference image. The four-character wide shot is deferred until those pass. Off-screen dialogue and reaction shots can reduce lip-sync demands during the first edit. Visual continuity needs human review; seeds and saved descriptions alone cannot guarantee it.

## Version 0.2 — 23 November 2026

Implemented file-based handoff between the lightweight laptop studio and an interactive GPU notebook/owned GPU machine. One-scene request ZIPs preserve visual settings and a hashed I2V image without carrying the entire book or voice library. Result ZIPs return the MP4 and render measurements to the original job; imports are atomic, project-scoped and repeat-safe. The existing explicit take-selection step remains required.

This is an additional path to neural acceptance tests, not a hosted GPU service. It leaves external HTTP engines and paid provisioning disabled. The interactive runner retains its job database and media so a retry cannot silently resubmit an already recorded prompt; successful output can be repackaged without inference. Laptop cost estimates exclude these external-device measurements. The complete portable ZIP cycle still needs real GPU acceptance, independently of the shared worker's successful Wan 2.1 benchmark.

## First GPU execution — 23 November 2026

[Real T4 results](GPU_BENCHMARK_2026-11-23.md) now document 1.0625-second and 5.0625-second Wan 2.1 MP4 outputs, source/model hashes, device measurements and visual limits. The actual run exposed and corrected the native SaveVideo API format and unnecessary CPU text encoding. Windows CI now checks real native H.264 saving. The low-resolution output is not approved 3D production footage; identity, sound, higher resolution, I2V and longer sequences remain separate gates. User download from Colab is pending because automated media transfer was blocked.
