from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
import shlex


BoxType = Literal["obj", "msg", "text", "floatatom", "symbolatom"]


def tokenize_pd_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return shlex.split(text)


@dataclass(slots=True)
class PdObject:
    object_id: str
    box_type: BoxType
    x: int
    y: int
    text: str = ""
    receive_symbol: str | None = None

    def is_controllable(self) -> bool:
        return self.box_type != "text"

    def content_tokens(self) -> list[str]:
        return tokenize_pd_text(self.text)

    def canvas_command(self) -> list[str]:
        if self.box_type in {"obj", "msg", "text"}:
            return [self.box_type, str(self.x), str(self.y), *self.content_tokens()]
        if self.box_type == "floatatom":
            return [
                "floatatom",
                str(self.x),
                str(self.y),
                "5",
                "0",
                "0",
                "0",
                "-",
                "-",
                "-",
            ]
        if self.box_type == "symbolatom":
            return [
                "symbolatom",
                str(self.x),
                str(self.y),
                "10",
                "0",
                "0",
                "0",
                "-",
                "-",
                "-",
            ]
        raise ValueError(f"Unsupported box type: {self.box_type}")

    def describe(self) -> str:
        if self.box_type in {"floatatom", "symbolatom"}:
            return self.box_type
        return self.text


@dataclass(slots=True)
class PdConnection:
    source_id: str
    outlet_index: int
    destination_id: str
    inlet_index: int


@dataclass(slots=True)
class PatchLayout:
    object_indices: dict[str, int]
    proxy_indices: dict[str, int]
    commands: list[list[str]]


@dataclass(slots=True)
class PatchModel:
    patch_name: str = "pd-mcp-canvas"
    objects: list[PdObject] = field(default_factory=list)
    connections: list[PdConnection] = field(default_factory=list)
    next_id: int = 1

    def add_object(self, box_type: BoxType, x: int, y: int, text: str = "") -> PdObject:
        object_id = f"obj-{self.next_id}"
        self.next_id += 1
        receive_symbol = f"pdmcp-{object_id}"
        obj = PdObject(
            object_id=object_id,
            box_type=box_type,
            x=x,
            y=y,
            text=text,
            receive_symbol=receive_symbol,
        )
        self.objects.append(obj)
        return obj

    def get_object(self, object_id: str) -> PdObject:
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        raise KeyError(f"Unknown object_id: {object_id}")

    def remove_object(self, object_id: str) -> PdObject:
        obj = self.get_object(object_id)
        self.objects = [item for item in self.objects if item.object_id != object_id]
        self.connections = [
            conn
            for conn in self.connections
            if conn.source_id != object_id and conn.destination_id != object_id
        ]
        return obj

    def connect(
        self,
        source_id: str,
        outlet_index: int,
        destination_id: str,
        inlet_index: int,
    ) -> PdConnection:
        self.get_object(source_id)
        self.get_object(destination_id)
        conn = PdConnection(
            source_id=source_id,
            outlet_index=outlet_index,
            destination_id=destination_id,
            inlet_index=inlet_index,
        )
        if conn not in self.connections:
            self.connections.append(conn)
        return conn

    def disconnect(
        self,
        source_id: str,
        outlet_index: int,
        destination_id: str,
        inlet_index: int,
    ) -> bool:
        before = len(self.connections)
        self.connections = [
            conn
            for conn in self.connections
            if not (
                conn.source_id == source_id
                and conn.outlet_index == outlet_index
                and conn.destination_id == destination_id
                and conn.inlet_index == inlet_index
            )
        ]
        return len(self.connections) != before

    def clear(self) -> None:
        self.objects = []
        self.connections = []
        self.next_id = 1

    def build_layout(self) -> PatchLayout:
        object_indices: dict[str, int] = {}
        proxy_indices: dict[str, int] = {}
        commands: list[list[str]] = [["clear"]]
        next_index = 0

        for obj in self.objects:
            if obj.is_controllable():
                proxy_x = max(10, obj.x - 18)
                proxy_y = max(10, obj.y - 25)
                proxy_indices[obj.object_id] = next_index
                commands.append(["obj", str(proxy_x), str(proxy_y), "r", obj.receive_symbol or ""])
                next_index += 1

            object_indices[obj.object_id] = next_index
            commands.append(obj.canvas_command())
            next_index += 1

        for obj in self.objects:
            if obj.object_id in proxy_indices:
                commands.append(
                    [
                        "connect",
                        str(proxy_indices[obj.object_id]),
                        "0",
                        str(object_indices[obj.object_id]),
                        "0",
                    ]
                )

        for conn in self.connections:
            commands.append(
                [
                    "connect",
                    str(object_indices[conn.source_id]),
                    str(conn.outlet_index),
                    str(object_indices[conn.destination_id]),
                    str(conn.inlet_index),
                ]
            )

        return PatchLayout(
            object_indices=object_indices,
            proxy_indices=proxy_indices,
            commands=commands,
        )

    def snapshot(self) -> dict:
        layout = self.build_layout()
        return {
            "patch_name": self.patch_name,
            "object_count": len(self.objects),
            "connection_count": len(self.connections),
            "objects": [
                {
                    "id": obj.object_id,
                    "box_type": obj.box_type,
                    "text": obj.describe(),
                    "position": [obj.x, obj.y],
                    "receive_symbol": obj.receive_symbol,
                    "pd_index": layout.object_indices[obj.object_id],
                }
                for obj in self.objects
            ],
            "connections": [
                {
                    "source_id": conn.source_id,
                    "outlet_index": conn.outlet_index,
                    "destination_id": conn.destination_id,
                    "inlet_index": conn.inlet_index,
                }
                for conn in self.connections
            ],
        }
