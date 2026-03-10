"""Verify package imports and basic setup."""

import pytest  # pyright: ignore[reportMissingImports]


def test_veritas_imports():
    """Package can be imported and exposes version."""
    import veritas

    assert hasattr(veritas, "__version__")
    assert veritas.__version__.startswith("0.1")


def test_modules_importable():
    """All planned modules can be imported."""
    import veritas.core
    import veritas.sinks
    import veritas.pricing
    import veritas.utils

    assert veritas.core is not None
    assert veritas.sinks is not None
    assert veritas.pricing is not None
    assert veritas.utils is not None


def test_track_importable():
    """track decorator is importable from top-level."""
    from veritas import track

    assert callable(track)
