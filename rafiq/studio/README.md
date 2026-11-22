# Rafiq AI Studio · MVP 0.1

A local Arabic/English production workspace for Rafiq Al-Basira. The studio uses its own project database and talks to the included ComfyUI engine through loopback HTTP. It does not provision cloud machines or call paid video APIs.

## Start on Windows

Use Python 3.11 or newer and PowerShell 7. From the repository root:

```powershell
git switch feature/rafiq-studio-mvp
./rafiq/setup-studio.ps1
./rafiq/start-studio.ps1
```

Open <http://127.0.0.1:8787>. This installs only the lightweight studio dependencies, without PyTorch or model weights. The interface works without a GPU. FFmpeg and ffprobe must be installed and on PATH for video/audio imports and exports. On Windows, one installation option is `winget install Gyan.FFmpeg`; reopen PowerShell afterward.

Data persists in `~/RafiqAIStudio/` (`C:\Users\<you>\RafiqAIStudio` on Windows). Back up the entire folder for projects, jobs and media. Project JSON downloads preserve text/settings but do not bundle media; importing them makes a new project and clears old asset links. `RAFIQ_DATA_DIR` can select another data directory.

Linux/macOS:

```bash
python3 -m venv .studio-venv
.studio-venv/bin/python -m pip install -r rafiq/studio/requirements.txt
.studio-venv/bin/python -m rafiq.studio
```

## Generate an actual shot

The web studio and GPU engine use separate Python environments. The earlier `rafiq/setup.ps1` deliberately installs CPU PyTorch; that environment alone is **not** a GPU video setup.

1. On a suitable GPU machine, install the appropriate GPU PyTorch build and the root ComfyUI requirements following [ComfyUI installation](https://github.com/Comfy-Org/ComfyUI#installing). Do not run the CPU installer over a working GPU environment.
2. Place the selected preset's three files in the model folders listed in [the model review](../docs/MODELS.md). No weights are bundled or downloaded by the studio.
3. Start the engine with `./rafiq/start-gpu.ps1`, or run `python main.py --offline --listen 127.0.0.1 --disable-auto-launch --disable-all-custom-nodes` in the GPU environment. The engine listens on port 8188; the studio listens on 8787.
4. In the studio, check Engine & cost. Preflight checks accelerator type, native nodes, model filenames and rejects API nodes. It does not validate model quality, hash identity, available VRAM or performance.
5. Start with one short shot. Estimate, inspect the composed prompt, approve, then review the resulting MP4 before selecting it for a scene.

Only loopback ComfyUI endpoints are supported by this MVP. `RAFIQ_COMFY_URL` may select another loopback port. External engines and paid provisioning are disabled. The included `benchmark.py` can run a real shot through the same graph/worker path and produce a timing report:

```bash
python -m rafiq.studio.benchmark --preset wan22-5b --seconds 1 --steps 8 --run
```

For a weak laptop, use the prepared [interactive Colab test notebook](../notebooks/Rafiq_First_GPU_Test.ipynb) if a free GPU is available. The notebook runs code inside Colab; it does not expose the studio or create a public tunnel. It has **not yet passed a real GPU run**. Do not buy compute units for this test.

## What is working

- Arabic RTL / English LTR, project creation/editing, script editing, shot duplication/reordering, saved settings and seeds.
- Four editable character records, wardrobe descriptions, location guides, character image/voice uploads, and a six-shot first-chapter example. Appearance descriptions are fictional production proposals.
- Native Wan 2.2 5B text/image workflows and a Wan 2.1 1.3B text workflow. For I2V, the scene image is uploaded to ComfyUI and actually bound to `LoadImage` and `Wan22ImageToVideoLatent`.
- A single persistent job queue, revision-bound expiring quotes, idempotent approval, real output downloads, failure reporting and explicit take selection. Interrupted prompts are not automatically resubmitted.
- MP4 assembly using FFmpeg: storyboard order, per-scene duration, optional dialogue audio, H.264/AAC, padding, consistent resolution/fps and fast-start output. Dialogue is trimmed to scene duration. Short video holds its final frame.
- Electricity cost estimates from user-supplied watts/tariff and assumed runtime, or runtime from similar completed jobs. Unknown inputs stay unknown. Hardware depreciation, storage and retries are excluded. There is no external provider fee.

Character/location guide images are saved for planning. Only the selected scene image conditions the built-in I2V graph. Seeds and textual descriptions do not guarantee character identity. Here, **3D means the requested visual style**, not editable rigged 3D assets. The Wan presets do not generate sound or lip sync. LTX-2.5 integration, advanced visual conditioning, automatic character portraits and commercial multiuser hosting remain later stages.

## Optional offline Arabic dialogue

`voice_worker.py` is an experimental isolated Chatterbox Multilingual adapter supporting ordered per-character reference clips and Arabic/English text. Install its dependencies and cache the model in a separate environment using the [official repository](https://github.com/resemble-ai/chatterbox). Set `RAFIQ_VOICE_PYTHON` to that environment's absolute Python executable before starting the studio. The worker sets HF/Transformers offline mode and never downloads weights on a job.

Provide one voice reference per speaker. Direction notes are saved for editorial planning; the current adapter uses the reference clip, language and text. Review pronunciation and similarity. This adapter has not been tested with weights; Chatterbox's repository reports that active maintenance has ended. Recorded dialogue can be imported without installing a TTS model.

## Verification and boundaries

```bash
python -m unittest discover -s rafiq/studio/tests -v
node --check rafiq/studio/web/studio.js
```

The tests use an explicitly labelled ComfyUI protocol fixture plus real FFmpeg encodes/decodes. They do **not** demonstrate neural inference. See [the validation record](../docs/VALIDATION.md) for the separate browser export test and the blocked GPU milestone.

The default server binds to loopback. Local-session tokens, same-origin mutation checks, host validation, per-project asset checks and sanitized uploads protect the single-user workflow. This is not Internet-facing authentication or a tenant isolation system. Run one studio process per data folder. Commercial deployment requires the next architecture stages in [the implementation plan](../docs/IMPLEMENTATION.md).

The repository retains the upstream GPL-3.0 license. Model weights and optional packages have separate licenses. No model files, tokens, user data or generated media belong in Git.

## العربية

النسخة الأولى تعمل محليًا لإدارة المشاريع والسيناريو والشخصيات والأماكن والمشاهد والوسائط. احفظ المشروع، وأضف لقطة لكل مشهد، ثم افتح «الإنتاج والتصدير» لإنشاء MP4 فعلي عبر FFmpeg. أدوات التثبيت أعلاه لا تشغّل خدمة مدفوعة ولا تنزّل الأوزان.

التوليد العصبي يحتاج جهازًا مسرّعًا وأوزانًا مثبتة. جهاز ذو RAM قرابة 8GB وبطاقات رسومية قديمة مناسب لإدارة المشروع والمونتاج الخفيف؛ لا يُعتمد لتشغيل نماذج الفيديو المختارة. دفتر Colab المرفق مسار لاختبار قصير إذا توفرت جلسة GPU مجانية، وليس استضافة تجارية دائمة.

التكلفة الظاهرة تقدير للكهرباء وفق القيم التي تدخلها والقياسات المتاحة، وليست وعدًا بسعر ثابت. ثبات الشخصيات وجودة العربية ومزامنة الشفاه تحتاج تجارب مستقلة قبل إنتاج الفيلم الطويل.
