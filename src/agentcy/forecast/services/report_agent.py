"""
Report Agent Service
Implements ReACT-pattern simulation report generation using local graph retrieval

Features:
1. Generate reports based on simulation requirements and graph information
2. First plan the outline structure, then generate content section by section
3. Each section uses ReACT multi-turn reasoning and reflection
4. Support user conversations with autonomous retrieval tool invocation
"""

import os
import json
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .graph_tools import GraphToolsService
from .report_language import _detect_language
from .report_logger import ReportConsoleLogger, ReportLogger

logger = get_logger('mirofish.report_agent')

REPORT_STORAGE_ERRORS = (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError)
OUTLINE_GENERATION_ERRORS = (
    OSError,
    AttributeError,
    KeyError,
    TypeError,
    ValueError,
    json.JSONDecodeError,
    RuntimeError,
)
OPTIONAL_INTERVIEW_ERRORS = (OSError, RuntimeError, TimeoutError, TypeError, ValueError)


def _now_iso() -> str:
    return datetime.now().isoformat()


class ReportStatus(str, Enum):
    """Report status"""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """Report section"""
    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content
        }

    def to_markdown(self, level: int = 2) -> str:
        """Convert to Markdown format"""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """Report outline"""
    title: str
    summary: str
    sections: List[ReportSection]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections]
        }

    def to_markdown(self) -> str:
        """Convert to Markdown format"""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """Complete report"""
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error
        }


# ═══════════════════════════════════════════════════════════════
# Prompt Template Constants
# ═══════════════════════════════════════════════════════════════

# ── Tool Descriptions ──

TOOL_DESC_INSIGHT_FORGE = """\
[Deep Insight Retrieval - Powerful Retrieval Tool]
This is our powerful retrieval function, designed for deep analysis. It will:
1. Automatically decompose your question into multiple sub-questions
2. Retrieve information from the simulation graph across multiple dimensions
3. Integrate results from semantic search, entity analysis, and relationship chain tracing
4. Return the most comprehensive and in-depth retrieval content

[Use Cases]
- Need to deeply analyze a specific topic
- Need to understand multiple aspects of an event
- Need to obtain rich material to support a report section

[Return Content]
- Relevant factual text (can be directly quoted)
- Core entity insights
- Relationship chain analysis"""

TOOL_DESC_PANORAMA_SEARCH = """\
[Broad Search - Get a Panoramic View]
This tool is used to obtain a complete overview of simulation results, especially suitable for understanding event evolution. It will:
1. Retrieve all relevant nodes and relationships
2. Distinguish between currently valid facts and historical/expired facts
3. Help you understand how public opinion evolved

[Use Cases]
- Need to understand the complete development trajectory of an event
- Need to compare public opinion changes across different stages
- Need to obtain comprehensive entity and relationship information

[Return Content]
- Currently valid facts (latest simulation results)
- Historical/expired facts (evolution records)
- All involved entities"""

TOOL_DESC_QUICK_SEARCH = """\
[Simple Search - Quick Retrieval]
A lightweight quick retrieval tool, suitable for simple and direct information queries.

[Use Cases]
- Need to quickly find specific information
- Need to verify a fact
- Simple information retrieval

[Return Content]
- List of facts most relevant to the query"""

TOOL_DESC_INTERVIEW_AGENTS = """\
[Deep Interview - Real Agent Interview (Dual Platform)]
Calls the OASIS simulation environment's interview API to conduct real interviews with running simulation Agents!
This is not an LLM simulation, but calls the actual interview interface to obtain original responses from simulation Agents.
By default, interviews are conducted simultaneously on both Twitter and Reddit platforms for more comprehensive perspectives.

Workflow:
1. Automatically reads persona files to understand all simulation Agents
2. Intelligently selects Agents most relevant to the interview topic (e.g., students, media, officials, etc.)
3. Automatically generates interview questions
4. Calls the /api/simulation/interview/batch interface for real interviews on both platforms
5. Integrates all interview results to provide multi-perspective analysis

[Use Cases]
- Need to understand event perspectives from different roles (What do students think? What does the media think? What do officials say?)
- Need to collect opinions and positions from multiple parties
- Need to obtain real responses from simulation Agents (from the OASIS simulation environment)
- Want to make the report more vivid by including "interview transcripts"

[Return Content]
- Identity information of interviewed Agents
- Each Agent's interview responses on both Twitter and Reddit platforms
- Key quotes (can be directly cited)
- Interview summary and viewpoint comparison

[Important] The OASIS simulation environment must be running to use this feature!"""

# ── Outline Planning Prompt ──

PLAN_SYSTEM_PROMPT = """\
You are a "Future Prediction Report" writing expert with a "God's-eye view" of the simulated world — you can perceive every Agent's behavior, statements, and interactions within the simulation.

[Core Concept]
We have built a simulated world and injected a specific "simulation requirement" as a variable. The evolution results of the simulated world represent predictions of what may happen in the future. What you are observing is not "experimental data" but a "rehearsal of the future."

[Your Task]
Write a "Future Prediction Report" that answers:
1. Under the conditions we set, what happened in the future?
2. How did various Agents (population groups) react and act?
3. What noteworthy future trends and risks does this simulation reveal?

[Report Positioning]
- This is a simulation-based future prediction report, revealing "if this happens, what will the future look like"
- Focus on prediction results: event trajectories, group reactions, emergent phenomena, potential risks
- Agent behaviors and statements in the simulated world are predictions of future population behavior
- This is NOT an analysis of real-world current conditions
- This is NOT a generic public opinion overview

[Section Count Limits]
- Minimum 2 sections, maximum 5 sections
- No sub-sections needed; each section should contain complete content directly
- Content should be concise, focusing on core prediction findings
- Section structure is designed by you based on the prediction results

Please output the report outline in JSON format as follows:
{
    "title": "Report Title",
    "summary": "Report summary (one sentence summarizing core prediction findings)",
    "sections": [
        {
            "title": "Section Title",
            "description": "Section content description"
        }
    ]
}

Note: The sections array must contain at least 2 and at most 5 elements!"""

PLAN_USER_PROMPT_TEMPLATE = """\
[Prediction Scenario Setup]
The variable injected into the simulated world (simulation requirement): {simulation_requirement}

[Simulated World Scale]
- Number of entities participating in the simulation: {total_nodes}
- Number of relationships generated between entities: {total_edges}
- Entity type distribution: {entity_types}
- Number of active Agents: {total_entities}

[Sample of Future Facts Predicted by the Simulation]
{related_facts_json}

Please examine this future rehearsal from a "God's-eye view":
1. Under the conditions we set, what state did the future present?
2. How did various population groups (Agents) react and act?
3. What noteworthy future trends does this simulation reveal?

Design the most appropriate report section structure based on the prediction results.

[Reminder] Report section count: minimum 2, maximum 5. Content should be concise and focused on core prediction findings."""

# ── Section Generation Prompt ──

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
You are a "Future Prediction Report" writing expert, currently writing a section of the report.

Report Title: {report_title}
Report Summary: {report_summary}
Prediction Scenario (simulation requirement): {simulation_requirement}

Current section to write: {section_title}

═══════════════════════════════════════════════════════════════
[Core Concept]
═══════════════════════════════════════════════════════════════

The simulated world is a rehearsal of the future. We injected specific conditions (simulation requirements) into the simulated world.
Agent behaviors and interactions in the simulation are predictions of future population behavior.

Your task is to:
- Reveal what happened in the future under the set conditions
- Predict how various population groups (Agents) reacted and acted
- Discover noteworthy future trends, risks, and opportunities

Do NOT write this as an analysis of real-world current conditions
DO focus on "what will the future look like" — the simulation results ARE the predicted future

═══════════════════════════════════════════════════════════════
[Most Important Rules - Must Follow]
═══════════════════════════════════════════════════════════════

1. [Must invoke tools to observe the simulated world]
   - You are observing a rehearsal of the future from a "God's-eye view"
   - All content must come from events and Agent behaviors in the simulated world
   - Do NOT use your own knowledge to write report content
   - Each section must invoke tools at least 3 times (maximum 5 times) to observe the simulated world, which represents the future

2. [Must quote Agents' original behaviors and statements]
   - Agent statements and behaviors are predictions of future population behavior
   - Use quotation format in the report to present these predictions, for example:
     > "A certain group would say: original content..."
   - These quotes are the core evidence of simulation predictions

3. [Language consistency - strict and absolute]
   - Report language: {report_language}
   - Write the ENTIRE report in {report_language}. Do NOT switch to a different language at any point.
   - Content returned by tools may contain other languages — translate/adapt as needed to maintain {report_language} throughout
   - When quoting tool output in {report_language}:
     * If {report_language} is Chinese: translate English or mixed content into fluent Chinese before including
     * If {report_language} is English: translate Chinese content into fluent English; keep English content as-is
   - Maintain the original meaning during translation, ensuring natural and smooth expression
   - This rule is absolute. Do not change language mid-section or mid-report under any circumstances
   - This rule applies to both body text and content within quotation blocks (> format)

4. [Faithfully present prediction results]
   - Report content must reflect the simulation results representing the future in the simulated world
   - Do not add information that does not exist in the simulation
   - If information on a certain aspect is insufficient, state this honestly

═══════════════════════════════════════════════════════════════
[Format Specification - Extremely Important!]
═══════════════════════════════════════════════════════════════

[One section = minimum content unit]
- Each section is the smallest content block of the report
- Do NOT use any Markdown headings (#, ##, ###, ####, etc.) within a section
- Do NOT add the section main title at the beginning of the content
- Section titles are automatically added by the system; you only need to write body text
- Use **bold**, paragraph breaks, quotes, and lists to organize content, but do not use headings

[Correct Example]
```
This section analyzes the public opinion dynamics of the event. Through in-depth analysis of simulation data, we found...

**Initial Ignition Phase**

Weibo served as the primary venue for public opinion, bearing the core function of initial information dissemination:

> "Weibo contributed 68% of the initial voice volume..."

**Emotion Amplification Phase**

The Douyin platform further amplified the event's impact:

- Strong visual impact
- High emotional resonance
```

[Incorrect Example]
```
## Executive Summary          <- Wrong! Do not add any headings
### I. Initial Phase          <- Wrong! Do not use ### for sub-sections
#### 1.1 Detailed Analysis   <- Wrong! Do not use #### for further division

This section analyzes...
```

═══════════════════════════════════════════════════════════════
[Available Retrieval Tools] (invoke 3-5 times per section)
═══════════════════════════════════════════════════════════════

{tools_description}

[Tool Usage Recommendations - Mix different tools, do not use just one]
- insight_forge: Deep insight analysis, automatically decomposes questions and retrieves facts and relationships across multiple dimensions
- panorama_search: Wide-angle panoramic search, understand the full picture of events, timelines, and evolution
- quick_search: Quickly verify a specific information point
- interview_agents: Interview simulation Agents, obtain first-person perspectives and real reactions from different roles

═══════════════════════════════════════════════════════════════
[Workflow]
═══════════════════════════════════════════════════════════════

Each reply can only do one of the following two things (not both):

Option A - Invoke a tool:
Output your thinking, then invoke a tool using the following format:
<tool_call>
{{"name": "tool_name", "parameters": {{"param_name": "param_value"}}}}
</tool_call>
The system will execute the tool and return the results to you. You do not need to and cannot write the tool return results yourself.

Option B - Output final content:
When you have obtained sufficient information through tools, output the section content starting with "Final Answer:"

Strictly prohibited:
- Do not include both a tool call and Final Answer in a single reply
- Do not fabricate tool return results (Observations); all tool results are injected by the system
- Invoke at most one tool per reply

═══════════════════════════════════════════════════════════════
[Section Content Requirements]
═══════════════════════════════════════════════════════════════

1. Content must be based on simulation data retrieved via tools
2. Extensively quote original text to demonstrate simulation effectiveness
3. Use Markdown formatting (but headings are prohibited):
   - Use **bold text** to mark key points (as a substitute for sub-headings)
   - Use lists (- or 1.2.3.) to organize key points
   - Use blank lines to separate different paragraphs
   - Do NOT use #, ##, ###, ####, or any other heading syntax
4. [Quotation Format Specification - Must be standalone paragraphs]
   Quotations must be standalone paragraphs with a blank line before and after; they cannot be mixed within a paragraph:

   Correct format:
   ```
   The school's response was considered lacking in substance.

   > "The school's response pattern appeared rigid and slow in the fast-paced social media environment."

   This assessment reflects widespread public dissatisfaction.
   ```

   Incorrect format:
   ```
   The school's response was considered lacking in substance. > "The school's response pattern..." This assessment reflects...
   ```
5. Maintain logical coherence with other sections
6. [Avoid Repetition] Carefully read the completed sections below; do not repeat the same information
7. [Emphasis] Do not add any headings! Use **bold** as a substitute for sub-section titles"""

SECTION_USER_PROMPT_TEMPLATE = """\
Completed section content (please read carefully to avoid repetition):
{previous_content}

═══════════════════════════════════════════════════════════════
[Current Task] Write section: {section_title}
═══════════════════════════════════════════════════════════════

[Important Reminders]
1. Carefully read the completed sections above to avoid repeating the same content!
2. You must invoke tools to retrieve simulation data before starting
3. Mix different tools; do not use just one type
4. Report content must come from retrieval results; do not use your own knowledge

[Format Warning - Must Follow]
- Do NOT write any headings (#, ##, ###, #### are all prohibited)
- Do NOT write "{section_title}" as the opening
- Section titles are automatically added by the system
- Write body text directly, using **bold** as a substitute for sub-section titles

Please begin:
1. First think (Thought) about what information this section needs
2. Then invoke a tool (Action) to retrieve simulation data
3. After collecting sufficient information, output Final Answer (body text only, no headings)"""

# ── ReACT Loop Message Templates ──

REACT_OBSERVATION_TEMPLATE = """\
Observation (retrieval results):

=== Tool {tool_name} returned ===
{result}

═══════════════════════════════════════════════════════════════
Tools invoked {tool_calls_count}/{max_tool_calls} times (used: {used_tools_str}){unused_hint}
- If information is sufficient: output section content starting with "Final Answer:" (must quote the above original text)
- If more information is needed: invoke a tool to continue retrieval
═══════════════════════════════════════════════════════════════"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "[Notice] You have only invoked tools {tool_calls_count} times; at least {min_tool_calls} are required. "
    "Please invoke more tools to retrieve additional simulation data before outputting Final Answer. {unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "Currently only {tool_calls_count} tool invocations have been made; at least {min_tool_calls} are required. "
    "Please invoke tools to retrieve simulation data. {unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "Tool invocation limit reached ({tool_calls_count}/{max_tool_calls}); no more tools can be invoked. "
    'Please immediately output section content starting with "Final Answer:" based on the information already obtained.'
)

REACT_UNUSED_TOOLS_HINT = "\nTip: You have not yet used: {unused_list}. Consider trying different tools for multi-angle information."

REACT_FORCE_FINAL_MSG = "Tool invocation limit reached. Please directly output Final Answer: and generate the section content."

# ── Chat Prompt ──

CHAT_SYSTEM_PROMPT_TEMPLATE = """\
You are a concise and efficient simulation prediction assistant.

[Background]
Prediction conditions: {simulation_requirement}

[Generated Analysis Report]
{report_content}

[Rules]
1. Prioritize answering questions based on the report content above
2. Answer questions directly; avoid lengthy deliberation
3. Only invoke tools to retrieve more data when the report content is insufficient to answer
4. Answers should be concise, clear, and well-organized

[Available Tools] (use only when needed, invoke at most 1-2 times)
{tools_description}

[Tool Invocation Format]
<tool_call>
{{"name": "tool_name", "parameters": {{"param_name": "param_value"}}}}
</tool_call>

[Answer Style]
- Concise and direct; do not write lengthy essays
- Use > format to quote key content
- Provide conclusions first, then explain the reasoning"""

CHAT_OBSERVATION_SUFFIX = "\n\nPlease answer the question concisely."


# ═══════════════════════════════════════════════════════════════
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


class ReportManager:
    """
    Report Manager

    Responsible for report persistence storage and retrieval

    File structure (section-by-section output):
    reports/
      {report_id}/
        meta.json          - Report metadata and status
        outline.json       - Report outline
        progress.json      - Generation progress
        section_01.md      - Section 1
        section_02.md      - Section 2
        ...
        full_report.md     - Complete report
    """

    # Report storage directory
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'reports')

    @classmethod
    def _ensure_reports_dir(cls):
        """Ensure the reports root directory exists"""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)

    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """Get the report folder path"""
        return os.path.join(cls.REPORTS_DIR, report_id)

    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """Ensure the report folder exists and return the path"""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder

    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """Get the report metadata file path"""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")

    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """Get the complete report Markdown file path"""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")

    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """Get the outline file path"""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")

    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """Get the progress file path"""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")

    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """Get the section Markdown file path"""
        return os.path.join(cls._get_report_folder(report_id), f"section_{section_index:02d}.md")

    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """Get the Agent log file path"""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")

    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """Get the console log file path"""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")

    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get console log content

        This is the console output log (INFO, WARNING, etc.) during report generation,
        different from the structured agent_log.jsonl log.

        Args:
            report_id: Report ID
            from_line: Starting line number for reading (for incremental retrieval, 0 means from the beginning)

        Returns:
            {
                "logs": [list of log lines],
                "total_lines": total number of lines,
                "from_line": starting line number,
                "has_more": whether there are more logs
            }
        """
        log_path = cls._get_console_log_path(report_id)

        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }

        logs = []
        total_lines = 0

        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # Keep original log line, strip trailing newline
                    logs.append(line.rstrip('\n\r'))

        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Already read to end
        }

    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        Get the complete console log (retrieve all at once)

        Args:
            report_id: Report ID

        Returns:
            List of log lines
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]

    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get Agent log content

        Args:
            report_id: Report ID
            from_line: Starting line number for reading (for incremental retrieval, 0 means from the beginning)

        Returns:
            {
                "logs": [list of log entries],
                "total_lines": total number of lines,
                "from_line": starting line number,
                "has_more": whether there are more logs
            }
        """
        log_path = cls._get_agent_log_path(report_id)

        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }

        logs = []
        total_lines = 0

        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # Skip lines that fail to parse
                        continue

        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Already read to end
        }

    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get the complete Agent log (retrieve all at once)

        Args:
            report_id: Report ID

        Returns:
            List of log entries
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]

    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        Save the report outline

        Called immediately after the planning phase is complete
        """
        cls._ensure_report_folder(report_id)

        with open(cls._get_outline_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"Outline saved: {report_id}")

    @classmethod
    def save_section(
        cls,
        report_id: str,
        section_index: int,
        section: ReportSection
    ) -> str:
        """
        Save a single section

        Called immediately after each section is generated, enabling section-by-section output

        Args:
            report_id: Report ID
            section_index: Section index (starting from 1)
            section: Section object

        Returns:
            Saved file path
        """
        cls._ensure_report_folder(report_id)

        # Build section Markdown content - clean up potentially duplicate titles
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # Save file
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(f"Section saved: {report_id}/{file_suffix}")
        return file_path

    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        Clean section content

        1. Remove Markdown heading lines at the beginning that duplicate the section title
        2. Convert all ### and lower level headings to bold text

        Args:
            content: Original content
            section_title: Section title

        Returns:
            Cleaned content
        """
        import re

        if not content:
            return content

        content = content.strip()
        lines = content.split('\n')
        cleaned_lines = []
        skip_next_empty = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check if this is a Markdown heading line
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)

            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()

                # Check if this is a duplicate of the section title (skip within first 5 lines)
                if i < 5:
                    if title_text == section_title or title_text.replace(' ', '') == section_title.replace(' ', ''):
                        skip_next_empty = True
                        continue

                # Convert all heading levels (#, ##, ###, ####, etc.) to bold
                # Because section titles are added by the system, content should not contain any headings
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # Add blank line
                continue

            # If the previous line was a skipped title and the current line is empty, also skip
            if skip_next_empty and stripped == '':
                skip_next_empty = False
                continue

            skip_next_empty = False
            cleaned_lines.append(line)

        # Remove leading blank lines
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)

        # Remove leading separator lines
        while cleaned_lines and cleaned_lines[0].strip() in ['---', '***', '___']:
            cleaned_lines.pop(0)
            # Also remove blank lines after the separator
            while cleaned_lines and cleaned_lines[0].strip() == '':
                cleaned_lines.pop(0)

        return '\n'.join(cleaned_lines)

    @classmethod
    def update_progress(
        cls,
        report_id: str,
        status: str,
        progress: int,
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None
    ) -> None:
        """
        Update report generation progress

        The frontend can read progress.json to get real-time progress
        """
        cls._ensure_report_folder(report_id)

        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": _now_iso()
        }

        with open(cls._get_progress_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)

    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report generation progress"""
        path = cls._get_progress_path(report_id)

        if not os.path.exists(path):
            return None

        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get the list of generated sections

        Returns information about all saved section files
        """
        folder = cls._get_report_folder(report_id)

        if not os.path.exists(folder):
            return []

        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse section index from filename
                parts = filename.replace('.md', '').split('_')
                section_index = int(parts[1])

                sections.append({
                    "filename": filename,
                    "section_index": section_index,
                    "content": content
                })

        return sections

    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
        Assemble the complete report

        Assemble the full report from saved section files and perform title cleanup
        """
        folder = cls._get_report_folder(report_id)

        # Build report header
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"

        # Read all section files in order
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]

        # Post-processing: clean up heading issues in the entire report
        md_content = cls._post_process_report(md_content, outline)

        # Save complete report
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(f"Complete report assembled: {report_id}")
        return md_content

    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
        Post-process report content

        1. Remove duplicate headings
        2. Keep report main title (#) and section titles (##), remove other heading levels (###, ####, etc.)
        3. Clean up excess blank lines and separator lines

        Args:
            content: Original report content
            outline: Report outline

        Returns:
            Processed content
        """
        import re

        lines = content.split('\n')
        processed_lines = []
        prev_was_heading = False

        # Collect all section titles from the outline
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Check if this is a heading line
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)

            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # Check if this is a duplicate heading (same content heading appears within 5 consecutive lines)
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r'^(#{1,6})\s+(.+)$', prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break

                if is_duplicate:
                    # Skip duplicate heading and trailing blank lines
                    i += 1
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue

                # Heading level handling:
                # - # (level=1) keep only report main title
                # - ## (level=2) keep section titles
                # - ### and below (level>=3) convert to bold text

                if level == 1:
                    if title == outline.title:
                        # Keep report main title
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # Section title incorrectly using #, correct to ##
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # Other level-1 headings convert to bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        # Keep section titles
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # Non-section level-2 headings convert to bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # ### and lower level headings convert to bold text
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False

                i += 1
                continue

            elif stripped == '---' and prev_was_heading:
                # Skip separator lines immediately following a heading
                i += 1
                continue

            elif stripped == '' and prev_was_heading:
                # Keep only one blank line after a heading
                if processed_lines and processed_lines[-1].strip() != '':
                    processed_lines.append(line)
                prev_was_heading = False

            else:
                processed_lines.append(line)
                prev_was_heading = False

            i += 1

        # Clean up multiple consecutive blank lines (keep at most 2)
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)

        return '\n'.join(result_lines)

    @classmethod
    def save_report(cls, report: Report) -> None:
        """Save report metadata and complete report"""
        cls._ensure_report_folder(report.report_id)

        # Save metadata JSON
        with open(cls._get_report_path(report.report_id), 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

        # Save outline
        if report.outline:
            cls.save_outline(report.report_id, report.outline)

        # Save complete Markdown report
        if report.markdown_content:
            with open(cls._get_report_markdown_path(report.report_id), 'w', encoding='utf-8') as f:
                f.write(report.markdown_content)

        logger.info(f"Report saved: {report.report_id}")

    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """Get report"""
        path = cls._get_report_path(report_id)

        if not os.path.exists(path):
            # Backward compatibility: check files stored directly in the reports directory
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Reconstruct Report object
        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            sections = []
            for s in outline_data.get('sections', []):
                sections.append(ReportSection(
                    title=s['title'],
                    content=s.get('content', '')
                ))
            outline = ReportOutline(
                title=outline_data['title'],
                summary=outline_data['summary'],
                sections=sections
            )

        # If markdown_content is empty, try reading from full_report.md
        markdown_content = data.get('markdown_content', '')
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()

        return Report(
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            simulation_requirement=data['simulation_requirement'],
            status=ReportStatus(data['status']),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error')
        )

    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """Get report by simulation ID"""
        cls._ensure_reports_dir()

        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # New format: folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report and report.simulation_id == simulation_id:
                    return report
            # Backward compatibility: JSON file
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report and report.simulation_id == simulation_id:
                    return report

        return None

    @classmethod
    def list_reports(cls, simulation_id: Optional[str] = None, limit: int = 50) -> List[Report]:
        """List reports"""
        cls._ensure_reports_dir()

        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # New format: folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            # Backward compatibility: JSON file
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)

        # Sort by creation time descending
        reports.sort(key=lambda r: r.created_at, reverse=True)

        return reports[:limit]

    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """Delete report (entire folder)"""
        import shutil

        folder_path = cls._get_report_folder(report_id)

        # New format: delete entire folder
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(f"Report folder deleted: {report_id}")
            return True

        # Backward compatibility: delete individual files
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")

        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True

        return deleted
