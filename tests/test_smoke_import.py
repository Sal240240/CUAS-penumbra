def test_penumbra_importable():
    import penumbra  # noqa: F401
    assert penumbra.__version__
