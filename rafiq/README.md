# Rafiq AI Studio

Rafiq AI Studio extends ComfyUI toward a bilingual image, video and audio workspace. This foundation adds a Windows CPU setup and a model-free startup check. The upstream web interface is available after startup.

## Windows

Install Git, PowerShell 7 and 64-bit Python 3.13 with the Windows Python launcher (`py`). From PowerShell 7:

```powershell
git clone https://github.com/ism87jo/Rafiq-AI-Studio.git
cd Rafiq-AI-Studio
git remote add upstream https://github.com/Comfy-Org/ComfyUI.git
git switch develop
./rafiq/setup.ps1
./.venv/Scripts/python.exe rafiq/smoke.py
./rafiq/start.ps1
```

Open <http://127.0.0.1:8188>. Stop the server with Ctrl+C. Setup downloads Python packages. The smoke test starts a separate CPU process, checks `GET /system_stats` and terminates the process. It requires no model weights. Before the foundation PR is merged, switch to `rafiq/foundation` to find these scripts.

## Architecture and first release

- Keep upstream updates reviewable. Fetch `upstream/master`, integrate it into a branch based on `develop` and run the Windows smoke workflow before merging.
- Keep Python inference, graph execution and the server in ComfyUI. Build the studio interface outside core using the HTTP prompt, history and output APIs and the WebSocket progress stream. Keep the packaged ComfyUI frontend available for workflow editing. Evaluate Electron Desktop packaging after browser acceptance tests.
- Start with Arabic RTL and English LTR, covering forms, keyboard navigation and mixed-direction prompts. Use versioned workflow presets and separate project metadata from generated files. Track each model's source, revision, checksum and license before enabling it.
- Validate image and audio presets independently. For video with synchronized audio, start with upstream LTX nodes and a pinned LTX-2 workflow. Verify required weights, licenses, output and GPU memory on the target device before marking the preset supported.
- Record latency and peak VRAM for each tested preset. Use existing ComfyUI offload controls and document hardware profiles. Add a remote execution adapter only after local workflows pass, with authenticated access and isolated project storage.

## Licenses

[ComfyUI core](https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE) and [ComfyUI frontend](https://github.com/Comfy-Org/ComfyUI_frontend) use GPL v3. [Comfy Desktop](https://github.com/Comfy-Org/Comfy-Desktop#license) offers AGPL v3 or later and commercial terms, with an MIT exception for its bridge types package. This repository uses the upstream core license.

[LTX-2 weights](https://huggingface.co/Lightricks/LTX-2/blob/main/LICENSE) have separate community terms. Review the license at the exact revision, its use restrictions and any commercial licensing requirements. Review each accompanying encoder, VAE, LoRA and other model artifact independently before redistribution or commercial release.

## العربية

يضيف هذا الفرع إعداد Windows على CPU واختبار إقلاع دون أوزان نماذج. ثبّت Git وPowerShell 7 وPython 3.13 بنسخة 64 بت، ثم نفّذ أوامر قسم Windows. يثبّت `setup.ps1` الاعتماديات في `.venv`، ويتحقق الاختبار من استجابة واجهة المحرك. شغّل `start.ps1` وافتح <http://127.0.0.1:8188> لواجهة ComfyUI الأصلية.

ستبدأ النسخة الأولى بواجهة عربية RTL وإنجليزية LTR وإدارة المشاريع والملفات وسجل النماذج. تُختبر مسارات الصور والصوت والفيديو كل على حدة، ويُختبر LTX-2 عبر عُقد ComfyUI الأصلية باستخدام إصدار محدد من الأوزان. يبقى التشغيل محليًا أولًا، ويُقيّم التشغيل البعيد بعد اجتياز الاختبارات المحلية. تُسجّل مدة التنفيذ وذروة استهلاك ذاكرة GPU لكل قالب معتمد.

ترخيص المحرك والواجهة GPL v3. لتطبيق Desktop شروط AGPL v3 أو أحدث وخيار تجاري، مع استثناء MIT لحزمة أنواع الجسر. لأوزان LTX-2 شروط مستقلة. راجع ترخيص الإصدار المحدد لكل ملف نموذج قبل التوزيع أو الإطلاق التجاري.
