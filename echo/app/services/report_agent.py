"""Report generation agent — fast-path (primary) and ReACT loop (legacy)."""

from __future__ import annotations

import os
import json
import re
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .graph_tools import GraphToolsService
from .report_language import _detect_language
from .report_logger import ReportConsoleLogger, ReportLogger
from .report_types import (
    Report, ReportOutline, ReportSection, ReportStatus,
    REPORT_STORAGE_ERRORS, OUTLINE_GENERATION_ERRORS, OPTIONAL_INTERVIEW_ERRORS,
    _now_iso,
    TOOL_DESC_INSIGHT_FORGE, TOOL_DESC_PANORAMA_SEARCH, TOOL_DESC_QUICK_SEARCH,
    TOOL_DESC_INTERVIEW_AGENTS, PLAN_SYSTEM_PROMPT, PLAN_USER_PROMPT_TEMPLATE,
    SECTION_SYSTEM_PROMPT_TEMPLATE, SECTION_USER_PROMPT_TEMPLATE,
    REACT_OBSERVATION_TEMPLATE, REACT_INSUFFICIENT_TOOLS_MSG,
    REACT_INSUFFICIENT_TOOLS_MSG_ALT, REACT_TOOL_LIMIT_MSG,
    REACT_UNUSED_TOOLS_HINT, REACT_FORCE_FINAL_MSG,
    CHAT_SYSTEM_PROMPT_TEMPLATE, CHAT_OBSERVATION_SUFFIX,
)
from .report_manager import ReportManager

# Re-export for backward compat
__all__ = ["ReportAgent", "ReportManager", "Report", "ReportStatus",
           "ReportOutline", "ReportSection"]

logger = get_logger("mirofish.report_agent")

# ReportAgent Main Class
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - Simulation Report Generation Agent

    Uses the ReACT (Reasoning + Acting) pattern:
    1. Planning phase: Analyze simulation requirements, plan report outline structure
    2. Generation phase: Generate content section by section, each section can invoke tools multiple times to retrieve information
    3. Reflection phase: Check content completeness and accuracy
    """

    # Maximum tool invocations per section
    MAX_TOOL_CALLS_PER_SECTION = 5

    # Maximum reflection rounds
    MAX_REFLECTION_ROUNDS = 3

    # Maximum tool invocations per chat
    MAX_TOOL_CALLS_PER_CHAT = 2

    def __init__(
        self,
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        graph_tools: Optional[GraphToolsService] = None
    ):
        """
        Initialize the Report Agent

        Args:
            graph_id: Graph ID
            simulation_id: Simulation ID
            simulation_requirement: Simulation requirement description
            llm_client: LLM client (optional)
            graph_tools: Graph tools service (optional)
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement

        self.llm = llm_client or LLMClient()
        self.graph_tools = graph_tools or GraphToolsService()

        # Detect report language from simulation requirement
        self.report_language = _detect_language(simulation_requirement)
        logger.info(f"Detected report language: {self.report_language} (based on simulation requirement)")

        # Tool definitions
        self.tools = self._define_tools()

        # Logger (initialized in generate_report)
        self.report_logger: Optional[ReportLogger] = None
        # Console logger (initialized in generate_report)
        self.console_logger: Optional[ReportConsoleLogger] = None

        logger.info(f"ReportAgent initialized: graph_id={graph_id}, simulation_id={simulation_id}")

    def generate_report_fast(
        self,
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None,
    ) -> Report:
        """Single-pass report generation — one LLM call instead of ReACT loop.

        Gathers all simulation data upfront, builds a comprehensive prompt,
        and generates the full report in a single LLM call.
        """
        import uuid as _uuid

        if not report_id:
            report_id = f"report_{_uuid.uuid4().hex[:12]}"

        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=_now_iso(),
        )

        try:
            ReportManager._ensure_report_folder(report_id)
            ReportManager.save_report(report)

            if progress_callback:
                progress_callback("generating", 10, "Gathering simulation data...")

            # Gather all data upfront
            context = self.graph_tools.get_simulation_context(
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement,
            )
            graph_stats = context.get("graph_statistics", {})
            related_facts = context.get("related_facts", [])

            # Get all nodes for entity summaries
            all_nodes = self.graph_tools.get_all_nodes(self.graph_id)
            entity_summaries = []
            for node in all_nodes[:20]:
                summary = f"- {node.name} ({', '.join(node.labels)})"
                if node.summary:
                    summary += f": {node.summary}"
                entity_summaries.append(summary)

            # Get simulation timeline and actions
            from .simulation_runner import SimulationRunner
            timeline = SimulationRunner.get_timeline(self.simulation_id)
            agent_stats = SimulationRunner.get_agent_stats(self.simulation_id)
            actions = SimulationRunner.get_all_actions(self.simulation_id)

            # Build action summaries (sample up to 30 most interesting)
            action_summaries = []
            interesting_actions = [
                a for a in actions
                if a.action_type not in ("DO_NOTHING", "REFRESH", "TREND")
            ]
            interesting_actions.sort(key=lambda a: a.timestamp)
            for a in interesting_actions[:30]:
                content_preview = (a.action_args.get("content") or a.result or "")[:200]
                action_summaries.append(
                    f"[Round {a.round_num}] [{a.platform}] {a.agent_name} ({a.action_type}): {content_preview}"
                )

            interview_text = self._collect_interview_text(agent_stats)

            if progress_callback:
                progress_callback("generating", 40, "Generating report...")

            # Build the single-pass prompt
            facts_text = "\n".join(
                f"- {f if isinstance(f, str) else f.get('fact', f.get('text', ''))}"
                for f in related_facts[:15]
            ) or "No facts extracted."

            entities_text = "\n".join(entity_summaries) or "No entities."
            actions_text = "\n".join(action_summaries) or "No notable actions."

            timeline_text = ""
            for t in timeline:
                timeline_text += f"Round {t['round_num']}: {t['total_actions']} actions ({t['twitter_actions']} twitter, {t['reddit_actions']} reddit)\n"
            timeline_text = timeline_text.strip() or "No timeline data."

            system_prompt = f"""You are an expert analyst writing a prediction report based on a social media simulation.
You are writing from a god's-eye view of a simulated future — not describing the present, but predicting what will happen.
Write in English. Be analytical, specific, and evidence-based. Quote agent statements where relevant.
Do NOT repeat the same data points across sections. Each section should cover distinct ground."""

            user_prompt = f"""## Simulation Requirement
{self.simulation_requirement}

## Knowledge Graph
Entities ({graph_stats.get('total_nodes', 0)} nodes, {graph_stats.get('total_edges', 0)} edges):
{entities_text}

Key facts:
{facts_text}

## Simulation Results
{timeline_text}

## Notable Agent Actions (simulated social media posts)
{actions_text}

## Agent Interviews
{interview_text or "No interviews available."}

---

Write a prediction report with:
1. A title and one-line executive summary
2. 3-4 analytical sections (use ## for section headers)
3. Each section should analyze a different dimension: key actors, policy dynamics, public discourse patterns, risks/opportunities
4. Quote specific agent actions and interview responses as evidence
5. Keep total length under 2000 words — be dense and analytical, not verbose"""

            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.5,
                max_tokens=4096,
            )

            if progress_callback:
                progress_callback("generating", 90, "Saving report...")

            # Parse into outline structure
            lines = response.strip().split("\n")
            title = "Simulation Report"
            summary = ""
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            # Extract summary (first > line or first paragraph)
            for line in lines:
                if line.startswith("> "):
                    summary = line[2:].strip()
                    break

            outline = ReportOutline(
                title=title,
                summary=summary,
                sections=[ReportSection(title=title, content=response)],
            )

            report.outline = outline
            report.markdown_content = response
            report.status = ReportStatus.COMPLETED
            report.completed_at = _now_iso()

            ReportManager.save_report(report)
            ReportManager.save_outline(report_id, outline)
            # Write full report markdown
            md_path = ReportManager._get_report_markdown_path(report_id)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(response)

            if progress_callback:
                progress_callback("generating", 100, "Report complete")

            logger.info(f"Single-pass report generated: {report_id}")
            return report

        except Exception as exc:
            self._record_failed_report(report, str(exc), "Failed to persist report on fast-path failure")
            logger.error(f"Report generation failed: {exc}")
            raise

    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define available tools"""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "The question or topic you want to analyze in depth",
                    "report_context": "Context of the current report section (optional, helps generate more precise sub-questions)"
                }
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "Search query, used for relevance ranking",
                    "include_expired": "Whether to include expired/historical content (default True)"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "Search query string",
                    "limit": "Number of results to return (optional, default 10)"
                }
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "Interview topic or requirement description (e.g., 'Understand students' views on the dormitory formaldehyde incident')",
                    "max_agents": "Maximum number of Agents to interview (optional, default 5, max 10)"
                }
            }
        }

    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> str:
        """
        Execute a tool invocation

        Args:
            tool_name: Tool name
            parameters: Tool parameters
            report_context: Report context (used for InsightForge)

        Returns:
            Tool execution result (text format)
        """
        logger.info(f"Executing tool: {tool_name}, parameters: {parameters}")

        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.graph_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                return result.to_text()

            elif tool_name == "panorama_search":
                # Broad search - get panoramic view
                query = parameters.get("query", "")
                include_expired = self._coerce_bool(parameters.get("include_expired", True))
                result = self.graph_tools.panorama_search(
                    graph_id=self.graph_id,
                    query=query,
                    include_expired=include_expired
                )
                return result.to_text()

            elif tool_name == "quick_search":
                # Simple search - quick retrieval
                query = parameters.get("query", "")
                limit = self._coerce_int(parameters.get("limit", 10), default=10)
                result = self.graph_tools.quick_search(
                    graph_id=self.graph_id,
                    query=query,
                    limit=limit
                )
                return result.to_text()

            elif tool_name == "interview_agents":
                # Deep interview - call the real OASIS interview API to get simulation Agent responses (dual platform)
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = min(self._coerce_int(parameters.get("max_agents", 5), default=5), 10)
                result = self.graph_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents
                )
                return result.to_text()

            elif tool_name == "search_graph":
                logger.info("search_graph redirected to quick_search")
                return self._execute_tool("quick_search", parameters, report_context)

            elif tool_name == "get_graph_statistics":
                result = self.graph_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.graph_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "get_simulation_context":
                logger.info("get_simulation_context redirected to insight_forge")
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)

            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.graph_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)

            else:
                return f"Unknown tool: {tool_name}. Please use one of: insight_forge, panorama_search, quick_search"

        except Exception as exc:
            logger.error(f"Tool execution failed: {tool_name}, error: {str(exc)}")
            return f"Tool execution failed: {str(exc)}"

    VALID_TOOL_NAMES = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes']
        return bool(value)

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        return int(value)

    def _parse_tool_call_json(self, payload: str) -> Optional[Dict[str, Any]]:
        try:
            call_data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(call_data, dict):
            return None
        return call_data if self._is_valid_tool_call(call_data) else None

    @staticmethod
    def _default_outline() -> ReportOutline:
        return ReportOutline(
            title="Future Prediction Report",
            summary="Future trends and risk analysis based on simulation predictions",
            sections=[
                ReportSection(title="Prediction Scenario and Core Findings"),
                ReportSection(title="Population Behavior Prediction Analysis"),
                ReportSection(title="Trend Outlook and Risk Alerts"),
            ],
        )

    def _record_failed_report(self, report: Report, error: str, debug_message: str) -> None:
        report.status = ReportStatus.FAILED
        report.error = error
        report.completed_at = _now_iso()
        try:
            ReportManager.save_report(report)
        except REPORT_STORAGE_ERRORS:
            logger.debug(debug_message, exc_info=True)

    def _collect_interview_text(self, agent_stats: List[Dict[str, Any]]) -> str:
        top_agents = sorted(agent_stats, key=lambda x: x.get("total_actions", 0), reverse=True)[:5]
        if not top_agents:
            return ""

        try:
            interview_result = self.graph_tools.interview_agents(
                simulation_id=self.simulation_id,
                interview_requirement=(
                    f"What is your prediction for how {self.simulation_requirement}? "
                    "What surprised you during the simulation?"
                ),
                simulation_requirement=self.simulation_requirement,
                max_agents=5,
            )
        except OPTIONAL_INTERVIEW_ERRORS as exc:
            logger.warning(f"Interview failed (non-fatal): {exc}")
            return ""

        return interview_result.to_text() if hasattr(interview_result, "to_text") else ""

    def _load_existing_report_excerpt(self) -> str:
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
        except REPORT_STORAGE_ERRORS as exc:
            logger.warning(f"Failed to retrieve report content: {exc}")
            return ""

        if not report or not report.markdown_content:
            return ""

        report_content = report.markdown_content[:15000]
        if len(report.markdown_content) > 15000:
            report_content += "\n\n... [Report content truncated] ..."
        return report_content

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from LLM response

        Supported formats (by priority):
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. Bare JSON (the response as a whole or a single line is a tool call JSON)
        """
        tool_calls = []

        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            call_data = self._parse_tool_call_json(match.group(1))
            if call_data is not None:
                tool_calls.append(call_data)

        if tool_calls:
            return tool_calls

        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            call_data = self._parse_tool_call_json(stripped)
            if call_data is not None:
                tool_calls.append(call_data)
                return tool_calls

        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            call_data = self._parse_tool_call_json(match.group(1))
            if call_data is not None:
                tool_calls.append(call_data)

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """Validate whether the parsed JSON is a valid tool call"""
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            # Normalize key names to name / parameters
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False

    def _get_tools_description(self) -> str:
        """Generate tool description text"""
        desc_parts = ["Available tools:"]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  Parameters: {params_desc}")
        return "\n".join(desc_parts)

    def _check_language_drift(
        self,
        content: str,
        section_title: str,
        messages: List[Dict[str, str]],
        section_index: int
    ) -> str:
        """
        Check if generated content drifted to a different language.

        For English reports, if content contains >5% CJK characters, attempt one regeneration with stricter prompt.

        Args:
            content: Section content to check
            section_title: Title of the section
            messages: Message history for regeneration attempt
            section_index: Index of the section

        Returns:
            Content (either original or regenerated)
        """
        # Only check for language drift if expecting English report
        if self.report_language != "en":
            return content

        detected_lang = _detect_language(content)

        # If content is detected as Chinese but we expected English, attempt regeneration
        if detected_lang == "zh":
            logger.warning(
                f"Section '{section_title}' drifted to Chinese — detected {_detect_language(content)} but expected English. "
                "Attempting regeneration with stricter English enforcement..."
            )

            # Prepare a stricter English enforcement prompt
            enforcement_prompt = (
                "[CRITICAL LANGUAGE REQUIREMENT]\n"
                "The output above contains Chinese text, which violates the English language requirement.\n"
                "You MUST respond ENTIRELY in English. Do not switch to Chinese.\n"
                "Please regenerate the section content in pure English.\n"
                "Start with 'Final Answer:' and write only in English."
            )

            # Append the drift detection to messages and attempt one more generation
            messages.append({
                "role": "user",
                "content": enforcement_prompt
            })

            regenerated = self.llm.chat(
                messages=messages,
                temperature=0.3,  # Lower temperature for stricter adherence
                max_tokens=4096
            )

            if regenerated:
                # Extract content if it has "Final Answer:" prefix
                if "Final Answer:" in regenerated:
                    regenerated = regenerated.split("Final Answer:")[-1].strip()

                # Check if regeneration succeeded
                if _detect_language(regenerated) == "en":
                    logger.info(f"Section '{section_title}' regenerated successfully in English")
                    return regenerated
                else:
                    logger.error(
                        f"Section '{section_title}' still contains Chinese after regeneration attempt. "
                        "Returning original content with warning."
                    )
            else:
                logger.error(f"Section '{section_title}' regeneration returned None. Returning original content.")

        return content

    def plan_outline(
        self,
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        Plan the report outline

        Use LLM to analyze simulation requirements and plan the report's directory structure

        Args:
            progress_callback: Progress callback function

        Returns:
            ReportOutline: Report outline
        """
        logger.info("Starting report outline planning...")

        if progress_callback:
            progress_callback("planning", 0, "Analyzing simulation requirements...")

        # First retrieve simulation context
        context = self.graph_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )

        if progress_callback:
            progress_callback("planning", 30, "Generating report outline...")

        system_prompt = PLAN_SYSTEM_PROMPT
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
            total_entities=context.get('total_entities', 0),
            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            if progress_callback:
                progress_callback("planning", 80, "Parsing outline structure...")

            # Parse outline
            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))

            outline = ReportOutline(
                title=response.get("title", "Simulation Analysis Report"),
                summary=response.get("summary", ""),
                sections=sections
            )

            if progress_callback:
                progress_callback("planning", 100, "Outline planning completed")

            logger.info(f"Outline planning completed: {len(sections)} sections")
            return outline

        except OUTLINE_GENERATION_ERRORS as exc:
            logger.error(f"Outline planning failed: {str(exc)}")
            return self._default_outline()

    def _generate_section_react(
        self,
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
        Generate a single section using the ReACT pattern

        ReACT loop:
        1. Thought - Analyze what information is needed
        2. Action - Invoke tools to retrieve information
        3. Observation - Analyze tool return results
        4. Repeat until sufficient information or maximum iterations reached
        5. Final Answer - Generate section content

        Args:
            section: The section to generate
            outline: Complete outline
            previous_sections: Content of previous sections (for maintaining coherence)
            progress_callback: Progress callback
            section_index: Section index (for logging)

        Returns:
            Section content (Markdown format)
        """
        logger.info(f"ReACT generating section: {section.title}")

        # Record section start log
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)

        # Map language code to display name
        report_language_name = "Chinese" if self.report_language == "zh" else "English"

        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
            report_language=report_language_name,
        )

        # Build user prompt - each completed section passes in up to 4000 characters
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # Each section up to 4000 characters
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "(This is the first section)"

        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # ReACT loop
        tool_calls_count = 0
        max_iterations = 5  # Maximum iteration rounds
        min_tool_calls = 3  # Minimum tool invocations
        conflict_retries = 0  # Consecutive conflicts where tool call and Final Answer appear simultaneously
        used_tools = set()  # Track tools that have been invoked
        all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

        # Report context, used for InsightForge sub-question generation
        report_context = f"Section title: {section.title}\nSimulation requirement: {self.simulation_requirement}"

        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating",
                    int((iteration / max_iterations) * 100),
                    f"Deep retrieval and writing in progress ({tool_calls_count}/{self.MAX_TOOL_CALLS_PER_SECTION})"
                )

            # Call LLM
            response = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )

            # Check if LLM returned None (API exception or empty content)
            if response is None:
                logger.warning(f"Section {section.title} iteration {iteration + 1}: LLM returned None")
                # If iterations remain, add message and retry
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "(empty response)"})
                    messages.append({"role": "user", "content": "Please continue generating content."})
                    continue
                # Last iteration also returned None, break out to forced finalization
                break

            logger.debug(f"LLM response: {response[:200]}...")

            # Parse once, reuse results
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # ── Conflict handling: LLM output both tool call and Final Answer simultaneously ──
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    f"Section {section.title} round {iteration+1}: "
                    f"LLM output both tool call and Final Answer simultaneously (conflict #{conflict_retries})"
                )

                if conflict_retries <= 2:
                    # First two times: discard this response, ask LLM to reply again
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[Format Error] You included both a tool call and Final Answer in a single reply, which is not allowed.\n"
                            "Each reply can only do one of the following two things:\n"
                            "- Invoke a tool (output a <tool_call> block, do not write Final Answer)\n"
                            "- Output final content (start with 'Final Answer:', do not include <tool_call>)\n"
                            "Please reply again, doing only one of these."
                        ),
                    })
                    continue
                else:
                    # Third time: degrade handling, truncate to first tool call and force execution
                    logger.warning(
                        f"Section {section.title}: {conflict_retries} consecutive conflicts, "
                        "degrading to truncated execution of first tool call"
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # Record LLM response log
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            # ── Case 1: LLM output Final Answer ──
            if has_final_answer:
                # Insufficient tool invocations, reject and require more tool calls
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = f"(These tools have not been used yet; consider trying them: {', '.join(unused_tools)})" if unused_tools else ""
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                # Normal completion
                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(f"Section {section.title} generation completed (tool invocations: {tool_calls_count})")

                # Check for language drift and regenerate if needed
                final_answer = self._check_language_drift(
                    final_answer,
                    section.title,
                    messages,
                    section_index
                )

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            # ── Case 2: LLM attempted to invoke a tool ──
            if has_tool_calls:
                # Tool quota exhausted -> explicitly notify, require Final Answer output
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                # Execute only the first tool call
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(f"LLM attempted to invoke {len(tool_calls)} tools, executing only the first: {call['name']}")

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                # Build unused tools hint
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list=", ".join(unused_tools))

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # ── Case 3: Neither tool call nor Final Answer ──
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                # Insufficient tool invocations, recommend unused tools
                unused_tools = all_tools - used_tools
                unused_hint = f"(These tools have not been used yet; consider trying them: {', '.join(unused_tools)})" if unused_tools else ""

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # Sufficient tool invocations, LLM output content without "Final Answer:" prefix
            # Directly use this content as the final answer, avoid idle loops
            logger.info(f"Section {section.title}: 'Final Answer:' prefix not detected, adopting LLM output as final content (tool invocations: {tool_calls_count})")
            final_answer = response.strip()

            # Check for language drift and regenerate if needed
            final_answer = self._check_language_drift(
                final_answer,
                section.title,
                messages,
                section_index
            )

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer

        # Maximum iterations reached, force content generation
        logger.warning(f"Section {section.title} reached maximum iterations, forcing generation")
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})

        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )

        # Check if LLM returned None during forced finalization
        if response is None:
            logger.error(f"Section {section.title}: LLM returned None during forced finalization, using default error message")
            final_answer = f"(This section failed to generate: LLM returned empty response, please try again later)"
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response

        # Check for language drift and regenerate if needed (only if we have valid content)
        if response is not None and not final_answer.startswith("(This section failed"):
            final_answer = self._check_language_drift(
                final_answer,
                section.title,
                messages,
                section_index
            )

        # Record section content generation completion log
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )

        return final_answer

    def generate_report(
        self,
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        Generate the complete report (real-time section-by-section output)

        Each section is saved to a file immediately after generation, without waiting for the entire report to complete.
        File structure:
        reports/{report_id}/
            meta.json       - Report metadata
            outline.json    - Report outline
            progress.json   - Generation progress
            section_01.md   - Section 1
            section_02.md   - Section 2
            ...
            full_report.md  - Complete report

        Args:
            progress_callback: Progress callback function (stage, progress, message)
            report_id: Report ID (optional, auto-generated if not provided)

        Returns:
            Report: Complete report
        """
        import uuid

        # Auto-generate report_id if not provided
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()

        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=_now_iso()
        )

        # List of completed section titles (for progress tracking)
        completed_section_titles = []

        try:
            # Initialize: create report folder and save initial state
            ReportManager._ensure_report_folder(report_id)

            # Initialize logger (structured log agent_log.jsonl)
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement
            )

            # Initialize console logger (console_log.txt)
            self.console_logger = ReportConsoleLogger(report_id)

            ReportManager.update_progress(
                report_id, "pending", 0, "Initializing report...",
                completed_sections=[]
            )
            ReportManager.save_report(report)

            # Phase 1: Plan outline
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, "Starting report outline planning...",
                completed_sections=[]
            )

            # Record planning start log
            self.report_logger.log_planning_start()

            if progress_callback:
                progress_callback("planning", 0, "Starting report outline planning...")

            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg:
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
            )
            report.outline = outline

            # Record planning completion log
            self.report_logger.log_planning_complete(outline.to_dict())

            # Save outline to file
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id, "planning", 15, f"Outline planning completed, {len(outline.sections)} sections total",
                completed_sections=[]
            )
            ReportManager.save_report(report)

            logger.info(f"Outline saved to file: {report_id}/outline.json")

            # Phase 2: Generate sections one by one (save per section)
            report.status = ReportStatus.GENERATING

            total_sections = len(outline.sections)
            generated_sections = []  # Save content for context

            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)

                # Update progress
                ReportManager.update_progress(
                    report_id, "generating", base_progress,
                    f"Generating section: {section.title} ({section_num}/{total_sections})",
                    current_section=section.title,
                    completed_sections=completed_section_titles
                )

                if progress_callback:
                    progress_callback(
                        "generating",
                        base_progress,
                        f"Generating section: {section.title} ({section_num}/{total_sections})"
                    )

                # Generate main section content
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg:
                        progress_callback(
                            stage,
                            base_progress + int(prog * 0.7 / total_sections),
                            msg
                        ) if progress_callback else None,
                    section_index=section_num
                )

                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # Save section
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # Record section completion log
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip()
                    )

                logger.info(f"Section saved: {report_id}/section_{section_num:02d}.md")

                # Update progress
                ReportManager.update_progress(
                    report_id, "generating",
                    base_progress + int(70 / total_sections),
                    f"Section {section.title} completed",
                    current_section=None,
                    completed_sections=completed_section_titles
                )

            # Phase 3: Assemble complete report
            if progress_callback:
                progress_callback("generating", 95, "Assembling complete report...")

            ReportManager.update_progress(
                report_id, "generating", 95, "Assembling complete report...",
                completed_sections=completed_section_titles
            )

            # Use ReportManager to assemble the complete report
            report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
            report.status = ReportStatus.COMPLETED
            report.completed_at = _now_iso()

            # Calculate total elapsed time
            total_time_seconds = (datetime.now() - start_time).total_seconds()

            # Record report completion log
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections,
                    total_time_seconds=total_time_seconds
                )

            # Save final report
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id, "completed", 100, "Report generation completed",
                completed_sections=completed_section_titles
            )

            if progress_callback:
                progress_callback("completed", 100, "Report generation completed")

            logger.info(f"Report generation completed: {report_id}")

            # Close console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

        except Exception as exc:
            logger.error(f"Report generation failed: {str(exc)}")
            self._record_failed_report(report, str(exc), "Failed to persist report on failure state")

            if self.report_logger:
                self.report_logger.log_error(str(exc), "failed")

            try:
                ReportManager.update_progress(
                    report_id, "failed", -1, f"Report generation failed: {str(exc)}",
                    completed_sections=completed_section_titles
                )
            except REPORT_STORAGE_ERRORS:
                logger.debug("Failed to persist report progress on failure state", exc_info=True)

            # Close console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

    def chat(
        self,
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Chat with the Report Agent

        During the conversation, the Agent can autonomously invoke retrieval tools to answer questions

        Args:
            message: User message
            chat_history: Chat history

        Returns:
            {
                "response": "Agent reply",
                "tool_calls": [list of tools invoked],
                "sources": [information sources]
            }
        """
        logger.info(f"Report Agent chat: {message[:50]}...")

        chat_history = chat_history or []

        report_content = self._load_existing_report_excerpt()

        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "(No report available yet)",
            tools_description=self._get_tools_description(),
        )

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        # Add chat history
        for h in chat_history[-10:]:  # Limit history length
            messages.append(h)

        # Add user message
        messages.append({
            "role": "user",
            "content": message
        })

        # ReACT loop (simplified version)
        tool_calls_made = []
        max_iterations = 2  # Reduced iteration rounds

        for iteration in range(max_iterations):
            response = self.llm.chat(
                messages=messages,
                temperature=0.5
            )

            # Parse tool calls
            tool_calls = self._parse_tool_calls(response)

            if not tool_calls:
                # No tool calls, return response directly
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)

                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }

            # Execute tool calls (limited quantity)
            tool_results = []
            for call in tool_calls[:1]:  # Execute at most 1 tool call per round
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result[:1500]  # Limit result length
                })
                tool_calls_made.append(call)

            # Add results to messages
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']} result]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })

        # Maximum iterations reached, get final response
        final_response = self.llm.chat(
            messages=messages,
            temperature=0.5
        )

        # Clean response
        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)

        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }


