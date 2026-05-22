"""agentcy-voice - Manage, compose, test, and export AI personas.

Library usage:
    >>> from agentcy_voice import Persona
    >>> vc = Persona.load("voice/personas/tech-investor.yaml")
    >>> response = vc.chat("Should I raise now?")

    # Multi-turn conversation
    >>> with vc.conversation() as conv:
    ...     print(conv.send("Hello"))
    ...     print(conv.send("What about bootstrapping?"))

    # Synthetic user generation (for testing chatbots)
    >>> angry = Persona.load("angry-customer.yaml")
    >>> test_input = angry.as_user("asking about refund policy")
    >>> my_bot_response = my_chatbot(test_input)

    # Bootstrap new persona from description
    >>> from agentcy_voice import bootstrap_from_description
    >>> data = bootstrap_from_description("skeptical tech journalist")
    >>> journalist = Persona(**data)
"""

__version__ = "0.1.0"

from agentcy_voice.bootstrap import (
    bootstrap_from_description,
    bootstrap_from_examples,
    bootstrap_from_person,
    bootstrap_from_role,
)
from agentcy_voice.llm import LLMError
from agentcy_voice.persona import Conversation, Persona

__all__ = [
    "Persona",
    "Conversation",
    "LLMError",
    "bootstrap_from_description",
    "bootstrap_from_person",
    "bootstrap_from_role",
    "bootstrap_from_examples",
]
