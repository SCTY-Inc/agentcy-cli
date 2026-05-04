"""Brand-os: CLI-first brand operations toolkit."""

__version__ = "0.1.0"

# Core
from brand_os.core.identity import (
    BrandProfile,
    Example,
    Identity,
    Visual,
    Voice,
)
from brand_os.core.brands import (
    discover_brands,
    load_brand_config,
    load_brand_profile,
)
from brand_os.core.llm import complete, complete_json, get_provider

# Intel
from brand_os.intel import (
    detect_outliers,
    extract_hooks,
    run_intel_pipeline,
)

# Signals
from brand_os.signals import (
    append_signals,
    filter_signals,
    query_signals,
    score_relevance,
)

# Plan
from brand_os.plan import (
    activation,
    creative,
    list_campaigns,
    load_campaign,
    research,
    save_campaign,
    strategy,
)

# Produce
from brand_os.produce import (
    generate_copy,
    generate_image,
    generate_thread,
    generate_video,
)

# Eval
from brand_os.eval import (
    aggregate_learnings,
    grade_content,
    heal_content,
    load_rubric,
    parse_rubric,
)

# Publish
from brand_os.publish import (
    add_to_queue,
    clear_queue,
    get_queue,
    remove_from_queue,
)

# Monitor
from brand_os.monitor import (
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
