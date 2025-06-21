from prefect import Flow

from flows import collect_public_flows


def test_collect_public_flows_returns_dict():
    flows = collect_public_flows()
    assert isinstance(flows, dict)
    # All values should be Prefect Flow objects
    for flow in flows.values():
        assert isinstance(flow, Flow)


def test_collect_public_flows_handles_import_error(monkeypatch):
    # Patch importlib.import_module to raise ImportError
    import importlib

    def fake_import_module(name):
        raise ImportError("Fake import error")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    flows = collect_public_flows()

    assert flows == {}


def test_collect_public_flows_handles_exception(monkeypatch):
    # Patch importlib.import_module to raise a generic Exception
    import importlib

    def fake_import_module(name):
        raise Exception("Generic error")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    flows = collect_public_flows()

    assert flows == {}
