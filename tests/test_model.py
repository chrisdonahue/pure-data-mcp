from pd_mcp.model import PatchModel, tokenize_pd_text


def test_tokenize_pd_text_handles_quotes() -> None:
    assert tokenize_pd_text('pack 440 "hello world"') == ["pack", "440", "hello world"]


def test_build_layout_omits_hidden_control_receives_by_default() -> None:
    model = PatchModel()
    osc = model.add_object("obj", 40, 60, "osc~ 440")
    dac = model.add_object("obj", 160, 60, "dac~")
    model.connect(osc.object_id, 0, dac.object_id, 0)

    layout = model.build_layout()

    assert layout.commands[0] == ["clear"]
    assert any(command[-1:] == ["dac~"] for command in layout.commands)
    assert not any(command[:4] == ["obj", "22", "35", "r"] for command in layout.commands)
    assert ["connect", "0", "0", "1", "0"] in layout.commands


def test_build_layout_adds_hidden_control_receives_when_requested() -> None:
    model = PatchModel()
    osc = model.add_object("obj", 40, 60, "osc~ 440", controllable=True)
    dac = model.add_object("obj", 160, 60, "dac~")
    model.connect(osc.object_id, 0, dac.object_id, 0)

    layout = model.build_layout()

    assert any(command[-2:] == ["r", osc.receive_symbol] for command in layout.commands)
    assert ["connect", "0", "0", "1", "0"] in layout.commands
    assert ["connect", "1", "0", "2", "0"] in layout.commands


def test_remove_object_also_removes_connections() -> None:
    model = PatchModel()
    one = model.add_object("obj", 10, 10, "noise~")
    two = model.add_object("obj", 80, 10, "dac~")
    model.connect(one.object_id, 0, two.object_id, 0)

    model.remove_object(one.object_id)

    assert len(model.objects) == 1
    assert len(model.connections) == 0
