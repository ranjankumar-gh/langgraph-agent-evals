def test_pinned_langgraph_version():
    from importlib.metadata import version

    assert version("langgraph") == "1.2.12"
