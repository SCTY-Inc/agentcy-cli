"""DSPy modules for persona-based chat."""

from __future__ import annotations

import dspy


class PersonaSignature(dspy.Signature):
    """Respond as a given persona."""

    persona: str = dspy.InputField(desc="Full persona definition and context")
    message: str = dspy.InputField(desc="User message to respond to")
    response: str = dspy.OutputField(desc="In-character response from the persona")


class PersonaChat(dspy.Module):
    """A persona-aware chat module."""

    def __init__(self, persona_prompt: str):
        super().__init__()
        self.persona_prompt = persona_prompt
        self.respond = dspy.ChainOfThought(PersonaSignature)

    def forward(self, message: str) -> dspy.Prediction:
        """Generate a response as the persona."""
        return self.respond(persona=self.persona_prompt, message=message)


class PersonaConsistency(dspy.Signature):
    """Evaluate if a response is consistent with persona traits."""

    persona: str = dspy.InputField(desc="Persona definition with traits and voice")
    response: str = dspy.InputField(desc="Response to evaluate")
    consistent: bool = dspy.OutputField(desc="True if response matches persona")
    reasoning: str = dspy.OutputField(desc="Brief explanation of consistency assessment")
