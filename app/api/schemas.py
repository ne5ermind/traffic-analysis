

from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from .common import STATUSES

class SceneIn(BaseModel):
    video_id: str
    name: str = Field(min_length=1, max_length=120)
    geometry: dict

class RunIn(BaseModel):
    scene_id: str | None = None
    video_id: str | None = None
    model: str | None = None
    model_secondary: str | None = None
    profile: Literal["fast", "ensemble"] = "fast"
    sample_fps: float = Field(default=6, ge=2, le=12)
    topology: Literal["auto", "three_way", "four_way"] = "auto"
    tracker: str = "supervision-bytetrack"
    lighting: Literal["day", "night", "auto"] = "auto"
    night_model: str | None = None

    @field_validator("tracker")
    @classmethod
    def tracker_allowed(cls, v):
        if v not in ("supervision-bytetrack", "bytetrack.yaml", "botsort.yaml"):
            raise ValueError("Неизвестный трекер")
        return v

    @model_validator(mode="after")
    def tracker_matches_models(self):
        if (self.model_secondary is not None and "profile" not in self.model_fields_set
                and self.tracker == "supervision-bytetrack"):
            # Clients of the original API supplied the second model without a profile.
            self.profile = "ensemble"
        if self.tracker != "supervision-bytetrack" and self.night_model:
            raise ValueError("Ночная модель требует supervision-bytetrack")
        if self.tracker != "supervision-bytetrack" and (self.profile != "fast" or self.model_secondary):
            raise ValueError("Старые трекеры поддерживают только один YOLO")
        if self.tracker == "supervision-bytetrack" and self.profile == "fast" and self.model_secondary:
            raise ValueError("Быстрый режим использует одну модель; выберите режим ансамбля")
        return self

class TopologyIn(BaseModel):
    topology: Literal["auto", "three_way", "four_way"]

class RunUpdate(BaseModel):
    action: Literal["cancel", "set_topology"]
    topology: Literal["auto", "three_way", "four_way"] | None = None

    @model_validator(mode="after")
    def topology_required(self):
        if self.action == "set_topology" and self.topology is None:
            raise ValueError("Для set_topology нужно указать topology")
        return self

class EventIn(BaseModel):
    category: Literal["pedestrian", "bicycle", "car", "motorcycle", "bus", "truck"]
    from_direction: str
    to_direction: str
    time_s: float = Field(ge=0, allow_inf_nan=False)
    start_s: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    status: str = "confirmed"
    reason: str = ""

    @field_validator("status")
    @classmethod
    def status_allowed(cls, v):
        if v not in STATUSES:
            raise ValueError("Недопустимый статус")
        return v

class EventEdit(EventIn):
    id: str
    version: int = Field(ge=1)

