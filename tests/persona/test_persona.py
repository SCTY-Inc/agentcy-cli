"""Tests for Persona class."""

import tempfile
from pathlib import Path

from agentcy.persona.persona import Persona, Voice


def test_persona_create():
    """Test basic persona creation."""
    p = Persona(name="test", traits=["helpful"])
    assert p.name == "test"
    assert "helpful" in p.traits
    assert p.version == 1


def test_persona_to_prompt():
    """Test prompt generation."""
    p = Persona(
        name="scientist",
        description="A research scientist",
        traits=["curious", "methodical"],
        voice=Voice(tone="academic"),
    )
    prompt = p.to_prompt()
    assert "research scientist" in prompt
    assert "curious" in prompt
    assert "academic" in prompt


def test_persona_save_load():
    """Test saving and loading personas."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.yaml"

        original = Persona(
            name="test",
            description="Test persona",
            traits=["trait1", "trait2"],
        )
        original.save(path)

        loaded = Persona.load(path)
        assert loaded.name == original.name
        assert loaded.traits == original.traits


def test_persona_merge():
    """Test merging two personas."""
    p1 = Persona(name="a", traits=["curious"])
    p2 = Persona(name="b", traits=["funny"])

    merged = p1.merge_traits(p2)
    assert "curious" in merged.traits
    assert "funny" in merged.traits
    assert merged.name == "a+b"
