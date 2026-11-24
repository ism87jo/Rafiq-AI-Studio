from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Character(Record):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    wardrobe: str = Field(default="", max_length=2000)
    reference_asset_id: str | None = None
    voice_asset_id: str | None = None
    voice_notes: str = Field(default="", max_length=1000)


class Location(Record):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    reference_asset_id: str | None = None


class Dialogue(Record):
    character_id: str
    text: str = Field(max_length=4000)
    language: Literal["ar", "en"] = "ar"


class Scene(Record):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(default="", max_length=12000)
    notes: str = Field(default="", max_length=12000)
    seconds: float = Field(default=5, ge=1, le=60)
    seed: int = Field(default=42, ge=0, le=2**53 - 1)
    mode: Literal["text", "image"] = "text"
    character_ids: list[str] = Field(default_factory=list, max_length=30)
    location_id: str | None = None
    reference_asset_id: str | None = None
    use_still: bool = False
    video_asset_id: str | None = None
    audio_asset_id: str | None = None
    dialogue: list[Dialogue] = Field(default_factory=list, max_length=100)


class RenderSettings(Record):
    preset: Literal["wan22-5b", "wan21-1.3b"] = "wan22-5b"
    width: int = Field(default=640, ge=64, le=1920, multiple_of=32)
    height: int = Field(default=352, ge=64, le=1088, multiple_of=32)
    fps: int = Field(default=24, ge=8, le=30)
    steps: int = Field(default=20, ge=1, le=100)
    cfg: float = Field(default=5, ge=0, le=20)
    negative_prompt: str = Field(default="text, watermark, distorted faces, extra limbs, flicker", max_length=4000)
    electricity_usd_kwh: float | None = Field(default=None, ge=0, le=10)
    system_watts: float | None = Field(default=None, gt=0, le=5000)
    assumed_render_seconds: float | None = Field(default=None, gt=0, le=86400)


class Project(Record):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    revision: int = Field(default=1, ge=1)
    title: str = Field(min_length=1, max_length=200)
    style: Literal["3d", "realistic", "anime"] = "3d"
    script: str = Field(default="", max_length=150000)
    characters: list[Character] = Field(default_factory=list, max_length=100)
    locations: list[Location] = Field(default_factory=list, max_length=100)
    scenes: list[Scene] = Field(default_factory=list, max_length=500)
    settings: RenderSettings = Field(default_factory=RenderSettings)

    @model_validator(mode="after")
    def valid_references(self):
        for items in (self.characters, self.locations, self.scenes):
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate character, location or scene ID")
        characters = {x.id for x in self.characters}
        locations = {x.id for x in self.locations}
        for scene in self.scenes:
            if set(scene.character_ids) - characters:
                raise ValueError("Scene references an unknown character")
            if scene.location_id and scene.location_id not in locations:
                raise ValueError("Scene references an unknown location")
            if any(line.character_id not in characters for line in scene.dialogue):
                raise ValueError("Dialogue references an unknown character")
        return self
