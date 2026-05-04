"""Shared types, dataclasses, prompt templates, and constants for report generation."""

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
