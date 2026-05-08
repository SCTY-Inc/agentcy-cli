"""Brand-os: CLI-first brand operations toolkit."""

__version__ = "0.1.0"

# Core
from agentcy.brand.core.identity import (
    BrandProfile,
    Example,
    Identity,
    Visual,
    Voice,
)
from agentcy.brand.core.brands import (
    discover_brands,
    load_brand_config,
    load_brand_profile,
)
from agentcy.brand.core.llm import complete, complete_json, get_provider

# Persona
from agentcy.brand.persona import (
    create_persona,
    delete_persona,
    get_persona,
    init_persona,
    list_personas,
    load_persona,
    save_persona,
)

# Intel
from agentcy.brand.intel import (
    detect_outliers,
    extract_hooks,
    run_intel_pipeline,
)

# Signals
from agentcy.brand.signals import (
    append_signals,
    filter_signals,
    query_signals,
    score_relevance,
)

# Plan
from agentcy.brand.plan import (
    activation,
    creative,
    list_campaigns,
    load_campaign,
    research,
    save_campaign,
    strategy,
)

# Produce
from agentcy.brand.produce import (
    generate_copy,
    generate_image,
    generate_thread,
    generate_video,
)

# Eval
from agentcy.brand.eval import (
    aggregate_learnings,
    grade_content,
    heal_content,
    load_rubric,
    parse_rubric,
)

# Publish
from agentcy.brand.publish import (
    add_to_queue,
    clear_queue,
    get_queue,
    remove_from_queue,
)

# Monitor
from agentcy.brand.monitor import (
    generate_report,
    send_report,
)

__all__ = [
    # Version
    "__version__",
    # Core
    "BrandProfile",
    "Example",
    "Identity",
    "Visual",
    "Voice",
    "discover_brands",
    "load_brand_config",
    "load_brand_profile",
    "complete",
    "complete_json",
    "get_provider",
    # Persona
    "create_persona",
    "delete_persona",
    "get_persona",
    "init_persona",
    "list_personas",
    "load_persona",
    "save_persona",
    # Intel
    "detect_outliers",
    "extract_hooks",
    "run_intel_pipeline",
    # Signals
    "append_signals",
    "filter_signals",
    "query_signals",
    "score_relevance",
    # Plan
    "activation",
    "creative",
    "list_campaigns",
    "load_campaign",
    "research",
    "save_campaign",
    "strategy",
    # Produce
    "generate_copy",
    "generate_image",
    "generate_thread",
    "generate_video",
    # Eval
    "aggregate_learnings",
    "grade_content",
    "heal_content",
    "load_rubric",
    "parse_rubric",
    # Publish
    "add_to_queue",
    "clear_queue",
    "get_queue",
    "remove_from_queue",
    # Monitor
    "generate_report",
    "send_report",
]
