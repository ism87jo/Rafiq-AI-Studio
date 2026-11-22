# Model review — 22 November 2026

This is a selection for first tests, not a claim that every available model was benchmarked. No model weights were present in the development environment and no neural benchmark has passed yet.

| Candidate | License and operation | Published hardware information | Decision |
| --- | --- | --- | --- |
| Wan 2.2 TI2V 5B | Apache 2.0; native text/image video, without generated sound in this preset | ComfyUI documents an 8GB offloading configuration. Wan's own reference CLI documents 24GB for its configuration. These are different execution paths, not equivalent speed promises. | First studio preset; GPU acceptance pending. |
| Wan 2.1 T2V 1.3B | Apache 2.0; smaller text-video baseline | Official ComfyUI guide describes an 8GB configuration. | Lightweight first notebook test; lower visual ambition. |
| LTX-2.5 | Open weights under the LTX-2.x Community License; inference code Apache 2.0. Native synchronized audio/video and multishot capabilities. | LTX Desktop recommends 24GB+ NVIDIA VRAM. The BF16 Python quick-start stack is about 66GiB of files; Desktop recommends 100GB+ free disk. Quantized workflows have different requirements. | Next quality/audio candidate after measuring hardware; not a selectable implemented preset yet. |
| HunyuanVideo 1.5 | Custom community terms with territory restrictions including EU/UK/South Korea exclusions | Project documents 14GB minimum with offload. | Not the default for a platform intended to expand internationally. |

The current LTX-2.x license text is dated 11 August 2026 and amended 11 November 2026. It requires a paid commercial agreement for entities with annual revenue of at least USD 10 million, subject to its terms and noncommercial carve-out. It also contains use, distribution and provenance obligations; it is not an Apache license for the weights. Recheck the exact revision and accompanying encoders/adapters before using or redistributing a bundle.

## Primary sources

- [ComfyUI Wan 2.2 installation and workflow](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [Wan 2.2 reference CLI and license](https://github.com/Wan-Video/Wan2.2)
- [ComfyUI Wan 2.1 guide](https://docs.comfy.org/tutorials/video/wan/wan-video)
- [LTX-2.5 native ComfyUI guide](https://docs.comfy.org/tutorials/video/ltx/ltx-2-5)
- [LTX reference code and quick start](https://github.com/Lightricks/LTX-2)
- [Exact LTX-2.x license text](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x)
- [LTX Desktop hardware guidance](https://github.com/Lightricks/LTX-Desktop#system-requirements)
- [HunyuanVideo 1.5 repository](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5)

## Implemented model file mapping

| Preset | File | Relative ComfyUI folder |
| --- | --- | --- |
| Wan 2.2 5B | `wan2.2_ti2v_5B_fp16.safetensors` | `models/diffusion_models/` |
| Wan 2.2 5B | `wan2.2_vae.safetensors` | `models/vae/` |
| Both | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `models/text_encoders/` |
| Wan 2.1 1.3B | `wan2.1_t2v_1.3B_fp16.safetensors` | `models/diffusion_models/` |
| Wan 2.1 1.3B | `wan_2.1_vae.safetensors` | `models/vae/` |

Use the official guide's linked Comfy-Org repositories for downloads. Every model must be checked independently, including encoder/VAE provenance. No model is automatically fetched by the studio.

The Wan 2.2 graph's loader filenames, sampling shift 8, `uni_pc` / `simple` sampler, native latent node and frame-rate choice were compared with [the official template](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_5B_ti2v.json), Git blob `634303feba82471ef3df3356178de4c037ae213e`. API syntax was checked against the native node implementations in this checkout. This verifies graph construction, not GPU execution.

Before calling a preset hardware-supported, retain source commit, weight repository revision, SHA-256 hashes, driver/device/RAM/VRAM, dimensions, frames, steps, elapsed time and output review. The notebook records resolved model revisions and hashes; no actual hashes can be claimed until those files exist.

## Arabic speech

[Chatterbox Multilingual](https://github.com/resemble-ai/chatterbox) supports Arabic and is MIT licensed, but the current repository states it has been retired from active maintenance. The optional local worker is experimental and unverified with weights. Keep it isolated and review every line. Importing recorded dialogue works today through FFmpeg.

[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) has Apache-licensed code and ten listed base languages; Arabic is not in that base language list. Do not advertise it as native Arabic without a separately evaluated adaptation. Arabic fine-tunes such as A3S need their own quality, provenance and license review before selection.

Free Colab resources are dynamic and not guaranteed. The [Colab FAQ](https://research.google.com/colaboratory/faq.html) restricts free users from bypassing the notebook UI for web UI generation. Our notebook runs an interactive code test with a loopback engine; it does not provide hosted studio access or remote workers.
