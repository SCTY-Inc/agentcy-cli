"""
LLM-based Entity and Relationship Extractor
Uses the configured LLM to replace the old managed extraction pipeline.
Uses the configured LLM to extract entities and relationships from text chunks.
"""

from typing import Dict, Any, List, Optional

from .graph_storage import GraphStorage
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.entity_extractor')

EXTRACTION_SYSTEM_PROMPT = """You are a knowledge graph entity extraction expert. Your task is to extract entities and relationships from text based on a given ontology schema.

## Rules
1. Extract ONLY entities whose types match the provided entity types
2. Extract ONLY relationships whose types match the provided relationship types
3. Entity names should be proper nouns or specific identifiers found in the text
4. Each relationship must reference entities that exist in your extraction
5. Be thorough but precise - extract all relevant entities and relationships mentioned in the text
6. For each entity, provide a brief summary based on context in the text
7. For each relationship, provide a fact statement describing the relationship

## Output Format
Return valid JSON with this exact structure:
{
  "entities": [
    {
      "name": "Entity Name",
      "type": "EntityType",
      "summary": "Brief description based on the text context"
    }
  ],
  "relationships": [
    {
      "source": "Source Entity Name",
      "target": "Target Entity Name",
      "type": "relationship_type",
      "fact": "A sentence describing this relationship"
    }
  ]
}

If no entities or relationships are found, return:
{"entities": [], "relationships": []}
"""


class EntityExtractor:
    """
    Extracts entities and relationships from text using LLM.
    Designed to replace the old managed automatic entity extraction pipeline.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        storage: Optional[GraphStorage] = None,
    ):
        self.llm = llm_client or LLMClient()
        self.storage = storage

    def extract(
        self,
        text: str,
        ontology: Dict[str, Any],
        max_text_length: int = 8000
    ) -> Dict[str, Any]:
        """
        Extract entities and relationships from a text chunk.

        Args:
            text: Text to extract from
            ontology: Ontology definition with entity_types and edge_types
            max_text_length: Maximum text length to send to LLM

        Returns:
            Dict with 'entities' and 'relationships' lists
        """
        if not text or not text.strip():
            return {"entities": [], "relationships": []}

        # Truncate if needed
        if len(text) > max_text_length:
            text = text[:max_text_length] + "\n...[truncated]"

        # Build ontology description
        entity_types_desc = self._format_entity_types(ontology)
        edge_types_desc = self._format_edge_types(ontology)

        user_message = f"""## Ontology Schema

### Entity Types
{entity_types_desc}

### Relationship Types
{edge_types_desc}

## Text to Extract From
{text}

Extract all entities and relationships from the text above that match the ontology schema. Return valid JSON only."""

        try:
            result = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=4096,
            )

            entities = result.get("entities", [])
            relationships = result.get("relationships", [])

            logger.debug(f"Extracted {len(entities)} entities, {len(relationships)} relationships")
            return {"entities": entities, "relationships": relationships}

        except Exception as e:
            logger.warning(f"Entity extraction failed for chunk: {str(e)[:200]}")
            return {"entities": [], "relationships": []}

    def extract_batch(
        self,
        chunks: List[str],
        ontology: Dict[str, Any],
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Extract entities and relationships from multiple text chunks,
        merging results across chunks.

        Args:
            chunks: List of text chunks
            ontology: Ontology definition
            progress_callback: Optional callback(message, progress_ratio)

        Returns:
            Merged dict with 'entities' and 'relationships'
        """
        all_entities = {}  # name_lower -> entity dict
        all_relationships = []  # list of relationship dicts
        total = len(chunks)

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(
                    f"Extracting entities from chunk {i+1}/{total}...",
                    (i + 1) / total
                )

            result = self.extract(chunk, ontology)

            # Merge entities (deduplicate by name)
            for entity in result.get("entities", []):
                name = entity.get("name", "").strip()
                if not name:
                    continue
                key = name.lower()
                if key in all_entities:
                    # Merge: keep longer summary, combine types
                    existing = all_entities[key]
                    if len(entity.get("summary", "")) > len(existing.get("summary", "")):
                        existing["summary"] = entity["summary"]
                    # Keep the more specific type if different
                    if entity.get("type") and entity["type"] != existing.get("type"):
                        existing.setdefault("additional_types", []).append(entity["type"])
                else:
                    all_entities[key] = entity

            # Collect relationships (deduplicate by source+target+type)
            for rel in result.get("relationships", []):
                source = rel.get("source", "").strip().lower()
                target = rel.get("target", "").strip().lower()
                rel_type = rel.get("type", "").strip().lower()
                if not source or not target:
                    continue

                # Check for duplicate
                is_dup = any(
                    r.get("source", "").strip().lower() == source and
                    r.get("target", "").strip().lower() == target and
                    r.get("type", "").strip().lower() == rel_type
                    for r in all_relationships
                )
                if not is_dup:
                    all_relationships.append(rel)

        logger.info(f"Batch extraction complete: {len(all_entities)} unique entities, "
                   f"{len(all_relationships)} unique relationships from {total} chunks")

        return {
            "entities": list(all_entities.values()),
            "relationships": all_relationships,
        }

    def _format_entity_types(self, ontology: Dict[str, Any]) -> str:
        """Format entity types for the prompt"""
        lines = []
        for et in ontology.get("entity_types", []):
            name = et.get("name", "Unknown")
            desc = et.get("description", "")
            attrs = et.get("attributes", [])
            attr_names = [a.get("name", "") for a in attrs]
            line = f"- **{name}**: {desc}"
            if attr_names:
                line += f" (attributes: {', '.join(attr_names)})"
            lines.append(line)
        return "\n".join(lines) if lines else "No specific entity types defined."

    def _format_edge_types(self, ontology: Dict[str, Any]) -> str:
        """Format edge types for the prompt"""
        lines = []
        for et in ontology.get("edge_types", []):
            name = et.get("name", "Unknown")
            desc = et.get("description", "")
            sources = []
            for st in et.get("source_targets", []):
                sources.append(f"{st.get('source', '?')} -> {st.get('target', '?')}")
            line = f"- **{name}**: {desc}"
            if sources:
                line += f" ({', '.join(sources)})"
            lines.append(line)
        return "\n".join(lines) if lines else "No specific relationship types defined."
