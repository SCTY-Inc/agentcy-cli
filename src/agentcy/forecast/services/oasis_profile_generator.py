"""
OASIS Agent Profile Generator
Converts entities from graph into Agent Profile format required by the OASIS simulation platform

Optimizations:
1. Call graph retrieval functions to enrich node information
2. Optimize prompts to generate highly detailed personas
3. Distinguish between individual entities and abstract group entities
"""

import json
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .entity_reader import EntityNode
from .graph_db import GraphDatabase
from .graph_storage import GraphStorage

logger = get_logger('mirofish.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent Profile data structure"""
    # Common fields
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str

    # Optional fields - Reddit style
    karma: int = 1000

    # Optional fields - Twitter style
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500

    # Additional persona information
    age: int | None = None
    gender: str | None = None
    mbti: str | None = None
    country: str | None = None
    profession: str | None = None
    interested_topics: list[str] = field(default_factory=list)

    # Source entity information
    source_entity_uuid: str | None = None
    source_entity_type: str | None = None

    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))

    def to_reddit_format(self) -> dict[str, Any]:
        """Convert to Reddit platform format"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS library requires the field name to be username (no underscore)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }

        # Add additional persona information (if available)
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics

        return profile

    def to_twitter_format(self) -> dict[str, Any]:
        """Convert to Twitter platform format"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS library requires the field name to be username (no underscore)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }

        # Add additional persona information
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics

        return profile

    def to_dict(self) -> dict[str, Any]:
        """Convert to full dictionary format"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS Profile Generator

    Converts entities from graph into Agent Profiles required for OASIS simulation

    Optimized features:
    1. Call graph retrieval functions to obtain richer context
    2. Generate highly detailed personas (including basic info, career history, personality traits, social media behavior, etc.)
    3. Distinguish between individual entities and abstract group entities
    """

    # MBTI type list
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]

    # Common countries list
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France",
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]

    # Individual entity types (require generating specific personas)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure",
        "expert", "faculty", "official", "journalist", "activist"
    ]

    # Group/organization entity types (require generating representative personas)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo",
        "mediaoutlet", "company", "institution", "group", "community"
    ]

    def __init__(
        self,
        graph_id: str | None = None,
        storage: GraphStorage | None = None,
        provider: str | None = None
    ):
        self.provider = (provider or Config.LLM_PROVIDER or "claude-cli").lower()
        self.llm = LLMClient(provider=self.provider)
        self.is_cli_provider = True

        # Graph database for retrieving rich context
        self.db = GraphDatabase()
        self.storage = storage
        self.graph_id = graph_id

    def generate_profile_from_entity(
        self,
        entity: EntityNode,
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        Generate an OASIS Agent Profile from a graph entity

        Args:
            entity: Graph entity node
            user_id: User ID (for OASIS)
            use_llm: Whether to use LLM for generating detailed persona

        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"

        # Basic information
        name = entity.name
        user_name = self._generate_username(name)

        # Build context information
        context = self._build_entity_context(entity)

        if use_llm:
            # Use LLM to generate detailed persona
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # Use rules to generate basic persona
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )

        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )

    def _generate_username(self, name: str) -> str:
        """Generate a username"""
        # Remove special characters, convert to lowercase
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')

        # Add random suffix to avoid duplicates
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"

    def _search_kuzu_for_entity(self, entity: EntityNode) -> dict[str, Any]:
        """
        Search the knowledge graph to retrieve rich information about the entity.

        Args:
            entity: Entity node object

        Returns:
            Dictionary containing facts, node_summaries, and context
        """
        entity_name = entity.name

        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }

        if not self.graph_id:
            logger.debug("Skipping graph retrieval: graph_id is not set")
            return results

        try:
            query = f"{entity_name}"

            # Search edges (facts/relationships)
            if self.storage is not None:
                edge_results = []
                query_terms = [term for term in query.lower().split() if term]
                for edge in self.storage.get_edges():
                    haystack = f"{edge.get('relation', '')} {edge.get('fact', '')}".lower()
                    score = sum(1 for term in query_terms if term in haystack)
                    if score:
                        edge_results.append(edge)
            else:
                edge_results = self.db.search(self.graph_id, query, limit=30, scope="edges")
            all_facts = set()
            for r in edge_results:
                fact = r.get("fact", "")
                if fact:
                    all_facts.add(fact)
            results["facts"] = list(all_facts)

            # Search nodes (entity summaries)
            if self.storage is not None:
                node_results = [
                    {
                        "name": node.get("name", ""),
                        "summary": node.get("summary", ""),
                    }
                    for node in self.storage.search_nodes(query, limit=20)
                ]
            else:
                node_results = self.db.search(self.graph_id, query, limit=20, scope="nodes")
            all_summaries = set()
            for r in node_results:
                summary = r.get("summary", "")
                if summary:
                    all_summaries.add(summary)
                name = r.get("name", "")
                if name and name != entity_name:
                    all_summaries.add(f"Related entity: {name}")
            results["node_summaries"] = list(all_summaries)

            # Build comprehensive context
            context_parts = []
            if results["facts"]:
                context_parts.append("Factual information:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("Related entities:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)

            logger.info(f"Graph search completed: {entity_name}, retrieved {len(results['facts'])} facts, {len(results['node_summaries'])} related nodes")

        except Exception as e:
            logger.warning(f"Graph retrieval failed ({entity_name}): {e}")

        return results

    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        Build the complete context information for an entity

        Includes:
        1. The entity's own edge information (facts)
        2. Detailed information about related nodes
        3. Rich information retrieved via graph search
        """
        context_parts = []

        # 1. Add entity attribute information
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### Entity Attributes\n" + "\n".join(attrs))

        # 2. Add related edge information (facts/relationships)
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # No limit on quantity
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")

                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (related entity)")
                    else:
                        relationships.append(f"- (related entity) --[{edge_name}]--> {entity.name}")

            if relationships:
                context_parts.append("### Related Facts and Relationships\n" + "\n".join(relationships))

        # 3. Add detailed information about related nodes
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # No limit on quantity
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")

                # Filter out default labels
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""

                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")

            if related_info:
                context_parts.append("### Related Entity Information\n" + "\n".join(related_info))

        # 4. Use graph search to retrieve richer information
        search_results = self._search_kuzu_for_entity(entity)

        if search_results.get("facts"):
            # Deduplicate: exclude already existing facts
            new_facts = [f for f in search_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Additional Facts from Graph Search\n" + "\n".join(f"- {f}" for f in new_facts[:15]))

        if search_results.get("node_summaries"):
            context_parts.append("### Related Nodes from Graph Search\n" + "\n".join(f"- {s}" for s in search_results["node_summaries"][:10]))

        return "\n\n".join(context_parts)

    def _is_individual_entity(self, entity_type: str) -> bool:
        """Determine whether this is an individual entity type"""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES

    def _is_group_entity(self, entity_type: str) -> bool:
        """Determine whether this is a group/organization entity type"""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES

    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: dict[str, Any],
        context: str
    ) -> dict[str, Any]:
        """
        Use LLM to generate a highly detailed persona

        Differentiates by entity type:
        - Individual entity: Generate a specific character profile
        - Group/organization entity: Generate a representative account profile
        """

        is_individual = self._is_individual_entity(entity_type)

        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # Retry generation until success or max attempts reached
        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                content = self.llm.chat(
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1),
                )

                # Try to parse JSON
                try:
                    result = json.loads(content)

                    # Validate required fields
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name} is a {entity_type}."

                    return result

                except json.JSONDecodeError as je:
                    logger.warning(f"JSON parsing failed (attempt {attempt+1}): {str(je)[:80]}")

                    # Try to fix JSON
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result

                    last_error = je

            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))  # Exponential backoff

        logger.warning(f"LLM persona generation failed ({max_attempts} attempts): {last_error}, falling back to rule-based generation")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )

    def _fix_truncated_json(self, content: str) -> str:
        """Fix truncated JSON (output was cut off by max_tokens limit)"""

        # If JSON was truncated, try to close it
        content = content.strip()

        # Count unclosed brackets
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')

        # Check for unclosed strings
        # Simple check: if there's no comma or closing bracket after the last quote, the string may be truncated
        if content and content[-1] not in '",}]':
            # Try to close the string
            content += '"'

        # Close brackets
        content += ']' * open_brackets
        content += '}' * open_braces

        return content

    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> dict[str, Any]:
        """Attempt to fix corrupted JSON"""
        import re

        # 1. First try to fix truncation
        content = self._fix_truncated_json(content)

        # 2. Try to extract the JSON portion
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()

            # 3. Handle newline characters within strings
            # Find all string values and replace newlines within them
            def fix_string_newlines(match):
                s = match.group(0)
                # Replace actual newlines within strings with spaces
                s = s.replace('\n', ' ').replace('\r', ' ')
                # Replace excess whitespace
                s = re.sub(r'\s+', ' ', s)
                return s

            # Match JSON string values
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)

            # 4. Try to parse
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError:
                # 5. If still failing, try more aggressive fixes
                try:
                    # Remove all control characters
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # Replace all consecutive whitespace
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except (json.JSONDecodeError, ValueError):
                    pass

        # 6. Try to extract partial information from content
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # May be truncated

        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name} is a {entity_type}.")

        # If meaningful content was extracted, mark as fixed
        if bio_match or persona_match:
            logger.info("Extracted partial information from corrupted JSON")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }

        # 7. Complete failure, return basic structure
        logger.warning("JSON repair failed, returning basic structure")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name} is a {entity_type}."
        }

    def _get_system_prompt(self, is_individual: bool) -> str:
        """Get the system prompt"""
        base_prompt = "You are an expert in generating concise social media user profiles for opinion simulation. Return valid JSON. All string values must not contain unescaped newline characters. Use English. IMPORTANT: Keep bio under 50 words and persona under 150 words. Be concise — every word must earn its place."
        return base_prompt

    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: dict[str, Any],
        context: str
    ) -> str:
        """Build the detailed persona prompt for an individual entity"""

        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
        context_str = context[:3000] if context else "No additional context"

        return f"""Generate a detailed social media user persona for this entity, reconstructing real-world situations as closely as possible.

Entity Name: {entity_name}
Entity Type: {entity_type}
Entity Summary: {entity_summary}
Entity Attributes: {attrs_str}

Context Information:
{context_str}

Please generate JSON containing the following fields:

1. bio: Social media bio, MAX 50 words. Punchy and distinctive.
2. persona: Concise persona description (MAX 150 words of plain text), must cover:
   - Background (occupation, location, key life context)
   - Personality and communication style (tone, posting habits)
   - Core stances on relevant topics
   - Connection to the events described in the context
3. age: Age as a number (must be an integer)
4. gender: Gender, must be in English: "male" or "female"
5. mbti: MBTI type (e.g., INTJ, ENFP, etc.)
6. country: Country
7. profession: Profession
8. interested_topics: Array of topics of interest

Important:
- All field values must be strings or numbers, do not use newline characters
- persona must be a coherent text description
- Use English (gender field must use English male/female)
- Content must be consistent with the entity information
- age must be a valid integer, gender must be "male" or "female"
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: dict[str, Any],
        context: str
    ) -> str:
        """Build the detailed persona prompt for a group/organization entity"""

        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
        context_str = context[:3000] if context else "No additional context"

        return f"""Generate a detailed social media account profile for this organization/group entity, reconstructing real-world situations as closely as possible.

Entity Name: {entity_name}
Entity Type: {entity_type}
Entity Summary: {entity_summary}
Entity Attributes: {attrs_str}

Context Information:
{context_str}

Please generate JSON containing the following fields:

1. bio: Official account bio, MAX 50 words. Professional and distinctive.
2. persona: Concise account profile (MAX 150 words of plain text), must cover:
   - Organization identity and function
   - Communication style and tone
   - Official positions on relevant topics
   - Connection to the events described in the context
3. age: Fixed at 30 (virtual age for organizational accounts)
4. gender: Fixed as "other" (organizational accounts use "other" to indicate non-individual)
5. mbti: MBTI type, used to describe the account style, e.g., ISTJ for rigorous and conservative
6. country: Country
7. profession: Description of organizational function
8. interested_topics: Array of areas of interest

Important:
- All field values must be strings or numbers, null values are not allowed
- persona must be a coherent text description, do not use newline characters
- Use English (gender field must use English "other")
- age must be the integer 30, gender must be the string "other"
- Organizational account communication must match its identity and positioning"""

    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate a basic persona using rules"""

        entity_type_lower = entity_type.lower()

        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic and social discussions. They enjoy sharing perspectives and connecting with peers.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }

        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": "Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {entity_type.lower()} who shares insights and opinions on important matters. They are known for their expertise and influence in public discourse.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }

        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity that reports news and facilitates public discourse. The account shares timely updates and engages with the audience on current events.",
                "age": 30,  # Virtual age for organizations
                "gender": "other",  # Organizations use "other"
                "mbti": "ISTJ",  # Organization style: rigorous and conservative
                "country": "China",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }

        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions, announcements, and engages with stakeholders on relevant matters.",
                "age": 30,  # Virtual age for organizations
                "gender": "other",  # Organizations use "other"
                "mbti": "ISTJ",  # Organization style: rigorous and conservative
                "country": "China",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }

        else:
            # Default persona
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name} is a {entity_type.lower()} participating in social discussions.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }

    def set_graph_id(self, graph_id: str):
        """Set the graph ID for graph retrieval"""
        self.graph_id = graph_id

    def generate_profiles_from_entities(
        self,
        entities: list[EntityNode],
        use_llm: bool = True,
        progress_callback: Callable | None = None,
        graph_id: str | None = None,
        parallel_count: int = 5,
        realtime_output_path: str | None = None,
        output_platform: str = "reddit"
    ) -> list[OasisAgentProfile]:
        """
        Batch generate Agent Profiles from entities (with parallel generation support)

        Args:
            entities: List of entities
            use_llm: Whether to use LLM for generating detailed personas
            progress_callback: Progress callback function (current, total, message)
            graph_id: Graph ID, used for graph retrieval to obtain richer context
            parallel_count: Number of parallel generations, default 5
            realtime_output_path: File path for real-time writing (if provided, writes after each generation)
            output_platform: Output platform format ("reddit" or "twitter")

        Returns:
            List of Agent Profiles
        """
        import concurrent.futures
        from threading import Lock

        # Set graph_id for graph retrieval
        if graph_id:
            self.graph_id = graph_id

        if use_llm and self.is_cli_provider:
            cli_parallel_limit = 4
            if parallel_count > cli_parallel_limit:
                logger.info(
                    f"CLI LLM provider detected ({self.provider}), reducing profile generation parallelism "
                    f"from {parallel_count} to {cli_parallel_limit}"
                )
                parallel_count = cli_parallel_limit

        total = len(entities)
        profiles = [None] * total  # Pre-allocate list to maintain order
        completed_count = [0]  # Use list to allow modification in closure
        lock = Lock()

        # Helper function for real-time file writing
        def save_profiles_realtime():
            """Save generated profiles to file in real time"""
            if not realtime_output_path:
                return

            with lock:
                # Filter out already generated profiles
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return

                try:
                    if output_platform == "reddit":
                        # Reddit JSON format
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV format
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"Real-time profile saving failed: {e}")

        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """Worker function to generate a single profile"""
            entity_type = entity.get_entity_type() or "Entity"

            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )

                # Output generated persona to console and log in real time
                self._print_generated_profile(entity.name, entity_type, profile)

                return idx, profile, None

            except Exception as e:
                logger.error(f"Failed to generate persona for entity {entity.name}: {str(e)}")
                # Create a basic fallback profile
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or "A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)

        logger.info(f"Starting parallel generation of {total} Agent personas (parallelism: {parallel_count})...")

        # Use thread pool for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # Submit all tasks
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }

            # Collect results
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"

                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile

                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]

                    # Write to file in real time
                    save_profiles_realtime()

                    if progress_callback:
                        progress_callback(
                            current,
                            total,
                            f"Completed {current}/{total}: {entity.name} ({entity_type})"
                        )

                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} using fallback persona: {error}")
                    else:
                        logger.info(f"[{current}/{total}] Successfully generated persona: {entity.name} ({entity_type})")

                except Exception as e:
                    logger.error(f"Exception occurred while processing entity {entity.name}: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # Write to file in real time (even for fallback personas)
                    save_profiles_realtime()

        logger.info(f"Persona generation complete: {len([p for p in profiles if p])} agents")

        return profiles

    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """Output generated persona to console in real time (full content, no truncation)"""
        separator = "-" * 70

        # Build complete output content (no truncation)
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else 'None'

        output_lines = [
            f"\n{separator}",
            f"[Generated] {entity_name} ({entity_type})",
            f"{separator}",
            f"Username: {profile.user_name}",
            "",
            "[Bio]",
            f"{profile.bio}",
            "",
            "[Detailed Persona]",
            f"{profile.persona}",
            "",
            "[Basic Attributes]",
            f"Age: {profile.age} | Gender: {profile.gender} | MBTI: {profile.mbti}",
            f"Profession: {profile.profession} | Country: {profile.country}",
            f"Interested Topics: {topics_str}",
            separator
        ]

        output = "\n".join(output_lines)
        logger.debug(output)

    def save_profiles(
        self,
        profiles: list[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        Save Profiles to file (choose correct format based on platform)

        OASIS platform format requirements:
        - Twitter: CSV format
        - Reddit: JSON format

        Args:
            profiles: List of Profiles
            file_path: File path
            platform: Platform type ("reddit" or "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)

    def _save_twitter_csv(self, profiles: list[OasisAgentProfile], file_path: str):
        """
        Save Twitter Profiles in CSV format (compliant with OASIS official requirements)

        OASIS Twitter required CSV fields:
        - user_id: User ID (starts from 0 based on CSV order)
        - name: User's real name
        - username: Username in the system
        - user_char: Detailed persona description (injected into LLM system prompt, guides Agent behavior)
        - description: Short public bio (displayed on user profile page)

        user_char vs description distinction:
        - user_char: Internal use, LLM system prompt, determines how the Agent thinks and acts
        - description: External display, bio visible to other users
        """
        import csv

        # Ensure file extension is .csv
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Write OASIS required headers
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)

            # Write data rows
            for idx, profile in enumerate(profiles):
                # user_char: Complete persona (bio + persona), used for LLM system prompt
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # Handle newline characters (replace with spaces in CSV)
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')

                # description: Short bio, used for external display
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')

                row = [
                    idx,                    # user_id: Sequential ID starting from 0
                    profile.name,           # name: Real name
                    profile.user_name,      # username: Username
                    user_char,              # user_char: Complete persona (internal LLM use)
                    description             # description: Short bio (external display)
                ]
                writer.writerow(row)

        logger.info(f"Saved {len(profiles)} Twitter Profiles to {file_path} (OASIS CSV format)")

    def _normalize_gender(self, gender: str | None) -> str:
        """
        Normalize the gender field to OASIS required English format

        OASIS requires: male, female, other
        """
        if not gender:
            return "other"

        gender_lower = gender.lower().strip()

        # Chinese-to-English gender mapping (Chinese keys are intentional input values)
        gender_map = {
            "男": "male",      # Chinese: "male"
            "女": "female",    # Chinese: "female"
            "机构": "other",   # Chinese: "institution/organization"
            "其他": "other",   # Chinese: "other"
            # English already valid
            "male": "male",
            "female": "female",
            "other": "other",
        }

        return gender_map.get(gender_lower, "other")

    def _save_reddit_json(self, profiles: list[OasisAgentProfile], file_path: str):
        """
        Save Reddit Profiles in JSON format

        Uses format consistent with to_reddit_format() to ensure OASIS can read correctly.
        Must include the user_id field, which is the key for OASIS agent_graph.get_agent() matching!

        Required fields:
        - user_id: User ID (integer, used to match poster_agent_id in initial_posts)
        - username: Username
        - name: Display name
        - bio: Bio
        - persona: Detailed persona
        - age: Age (integer)
        - gender: "male", "female", or "other"
        - mbti: MBTI type
        - country: Country
        """
        data = []
        for idx, profile in enumerate(profiles):
            # Use format consistent with to_reddit_format()
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,  # Critical: must include user_id
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is a participant in social discussions.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS required fields - ensure all have default values
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "China",
            }

            # Optional fields
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics

            data.append(item)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(profiles)} Reddit Profiles to {file_path} (JSON format, includes user_id field)")

    # Keep old method name as alias for backward compatibility
    def save_profiles_to_json(
        self,
        profiles: list[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[Deprecated] Please use the save_profiles() method"""
        logger.warning("save_profiles_to_json is deprecated, please use the save_profiles method")
        self.save_profiles(profiles, file_path, platform)
