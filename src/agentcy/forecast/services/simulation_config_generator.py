"""
Simulation Configuration Intelligent Generator
Uses LLM to automatically generate detailed simulation parameters based on
simulation requirements, document content, and graph information.
Achieves full automation without manual parameter setup.

Uses a step-by-step generation strategy to avoid failures from generating
overly long content in a single pass:
1. Generate time configuration
2. Generate event configuration
3. Generate agent configurations in batches
4. Generate platform configuration
"""

import json
import math
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .entity_reader import EntityNode

logger = get_logger('mirofish.simulation_config')

# Default daily activity pattern configuration
DEFAULT_TIMEZONE_CONFIG = {
    # Late night hours (almost no activity)
    "dead_hours": [0, 1, 2, 3, 4, 5],
    # Morning hours (gradually waking up)
    "morning_hours": [6, 7, 8],
    # Work hours
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    # Evening peak (most active)
    "peak_hours": [19, 20, 21, 22],
    # Night hours (activity declining)
    "night_hours": [23],
    # Activity multipliers
    "activity_multipliers": {
        "dead": 0.05,      # Almost no one active in the early morning
        "morning": 0.4,    # Gradually increasing in the morning
        "work": 0.7,       # Moderate during work hours
        "peak": 1.5,       # Evening peak
        "night": 0.5       # Declining late at night
    }
}


@dataclass
class AgentActivityConfig:
    """Activity configuration for a single Agent"""
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str

    # Activity level (0.0-1.0)
    activity_level: float = 0.5  # Overall activity level

    # Posting frequency (expected posts per hour)
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0

    # Active hours (24-hour format, 0-23)
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))

    # Response speed (reaction delay to trending events, in simulated minutes)
    response_delay_min: int = 5
    response_delay_max: int = 60

    # Sentiment bias (-1.0 to 1.0, negative to positive)
    sentiment_bias: float = 0.0

    # Stance (attitude toward specific topics)
    stance: str = "neutral"  # supportive, opposing, neutral, observer

    # Influence weight (determines probability of posts being seen by other Agents)
    influence_weight: float = 1.0


@dataclass
class TimeSimulationConfig:
    """Time simulation configuration (based on general daily activity patterns)"""
    # Total simulation duration (simulated hours)
    total_simulation_hours: int = 72  # Default: simulate 72 hours (3 days)

    # Time per round (simulated minutes) - default 60 minutes (1 hour), accelerated time flow
    minutes_per_round: int = 60

    # Range of Agents activated per hour
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20

    # Peak hours (evening 19-22, most active time)
    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5

    # Off-peak hours (0-5 AM, almost no activity)
    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05  # Extremely low activity in early morning

    # Morning hours
    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4

    # Work hours
    work_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    """Event configuration"""
    # Initial events (trigger events at simulation start)
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)

    # Scheduled events (events triggered at specific times)
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)

    # Trending topic keywords
    hot_topics: List[str] = field(default_factory=list)

    # Narrative direction
    narrative_direction: str = ""

    # Taxonomy-driven scenario buckets used to seed simulation coverage
    scenario_buckets: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PlatformConfig:
    """Platform-specific configuration"""
    platform: str  # twitter or reddit

    # Recommendation algorithm weights
    recency_weight: float = 0.4  # Time freshness
    popularity_weight: float = 0.3  # Popularity
    relevance_weight: float = 0.3  # Relevance

    # Viral spread threshold (interactions needed to trigger spread)
    viral_threshold: int = 10

    # Echo chamber effect strength (degree of similar opinion clustering)
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """Complete simulation parameter configuration"""
    # Basic information
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str

    # Time configuration
    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)

    # Agent configuration list
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)

    # Event configuration
    event_config: EventConfig = field(default_factory=EventConfig)

    # Platform configuration
    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None

    # LLM configuration
    llm_provider: str = ""
    llm_model: str = ""
    llm_base_url: str = ""

    # Generation metadata
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = ""  # LLM reasoning explanation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        time_dict = asdict(self.time_config)
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": time_dict,
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class SimulationConfigGenerator:
    """
    Simulation Configuration Intelligent Generator

    Uses LLM to analyze simulation requirements, document content, and graph entity
    information to automatically generate optimal simulation parameter configurations.

    Uses a step-by-step generation strategy:
    1. Generate time configuration and event configuration (lightweight)
    2. Generate Agent configurations in batches (10-20 per batch)
    3. Generate platform configuration
    """

    # Maximum context character count
    MAX_CONTEXT_LENGTH = 50000
    # Number of Agents per batch
    AGENTS_PER_BATCH = 15

    # Context truncation lengths for each step (character count)
    TIME_CONFIG_CONTEXT_LENGTH = 10000   # Time configuration
    EVENT_CONFIG_CONTEXT_LENGTH = 8000   # Event configuration
    ENTITY_SUMMARY_LENGTH = 300          # Entity summary
    AGENT_SUMMARY_LENGTH = 300           # Entity summary in Agent configuration
    ENTITIES_PER_TYPE_DISPLAY = 20       # Number of entities displayed per type

    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or Config.LLM_PROVIDER or "claude-cli").lower()
        self.llm = LLMClient(provider=self.provider)

    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
        Intelligently generate complete simulation configuration (step-by-step)

        Args:
            simulation_id: Simulation ID
            project_id: Project ID
            graph_id: Graph ID
            simulation_requirement: Simulation requirement description
            document_text: Original document content
            entities: Filtered entity list
            enable_twitter: Whether to enable Twitter
            enable_reddit: Whether to enable Reddit
            progress_callback: Progress callback function(current_step, total_steps, message)

        Returns:
            SimulationParameters: Complete simulation parameters
        """
        logger.info(f"Starting intelligent simulation config generation: simulation_id={simulation_id}, entity_count={len(entities)}")

        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = 3 + num_batches  # Time config + Event config + N Agent batches + Platform config
        current_step = 0

        def report_progress(step: int, message: str):
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")

        # 1. Build base context information
        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities
        )

        reasoning_parts = []

        # ========== Step 1: Generate time configuration ==========
        report_progress(1, "Generating time configuration...")
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(f"Time config: {time_config_result.get('reasoning', 'Success')}")

        # ========== Step 2: Generate event configuration ==========
        report_progress(2, "Generating event configuration and trending topics...")
        event_config_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(
            event_config_result,
            simulation_requirement=simulation_requirement,
            entities=entities,
        )
        reasoning_parts.append(f"Event config: {event_config_result.get('reasoning', 'Success')}")
        reasoning_parts.append(f"Scenario buckets: {len(event_config.scenario_buckets)}")

        # ========== Steps 3-N: Generate Agent configurations in batches ==========
        all_agent_configs = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]

            report_progress(
                3 + batch_idx,
                f"Generating Agent configs ({start_idx + 1}-{end_idx}/{len(entities)})..."
            )

            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement
            )
            all_agent_configs.extend(batch_configs)

        reasoning_parts.append(f"Agent config: successfully generated {len(all_agent_configs)}")

        # ========== Assign publisher Agents to initial posts ==========
        logger.info("Assigning suitable publisher Agents to initial posts...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len([p for p in event_config.initial_posts if p.get("poster_agent_id") is not None])
        reasoning_parts.append(f"Initial post assignment: {assigned_count} posts assigned to publishers")

        # ========== Final step: Generate platform configuration ==========
        report_progress(total_steps, "Generating platform configuration...")
        twitter_config = None
        reddit_config = None

        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5
            )

        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6
            )

        # Build final parameters
        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_provider=self.provider,
            llm_model=self.provider,
            llm_base_url="",
            generation_reasoning=" | ".join(reasoning_parts)
        )

        logger.info(f"Simulation config generation complete: {len(params.agent_configs)} Agent configs")

        return params

    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode]
    ) -> str:
        """Build LLM context, truncated to maximum length"""

        # Entity summary
        entity_summary = self._summarize_entities(entities)

        # Build context
        context_parts = [
            f"## Simulation Requirement\n{simulation_requirement}",
            f"\n## Entity Information ({len(entities)} total)\n{entity_summary}",
        ]

        current_length = sum(len(p) for p in context_parts)
        remaining_length = self.MAX_CONTEXT_LENGTH - current_length - 500  # Reserve 500 chars margin

        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...(document truncated)"
            context_parts.append(f"\n## Original Document Content\n{doc_text}")

        return "\n".join(context_parts)

    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """Generate entity summary"""
        lines = []

        # Group by type
        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)

        for entity_type, type_entities in by_type.items():
            lines.append(f"\n### {entity_type} ({len(type_entities)} total)")
            # Use configured display count and summary length
            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                summary_preview = (e.summary[:summary_len] + "...") if len(e.summary) > summary_len else e.summary
                lines.append(f"- {e.name}: {summary_preview}")
            if len(type_entities) > display_count:
                lines.append(f"  ... and {len(type_entities) - display_count} more")

        return "\n".join(lines)

    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """LLM call with retry logic and JSON repair"""
        import re

        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                content = self.llm.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1),
                )

                # Try to parse JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed (attempt {attempt+1}): {str(e)[:80]}")

                    # Try to fix JSON
                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed

                    last_error = e

            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(2 * (attempt + 1))

        raise last_error or Exception("LLM call failed")

    def _fix_truncated_json(self, content: str) -> str:
        """Fix truncated JSON"""
        content = content.strip()

        # Count unclosed brackets
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')

        # Check for unclosed strings
        if content and content[-1] not in '",}]':
            content += '"'

        # Close brackets
        content += ']' * open_brackets
        content += '}' * open_braces

        return content

    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Try to fix configuration JSON"""
        import re

        # Fix truncated content
        content = self._fix_truncated_json(content)

        # Extract JSON portion
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()

            # Remove newlines within strings
            def fix_string(match):
                s = match.group(0)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = re.sub(r'\s+', ' ', s)
                return s

            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)

            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                # Try removing all control characters
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                try:
                    return json.loads(json_str)
                except (json.JSONDecodeError, ValueError):
                    pass

        return None

    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """Generate time configuration"""
        context_truncated = context[:self.TIME_CONFIG_CONTEXT_LENGTH]

        max_agents_allowed = max(1, int(num_entities * 0.9))

        prompt = f"""Based on the following simulation requirements, generate time simulation configuration.

{context_truncated}

## Task
Please generate a time configuration JSON.

### General Principles (for reference only, adjust flexibly based on specific events and participant groups):
- Follow typical daily activity patterns for the target user population
- 0-5 AM: almost no activity (activity multiplier 0.05)
- 6-8 AM: gradually increasing activity (activity multiplier 0.4)
- 9 AM-6 PM: moderate activity during work hours (activity multiplier 0.7)
- 7-10 PM: peak activity period (activity multiplier 1.5)
- After 11 PM: declining activity (activity multiplier 0.5)
- General pattern: low activity in early morning, gradually increasing in morning, moderate during work hours, peak in evening
- **Important**: The example values below are for reference only. You should adjust specific time periods based on the nature of the event and characteristics of participant groups.
  - Example: Student groups may peak at 9-11 PM; media may be active all day; official institutions only during work hours
  - Example: Breaking news may cause late-night discussions, off_peak_hours can be shortened accordingly

### Return JSON format (no markdown)

Example:
{{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 50,
    "peak_hours": [19, 20, 21, 22],
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "reasoning": "Explanation of time configuration for this event"
}}

Field descriptions:
- total_simulation_hours (int): Total simulation duration, 24-168 hours; shorter for breaking events, longer for sustained topics
- minutes_per_round (int): Duration per round, 30-120 minutes, recommended 60 minutes
- agents_per_hour_min (int): Minimum Agents activated per hour (range: 1-{max_agents_allowed})
- agents_per_hour_max (int): Maximum Agents activated per hour (range: 1-{max_agents_allowed})
- peak_hours (int array): Peak hours, adjust based on event participant groups
- off_peak_hours (int array): Off-peak hours, typically late night/early morning
- morning_hours (int array): Morning hours
- work_hours (int array): Work hours
- reasoning (string): Brief explanation of why this configuration was chosen"""

        system_prompt = "You are a social media simulation expert. Return pure JSON format. Time configuration should follow realistic daily activity patterns for the target population."

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"Time config LLM generation failed: {e}, using default config")
            return self._get_default_time_config(num_entities)

    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """Get default time configuration (general daily patterns)"""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,  # 1 hour per round, accelerated time flow
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": "Using default daily activity pattern configuration (1 hour per round)"
        }

    def _parse_time_config(self, result: Dict[str, Any], num_entities: int) -> TimeSimulationConfig:
        """Parse time configuration result and validate agents_per_hour values do not exceed total agent count"""
        # Get raw values
        agents_per_hour_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        agents_per_hour_max = result.get("agents_per_hour_max", max(5, num_entities // 5))

        # Validate and correct: ensure values do not exceed total agent count
        if agents_per_hour_min > num_entities:
            logger.warning(f"agents_per_hour_min ({agents_per_hour_min}) exceeds total Agent count ({num_entities}), corrected")
            agents_per_hour_min = max(1, num_entities // 10)

        if agents_per_hour_max > num_entities:
            logger.warning(f"agents_per_hour_max ({agents_per_hour_max}) exceeds total Agent count ({num_entities}), corrected")
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)

        # Ensure min < max
        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(f"agents_per_hour_min >= max, corrected to {agents_per_hour_min}")

        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),  # Default 1 hour per round
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # Almost no one active in early morning
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5
        )

    def _dedupe_strings(self, values: List[Any], limit: Optional[int] = None) -> List[str]:
        seen = set()
        deduped: List[str] = []
        for value in values:
            if isinstance(value, str):
                normalized = " ".join(value.split())
            else:
                normalized = " ".join(str(value or "").split())
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)
            if limit is not None and len(deduped) >= limit:
                break
        return deduped

    def _entity_types_for_taxonomy(self, entities: List[EntityNode]) -> List[str]:
        return self._dedupe_strings(
            [entity.get_entity_type() or "Unknown" for entity in entities],
            limit=6,
        )

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        return slug or "scenario"

    def _extract_requirement_topics(self, simulation_requirement: str) -> List[str]:
        stopwords = {
            "about",
            "across",
            "after",
            "before",
            "during",
            "first",
            "from",
            "into",
            "over",
            "predict",
            "public",
            "reaction",
            "responses",
            "social",
            "their",
            "these",
            "those",
            "through",
            "under",
            "week",
            "weeks",
            "with",
        }
        words = re.findall(r"[A-Za-z][A-Za-z-]+", simulation_requirement.lower())
        return self._dedupe_strings(
            [word.replace("-", " ") for word in words if len(word) >= 4 and word not in stopwords],
            limit=4,
        )

    def _normalize_scenario_buckets(
        self,
        result: Dict[str, Any],
        simulation_requirement: str,
        entities: List[EntityNode],
    ) -> List[Dict[str, Any]]:
        available_types = self._entity_types_for_taxonomy(entities)
        fallback_topics = self._dedupe_strings(
            list(result.get("hot_topics", []) or []) + self._extract_requirement_topics(simulation_requirement),
            limit=6,
        )
        raw_buckets = list(result.get("scenario_buckets", []) or [])
        raw_posts = list(result.get("initial_posts", []) or [])

        if not raw_buckets and raw_posts:
            raw_buckets = [
                {
                    "label": f"Scenario {index + 1}",
                    "poster_type": post.get("poster_type"),
                    "seed_post": post.get("content"),
                    "topics": [fallback_topics[index]] if index < len(fallback_topics) else [],
                    "trigger_round": index + 1,
                }
                for index, post in enumerate(raw_posts[:4])
            ]

        if not raw_buckets:
            if not fallback_topics:
                fallback_topics = [simulation_requirement.strip() or "core reaction"]
            raw_buckets = [
                {
                    "label": topic.title(),
                    "focus": f"Discussion centers on {topic}.",
                    "poster_type": (
                        available_types[index % len(available_types)] if available_types else "Unknown"
                    ),
                    "seed_post": f"{topic.title()} is becoming a focal point in this discussion.",
                    "follow_up": f"People ask for evidence, trade-offs, and who benefits from {topic}.",
                    "trigger_round": index + 1,
                    "topics": [topic],
                }
                for index, topic in enumerate(fallback_topics[:4])
            ]

        buckets: List[Dict[str, Any]] = []
        for index, raw_bucket in enumerate(raw_buckets[:6]):
            bucket = dict(raw_bucket)
            label = str(
                bucket.get("label")
                or bucket.get("name")
                or bucket.get("topic")
                or bucket.get("focus")
                or f"Scenario {index + 1}"
            ).strip()
            topics = self._dedupe_strings(
                list(bucket.get("topics", []) or []) + ([bucket.get("topic")] if bucket.get("topic") else []),
                limit=4,
            )
            if not topics and index < len(fallback_topics):
                topics = [fallback_topics[index]]

            poster_type = str(bucket.get("poster_type") or "").strip()
            if not poster_type:
                poster_type = available_types[index % len(available_types)] if available_types else "Unknown"

            seed_post = str(bucket.get("seed_post") or bucket.get("content") or "").strip()
            if not seed_post:
                topic_fragment = topics[0] if topics else label.lower()
                seed_post = f"{topic_fragment.title()} is becoming a focal point in this discussion."

            follow_up = str(bucket.get("follow_up") or bucket.get("scheduled_event") or "").strip()
            if not follow_up and topics:
                follow_up = f"People ask for evidence, trade-offs, and who benefits from {topics[0]}."

            try:
                trigger_round = max(1, int(bucket.get("trigger_round", index + 1)))
            except (TypeError, ValueError):
                trigger_round = index + 1

            buckets.append(
                {
                    "bucket_id": str(bucket.get("bucket_id") or self._slug(label)),
                    "label": label,
                    "focus": str(bucket.get("focus") or bucket.get("description") or label).strip(),
                    "poster_type": poster_type,
                    "seed_post": seed_post,
                    "follow_up": follow_up,
                    "trigger_round": trigger_round,
                    "topics": topics,
                }
            )

        return buckets

    def _build_initial_posts_from_buckets(
        self,
        raw_posts: List[Dict[str, Any]],
        scenario_buckets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if raw_posts:
            normalized_posts: List[Dict[str, Any]] = []
            for index, post in enumerate(raw_posts):
                bucket = scenario_buckets[min(index, len(scenario_buckets) - 1)] if scenario_buckets else None
                normalized = dict(post)
                normalized["content"] = str(post.get("content") or (bucket.get("seed_post") if bucket else "")).strip()
                normalized["poster_type"] = str(post.get("poster_type") or (bucket.get("poster_type") if bucket else "Unknown")).strip() or "Unknown"
                if bucket is not None:
                    normalized.setdefault("scenario_bucket_id", bucket["bucket_id"])
                    normalized.setdefault("scenario_bucket_label", bucket["label"])
                normalized_posts.append(normalized)
            return normalized_posts

        return [
            {
                "content": bucket["seed_post"],
                "poster_type": bucket["poster_type"],
                "scenario_bucket_id": bucket["bucket_id"],
                "scenario_bucket_label": bucket["label"],
            }
            for bucket in scenario_buckets
            if bucket.get("seed_post")
        ]

    def _build_scheduled_events_from_buckets(
        self,
        raw_events: List[Dict[str, Any]],
        scenario_buckets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if raw_events:
            normalized_events: List[Dict[str, Any]] = []
            for index, event in enumerate(raw_events):
                bucket = scenario_buckets[min(index, len(scenario_buckets) - 1)] if scenario_buckets else None
                normalized = dict(event)
                if bucket is not None:
                    normalized.setdefault("scenario_bucket_id", bucket["bucket_id"])
                    normalized.setdefault("scenario_bucket_label", bucket["label"])
                normalized_events.append(normalized)
            return normalized_events

        return [
            {
                "trigger_round": bucket["trigger_round"],
                "content": bucket["follow_up"],
                "poster_type": bucket["poster_type"],
                "scenario_bucket_id": bucket["bucket_id"],
                "scenario_bucket_label": bucket["label"],
            }
            for bucket in scenario_buckets
            if bucket.get("follow_up")
        ]

    def _generate_event_config(
        self,
        context: str,
        simulation_requirement: str,
        entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """Generate event configuration"""

        # Get available entity type list for LLM reference
        entity_types_available = list(set(
            e.get_entity_type() or "Unknown" for e in entities
        ))

        # List representative entity names for each type
        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)

        type_info = "\n".join([
            f"- {t}: {', '.join(examples)}"
            for t, examples in type_examples.items()
        ])

        context_truncated = context[:self.EVENT_CONFIG_CONTEXT_LENGTH]

        prompt = f"""Based on the following simulation requirements, generate event configuration.

Simulation requirement: {simulation_requirement}

{context_truncated}

## Available Entity Types and Examples
{type_info}

## Task
Please generate an event configuration JSON:
- Extract trending topic keywords
- Describe the narrative development direction
- Build 3-5 taxonomy-driven scenario buckets that intentionally cover different reaction angles
- Each scenario bucket must specify a poster_type (publisher type) selected from the available entity types
- Each scenario bucket must include a seed_post that can be used as an initial simulation post
- Optionally include aligned initial_posts if useful, but the scenario_buckets are the primary coverage structure

**Important**: poster_type must be selected from the "Available Entity Types" above, so that scenario buckets and initial posts can be assigned to suitable Agents for publishing.
For example: official statements should be published by Official/University types, news by MediaOutlet types, student opinions by Student types.

Return JSON format (no markdown):
{{
    "hot_topics": ["keyword1", "keyword2", ...],
    "narrative_direction": "<narrative development direction description>",
    "scenario_buckets": [
        {{
            "label": "<short bucket name>",
            "focus": "<what this reaction lane explores>",
            "poster_type": "<entity type from available types>",
            "seed_post": "<initial post content for this bucket>",
            "follow_up": "<later-stage follow-up or counter-angle>",
            "trigger_round": 2,
            "topics": ["keyword1", "keyword2"]
        }}
    ],
    "initial_posts": [
        {{"content": "post content", "poster_type": "entity type (must be from available types)"}},
        ...
    ],
    "reasoning": "<brief explanation>"
}}"""

        system_prompt = "You are a public opinion analysis expert. Return pure JSON format. Note that poster_type must exactly match available entity types, and scenario_buckets should cover distinct reaction lanes instead of repeating the same angle."

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"Event config LLM generation failed: {e}, using default config")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "Using default configuration"
            }

    def _parse_event_config(
        self,
        result: Dict[str, Any],
        *,
        simulation_requirement: str = "",
        entities: Optional[List[EntityNode]] = None,
    ) -> EventConfig:
        """Parse event configuration result and normalize taxonomy-driven scenario buckets."""
        scenario_buckets = self._normalize_scenario_buckets(
            result,
            simulation_requirement,
            entities or [],
        )
        initial_posts = self._build_initial_posts_from_buckets(
            list(result.get("initial_posts", []) or []),
            scenario_buckets,
        )
        scheduled_events = self._build_scheduled_events_from_buckets(
            list(result.get("scheduled_events", []) or []),
            scenario_buckets,
        )
        hot_topics = self._dedupe_strings(
            list(result.get("hot_topics", []) or [])
            + [topic for bucket in scenario_buckets for topic in bucket.get("topics", [])],
            limit=8,
        )
        return EventConfig(
            initial_posts=initial_posts,
            scheduled_events=scheduled_events,
            hot_topics=hot_topics,
            narrative_direction=result.get("narrative_direction", ""),
            scenario_buckets=scenario_buckets,
        )

    def _assign_initial_post_agents(
        self,
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
        Assign suitable publisher Agents to initial posts

        Matches the most appropriate agent_id based on each post's poster_type
        """
        if not event_config.initial_posts:
            return event_config

        # Build agent index by entity type
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)

        # Type alias mapping (handles different formats the LLM may output)
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }

        # Track used agent index per type to avoid reusing the same agent
        used_indices: Dict[str, int] = {}

        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")

            # Try to find a matching agent
            matched_agent_id = None

            # 1. Direct match
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2. Match using aliases
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break

            # 3. If still not found, use the agent with highest influence
            if matched_agent_id is None:
                logger.warning(f"No matching Agent found for type '{poster_type}', using agent with highest influence")
                if agent_configs:
                    # Sort by influence and select the highest
                    sorted_agents = sorted(agent_configs, key=lambda a: a.influence_weight, reverse=True)
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0

            updated_post = dict(post)
            updated_post["content"] = content
            updated_post["poster_type"] = post.get("poster_type", "Unknown")
            updated_post["poster_agent_id"] = matched_agent_id
            updated_posts.append(updated_post)

            logger.info(f"Initial post assignment: poster_type='{poster_type}' -> agent_id={matched_agent_id}")

        event_config.initial_posts = updated_posts
        return event_config

    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str
    ) -> List[AgentActivityConfig]:
        """Generate Agent configurations in batches"""

        # Build entity information (using configured summary length)
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": start_idx + i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else ""
            })

        prompt = f"""Based on the following information, generate social media activity configuration for each entity.

Simulation requirement: {simulation_requirement}

## Entity List
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## Task
Generate activity configuration for each entity. Note:
- **Follow realistic daily activity patterns**: 0-5 AM almost no activity, 7-10 PM most active
- **Official institutions** (University/GovernmentAgency): low activity (0.1-0.3), active during work hours (9-17), slow response (60-240 min), high influence (2.5-3.0)
- **Media** (MediaOutlet): moderate activity (0.4-0.6), active all day (8-23), fast response (5-30 min), high influence (2.0-2.5)
- **Individuals** (Student/Person/Alumni): high activity (0.6-0.9), mainly active in evening (18-23), fast response (1-15 min), low influence (0.8-1.2)
- **Public figures/Experts**: moderate activity (0.4-0.6), moderate-high influence (1.5-2.0)

Return JSON format (no markdown):
{{
    "agent_configs": [
        {{
            "agent_id": <must match input>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <posting frequency>,
            "comments_per_hour": <commenting frequency>,
            "active_hours": [<list of active hours, following realistic daily patterns>],
            "response_delay_min": <minimum response delay in minutes>,
            "response_delay_max": <maximum response delay in minutes>,
            "sentiment_bias": <-1.0 to 1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <influence weight>
        }},
        ...
    ]
}}"""

        system_prompt = "You are a social media behavior analysis expert. Return pure JSON. Configuration should follow realistic daily activity patterns for the target population."

        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as e:
            logger.warning(f"Agent config batch LLM generation failed: {e}, using rule-based generation")
            llm_configs = {}

        # Build AgentActivityConfig objects
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})

            # If LLM did not generate, use rule-based generation
            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)

            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0)
            )
            configs.append(config)

        return configs

    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """Generate a single Agent configuration based on rules (general daily patterns)"""
        entity_type = (entity.get_entity_type() or "Unknown").lower()

        if entity_type in ["university", "governmentagency", "ngo"]:
            # Official institutions: active during work hours, low frequency, high influence
            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),  # 9:00-17:59
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0
            }
        elif entity_type in ["mediaoutlet"]:
            # Media: active all day, moderate frequency, high influence
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),  # 7:00-23:59
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5
            }
        elif entity_type in ["professor", "expert", "official"]:
            # Experts/Professors: active during work hours + evening, moderate frequency
            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),  # 8:00-21:59
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0
            }
        elif entity_type in ["student"]:
            # Students: mainly evening, high frequency
            return {
                "activity_level": 0.8,
                "posts_per_hour": 0.6,
                "comments_per_hour": 1.5,
                "active_hours": [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # Morning + evening
                "response_delay_min": 1,
                "response_delay_max": 15,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 0.8
            }
        elif entity_type in ["alumni"]:
            # Alumni: mainly evening
            return {
                "activity_level": 0.6,
                "posts_per_hour": 0.4,
                "comments_per_hour": 0.8,
                "active_hours": [12, 13, 19, 20, 21, 22, 23],  # Lunch break + evening
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
        else:
            # General public: evening peak
            return {
                "activity_level": 0.7,
                "posts_per_hour": 0.5,
                "comments_per_hour": 1.2,
                "active_hours": [9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # Daytime + evening
                "response_delay_min": 2,
                "response_delay_max": 20,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
