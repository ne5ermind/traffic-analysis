from typing import Literal
from pydantic import BaseModel, Field, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def trim(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Укажите название проекта")
        return self


class AnalysisRequest(BaseModel):
    profile: Literal["fast", "balanced", "accurate"] = "balanced"
    recalculate: bool = False


class Point(BaseModel):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)


class Zone(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["entry", "exit"]
    points: list[Point] = Field(min_length=3, max_length=40)


class Line(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=120)
    points: list[Point] = Field(min_length=2, max_length=2)


class Approach(Point):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,24}$")
    label: str = Field(min_length=1, max_length=60)


class Intersection(BaseModel):
    intersection_type: Literal["t", "y", "four_way", "multi_way", "straight"]
    center: Point
    approaches: list[Approach] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def valid_approaches(self):
        import math
        n = {"t": 3, "y": 3, "four_way": 4, "straight": 2}.get(self.intersection_type)
        if n and len(self.approaches) != n:
            raise ValueError(f"Для выбранного типа нужно подходов: {n}")
        if len({a.id for a in self.approaches}) != len(self.approaches):
            raise ValueError("Подходы должны иметь разные идентификаторы")
        angles = []
        for a in self.approaches:
            if math.hypot(a.x-self.center.x, a.y-self.center.y) < .12:
                raise ValueError("Отметьте подход дальше от центра перекрёстка")
            angle = math.degrees(math.atan2(a.x-self.center.x, self.center.y-a.y)) % 360
            if any(min(abs(angle-v), 360-abs(angle-v)) < 25 for v in angles):
                raise ValueError("Подходы слишком близки по направлению")
            angles.append(angle)
        return self


class Calibration(BaseModel):
    intersection: Intersection | None = None
    zones: list[Zone] = Field(default_factory=list, max_length=50)
    lines: list[Line] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def valid_geometry(self):
        shapes = self.zones + self.lines
        if len({s.id for s in shapes}) != len(shapes):
            raise ValueError("Идентификаторы фигур должны быть уникальными")
        for z in self.zones:
            pts = z.points
            area = sum(p.x * q.y - q.x * p.y for p, q in zip(pts, pts[1:] + pts[:1]))
            if abs(area) < 0.00001:
                raise ValueError("Зона должна иметь площадь")
        for line in self.lines:
            if line.points[0] == line.points[1]:
                raise ValueError("Линия должна иметь длину")
        return self


class Rename(BaseModel):
    name: str = Field(min_length=1, max_length=120)
