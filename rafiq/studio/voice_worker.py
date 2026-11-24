"""Optional, isolated Chatterbox worker. Load existing cached weights offline."""
import argparse
import json
import os
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import torch
import torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    torch.manual_seed(request["seed"])
    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda" if torch.cuda.is_available() else "cpu")
    clips = []
    for line in request["lines"]:
        clips.append(model.generate(line["text"], language_id=line["language"], audio_prompt_path=line["reference"]))
        clips.append(torch.zeros(1, int(model.sr * 0.25)))
    torchaudio.save(str(args.output), torch.cat(clips, dim=-1), model.sr)


if __name__ == "__main__":
    main()
