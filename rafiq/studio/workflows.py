import math


PRESETS = {
    "wan22-5b": {
        "name": "Wan 2.2 TI2V 5B", "license": "Apache-2.0", "text": True, "image": True,
        "model": "wan2.2_ti2v_5B_fp16.safetensors", "vae": "wan2.2_vae.safetensors",
        "encoder": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "fps": 24,
        "source": "https://docs.comfy.org/tutorials/video/wan/wan2_2",
        "status": "integration-unverified-on-gpu",
    },
    "wan21-1.3b": {
        "name": "Wan 2.1 T2V 1.3B", "license": "Apache-2.0", "text": True, "image": False,
        "model": "wan2.1_t2v_1.3B_fp16.safetensors", "vae": "wan_2.1_vae.safetensors",
        "encoder": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "fps": 16,
        "source": "https://docs.comfy.org/tutorials/video/wan/wan-video",
        "status": "integration-unverified-on-gpu",
    },
}

STYLES = {
    "3d": "Stylized 3D animated family film, soft cinematic lighting, expressive stylized characters, detailed materials",
    "realistic": "Photorealistic cinematic live action, natural skin texture, realistic lighting",
    "anime": "Hand drawn anime style, clean line art, consistent character design, cinematic composition",
}


def scene_prompt(project, scene):
    parts = [STYLES[project["style"]], scene["prompt"]]
    for character in project["characters"]:
        if character["id"] in scene["character_ids"]:
            parts.append(f"Character {character['name']}: {character['description']}. Clothing: {character['wardrobe']}.")
    for location in project["locations"]:
        if location["id"] == scene["location_id"]:
            parts.append(f"Location: {location['description']}")
    return "\n".join(part for part in parts if part)


def frame_count(seconds, fps):
    return max(5, math.ceil((seconds * fps - 1) / 4) * 4 + 1)


def build_graph(project, scene, reference_name=None, prefix="rafiq/shot"):
    settings = project["settings"]
    preset = PRESETS[settings["preset"]]
    if scene["mode"] == "image" and not preset["image"]:
        raise ValueError("This preset supports text only. Choose Wan 2.2 5B for image-to-video.")
    if scene["mode"] == "image" and not reference_name:
        raise ValueError("Image-to-video requires a scene reference image.")
    frames = frame_count(scene["seconds"], settings["fps"])

    def node(name, **inputs):
        return {"class_type": name, "inputs": inputs}

    graph = {
        "1": node("UNETLoader", unet_name=preset["model"], weight_dtype="default"),
        "2": node("CLIPLoader", clip_name=preset["encoder"], type="wan", device="default"),
        "3": node("VAELoader", vae_name=preset["vae"]),
        "4": node("CLIPTextEncode", text=scene_prompt(project, scene), clip=["2", 0]),
        "5": node("CLIPTextEncode", text=settings["negative_prompt"], clip=["2", 0]),
        "7": node("ModelSamplingSD3", model=["1", 0], shift=8),
        "8": node("KSampler", model=["7", 0], seed=scene["seed"], steps=settings["steps"],
                  cfg=settings["cfg"], sampler_name="uni_pc", scheduler="simple", positive=["4", 0],
                  negative=["5", 0], latent_image=["6", 0], denoise=1),
        "9": node("VAEDecode", samples=["8", 0], vae=["3", 0]),
        "10": node("CreateVideo", images=["9", 0], fps=settings["fps"]),
        "11": node("SaveVideo", video=["10", 0], filename_prefix=prefix,
                   format={"format": "mp4", "codec": {"codec": "h264"}}),
    }
    inputs = dict(width=settings["width"], height=settings["height"], length=frames, batch_size=1)
    if settings["preset"] == "wan22-5b":
        graph["6"] = node("Wan22ImageToVideoLatent", vae=["3", 0], **inputs)
        if scene["mode"] == "image":
            graph["12"] = node("LoadImage", image=reference_name)
            graph["6"]["inputs"]["start_image"] = ["12", 0]
    else:
        graph["6"] = node("EmptyHunyuanLatentVideo", **inputs)
    return graph


def estimate(project, scene, jobs):
    settings = project["settings"]
    signature = {key: settings[key] for key in ("preset", "width", "height", "fps", "steps", "cfg")}
    measured = []
    for job in jobs:
        if job.get("execution") == "portable":
            continue
        if job["kind"] != "generate" or job["state"] != "succeeded":
            continue
        payload = job["payload"]
        old = payload["project"]["settings"]
        same = all(old[key] == value for key, value in signature.items())
        if same and payload["scene"]["mode"] == scene["mode"] and job.get("generation_seconds"):
            measured.append(job["generation_seconds"] * scene["seconds"] / payload["scene"]["seconds"])
    seconds = sum(measured[:5]) / len(measured[:5]) if measured else settings["assumed_render_seconds"]
    watts = settings["system_watts"]
    tariff = settings["electricity_usd_kwh"]
    cost = None if seconds is None or watts is None or tariff is None else seconds / 3600 * watts / 1000 * tariff
    return dict(currency="USD", estimated_seconds=seconds, estimated_cost=cost,
                source="measured-similar-jobs" if measured else "user-assumption" if seconds else "unknown",
                sample_count=len(measured[:5]), attempts=1, provider_fee=0,
                excludes=["hardware depreciation", "storage", "retries", "voice generation"],
                output_seconds=frame_count(scene["seconds"], settings["fps"]) / settings["fps"])
