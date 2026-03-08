from __future__ import annotations

from dataclasses import dataclass, field
import socket

from .model import PatchModel


def escape_fudi_atom(value: object) -> str:
    atom = str(value)
    atom = atom.replace("\\", "\\\\")
    atom = atom.replace(" ", "\\ ")
    atom = atom.replace(",", "\\,")
    atom = atom.replace(";", "\\;")
    atom = atom.replace("$", "\\$")
    return atom


def encode_fudi(selector: str, atoms: list[object]) -> bytes:
    parts = [escape_fudi_atom(selector), *[escape_fudi_atom(atom) for atom in atoms]]
    return (" ".join(parts) + ";\n").encode("utf-8")


@dataclass(slots=True)
class PdUdpBridge:
    host: str = "127.0.0.1"
    port: int = 5000
    _socket: socket.socket = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, selector: str, *atoms: object) -> None:
        packet = encode_fudi(selector, list(atoms))
        self._socket.sendto(packet, (self.host, self.port))

    def sync_model(self, model: PatchModel) -> dict:
        layout = model.build_layout()
        for command in layout.commands:
            selector, *atoms = command
            self.send("canvas", selector, *atoms)
        return {
            "status": "synced",
            "canvas_message_count": len(layout.commands),
            "pd_indices": layout.object_indices,
        }

    def set_dsp(self, enabled: bool) -> None:
        self.send("dsp", 1 if enabled else 0)

    def send_to_receive(self, receive_symbol: str, *atoms: object) -> None:
        if not atoms:
            atoms = ("bang",)
        self.send("send", receive_symbol, *atoms)

    def close(self) -> None:
        self._socket.close()
