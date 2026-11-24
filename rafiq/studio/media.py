import json
import shutil
import subprocess


def run_media(command, timeout=1800):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise ValueError(result.stderr[-2500:] or "Media processing failed")
    return result.stdout


def probe(path):
    if not shutil.which("ffprobe"):
        raise ValueError("Install FFmpeg (including ffprobe) and add it to PATH")
    return json.loads(run_media(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], timeout=30))


def normalize_audio(source, target):
    if not shutil.which("ffmpeg"):
        raise ValueError("Install FFmpeg and add it to PATH")
    run_media(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-vn", "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(target)], timeout=120)


def has_export_visual(scene):
    return bool(scene["video_asset_id"] or (scene.get("use_still") and scene["reference_asset_id"]))


def export_movie(store, project, work, output):
    if not project["scenes"]:
        raise ValueError("The storyboard is empty")
    if not shutil.which("ffmpeg"):
        raise ValueError("Install FFmpeg and add it to PATH")
    settings = project["settings"]
    work.mkdir(parents=True, exist_ok=True)
    files = []
    for index, scene in enumerate(project["scenes"]):
        if not has_export_visual(scene):
            raise ValueError(f"Scene has no selected video or enabled still: {scene['title']}")
        still = not scene["video_asset_id"]
        asset_id = scene["reference_asset_id"] if still else scene["video_asset_id"]
        source = store.path(asset_id, project["id"], "image" if still else "video")
        streams = [] if still else probe(source)["streams"]
        audio = store.path(scene["audio_asset_id"], project["id"], "audio") if scene["audio_asset_id"] else None
        target = work / f"part-{index:04}.mp4"
        command = ["ffmpeg", "-y", "-v", "error"]
        if still:
            command += ["-loop", "1", "-framerate", str(settings["fps"])]
        command += ["-i", str(source)]
        if audio:
            command += ["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"]
        elif any(stream["codec_type"] == "audio" for stream in streams):
            command += ["-map", "0:v:0", "-map", "0:a:0"]
        else:
            command += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v:0", "-map", "1:a:0"]
        command += ["-vf", f"scale={settings['width']}:{settings['height']}:force_original_aspect_ratio=decrease,pad={settings['width']}:{settings['height']}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={settings['fps']},tpad=stop_mode=clone:stop_duration=60",
                    "-af", "apad", "-t", str(scene["seconds"]), "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(target)]
        run_media(command)
        files.append(target)
    listing = work / "concat.txt"
    listing.write_text("\n".join(f"file '{file.name}'" for file in files), encoding="utf-8")
    run_media(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "1", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(output)])
    return probe(output)
