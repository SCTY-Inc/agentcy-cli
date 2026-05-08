"""
Agent interview mixin for GraphToolsService.
Provides: interview_agents and all supporting private helpers
(_clean_tool_call_response, _load_agent_profiles, _select_agents_for_interview,
_generate_interview_questions, _generate_interview_summary).
"""

import csv
import json
import os
import re
from typing import Any

from ..utils.logger import get_logger
from .graph_models import AgentInterview, InterviewResult

logger = get_logger('mirofish.graph_tools')


class GraphInterviewMixin:
    """
    Mixin providing agent interview functionality.
    Expects self to have: llm (LLMClient).
    """

    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: list[str] = None
    ) -> InterviewResult:
        """
        [InterviewAgents - In-Depth Interview]

        Calls the real OASIS interview API to interview agents running in the simulation:
        1. Automatically reads profile files to learn about all simulated agents
        2. Uses LLM to analyze interview requirements and intelligently select the most relevant agents
        3. Uses LLM to generate interview questions
        4. Calls /api/simulation/interview/batch endpoint for real interviews (dual-platform simultaneous interviews)
        5. Integrates all interview results and generates an interview report

        [Important] This feature requires the simulation environment to be running (OASIS environment not shut down)

        [Use Cases]
        - Need to understand event perspectives from different roles
        - Need to collect opinions and viewpoints from multiple parties
        - Need to obtain real responses from simulated agents (not LLM-simulated)

        Args:
            simulation_id: Simulation ID (used to locate profile files and call interview API)
            interview_requirement: Interview requirement description (unstructured, e.g., "understand students' views on the event")
            simulation_requirement: Simulation requirement background (optional)
            max_agents: Maximum number of agents to interview
            custom_questions: Custom interview questions (optional, auto-generated if not provided)

        Returns:
            InterviewResult: Interview result
        """
        from .simulation_runner import SimulationRunner

        logger.info(f"InterviewAgents in-depth interview (real API): {interview_requirement[:50]}...")

        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )

        # Step 1: Read profile files
        profiles = self._load_agent_profiles(simulation_id)

        if not profiles:
            logger.warning(f"No profile files found for simulation {simulation_id}")
            result.summary = "No agent profile files found for interview"
            return result

        result.total_agents = len(profiles)
        logger.info(f"Loaded {len(profiles)} agent profiles")

        # Step 2: Use LLM to select agents to interview (returns agent_id list)
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )

        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(f"Selected {len(selected_agents)} agents for interview: {selected_indices}")

        # Step 3: Generate interview questions (if not provided)
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(f"Generated {len(result.interview_questions)} interview questions")

        # Combine questions into a single interview prompt
        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])

        # Add optimization prefix to constrain agent response format
        INTERVIEW_PROMPT_PREFIX = (
            "You are being interviewed. Please draw on your persona, all past memories, and actions "
            "to answer the following questions directly in plain text.\n"
            "Response requirements:\n"
            "1. Answer directly in natural language; do not call any tools\n"
            "2. Do not return JSON format or tool call format\n"
            "3. Do not use Markdown headings (such as #, ##, ###)\n"
            "4. Answer each question in order, starting each answer with 'Question X:' (where X is the question number)\n"
            "5. Separate answers to each question with a blank line\n"
            "6. Provide substantive answers, with at least 2-3 sentences per question\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"

        # Step 4: Call the real interview API (no platform specified, defaults to dual-platform interview)
        try:
            # Build batch interview list (no platform specified, dual-platform interview)
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt  # Use optimized prompt
                    # No platform specified, API will interview on both Twitter and Reddit
                })

            logger.info(f"Calling batch interview API (dual-platform): {len(interviews_request)} agents")

            # Call SimulationRunner's batch interview method (no platform passed, dual-platform interview)
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,  # No platform specified, dual-platform interview
                timeout=180.0   # Dual-platform needs longer timeout
            )

            logger.info(f"Interview API returned: {api_result.get('interviews_count', 0)} results, success={api_result.get('success')}")

            if not api_result.get("success", False):
                error_msg = api_result.get("error", "Unknown error")
                logger.warning(f"Interview API returned failure: {error_msg}")
                result.summary = f"Interview API call failed: {error_msg}. Please check the OASIS simulation environment status."
                return result

            # Step 5: Parse API return results and build AgentInterview objects
            # Dual-platform mode return format: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}

            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "Unknown")
                agent_bio = agent.get("bio", "")

                # Get interview results for this agent on both platforms
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})

                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # Clean possible tool call JSON wrappers
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # Always output dual-platform markers
                twitter_text = twitter_response if twitter_response else "(No response from this platform)"
                reddit_text = reddit_response if reddit_response else "(No response from this platform)"
                response_text = f"[Twitter Platform Response]\n{twitter_text}\n\n[Reddit Platform Response]\n{reddit_text}"

                # Extract key quotes (from responses on both platforms)
                combined_responses = f"{twitter_response} {reddit_response}"

                # Clean response text: remove markers, numbering, Markdown, and other noise
                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                # Remove question markers in both Chinese ("问题" = "Question") and English
                clean_text = re.sub(r'(?:问题|Question)\s*\d+[：:]\s*', '', clean_text)
                clean_text = re.sub(r'【[^】]+】', '', clean_text)  # Remove Chinese bracket markers 【...】

                # Strategy 1 (primary): Extract complete sentences with substantive content
                sentences = re.split(r'[。！？.!?]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W，,；;：:、]+', s.strip())
                    and not s.strip().startswith(('{', '问题', 'Question'))  # "问题" = Chinese for "Question"
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "。" for s in meaningful[:3]]  # "。" = Chinese full-stop period

                # Strategy 2 (supplementary): Correctly paired Chinese quotation marks with long text
                if not key_quotes:
                    paired = re.findall(r'“([^“”]{15,100})”', clean_text)
                    paired += re.findall(r'「([^「」]{15,100})」', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[，,；;：:、]', q)][:3]

                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],  # Extended bio length limit
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)

            result.interviewed_count = len(result.interviews)

        except ValueError as e:
            # Simulation environment not running
            logger.warning(f"Interview API call failed (environment not running?): {e}")
            result.summary = f"Interview failed: {str(e)}. The simulation environment may have been shut down. Please ensure the OASIS environment is running."
            return result
        except Exception as e:
            logger.error(f"Interview API call exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"An error occurred during the interview: {str(e)}"
            return result

        # Step 6: Generate interview summary
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )

        logger.info(f"InterviewAgents completed: interviewed {result.interviewed_count} agents (dual-platform)")
        return result

    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """Clean JSON tool call wrappers from agent responses and extract actual content"""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> list[dict[str, Any]]:
        """Load agent profile files for the simulation"""
        # Build profile file path
        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )

        profiles = []

        # Prefer reading Reddit JSON format
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(f"Loaded {len(profiles)} profiles from reddit_profiles.json")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read reddit_profiles.json: {e}")

        # Try reading Twitter CSV format
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "Unknown"
                        })
                logger.info(f"Loaded {len(profiles)} profiles from twitter_profiles.csv")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read twitter_profiles.csv: {e}")

        return profiles

    def _select_agents_for_interview(
        self,
        profiles: list[dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """
        Use LLM to select agents to interview

        Returns:
            tuple: (selected_agents, selected_indices, reasoning)
                - selected_agents: Full information list of selected agents
                - selected_indices: Index list of selected agents (for API calls)
                - reasoning: Selection reasoning
        """

        # Build agent summary list
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "Unknown"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)

        system_prompt = """You are a professional interview planning expert. Your task is to select the most suitable interview subjects from a list of simulated agents based on interview requirements.

Selection criteria:
1. The agent's identity/profession is relevant to the interview topic
2. The agent may hold unique or valuable perspectives
3. Select diverse viewpoints (e.g., supporters, opponents, neutral parties, professionals, etc.)
4. Prioritize roles directly related to the event

Return in JSON format:
{
    "selected_indices": [list of selected agent indices],
    "reasoning": "Explanation of selection reasoning"
}"""

        user_prompt = f"""Interview requirement:
{interview_requirement}

Simulation background:
{simulation_requirement if simulation_requirement else "Not provided"}

Available agent list ({len(agent_summaries)} total):
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

Please select up to {max_agents} agents most suitable for interview and explain the selection reasoning."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "Automatically selected based on relevance")

            # Get full information of selected agents
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)

            return selected_agents, valid_indices, reasoning

        except Exception as e:
            logger.warning(f"LLM agent selection failed, using default selection: {e}")
            # Fallback: select the first N agents
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "Using default selection strategy"

    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: list[dict[str, Any]]
    ) -> list[str]:
        """Use LLM to generate interview questions"""

        agent_roles = [a.get("profession", "Unknown") for a in selected_agents]

        system_prompt = """You are a professional journalist/interviewer. Generate 3-5 in-depth interview questions based on the interview requirements.

Question requirements:
1. Open-ended questions that encourage detailed responses
2. Questions that different roles might answer differently
3. Cover multiple dimensions including facts, opinions, and feelings
4. Natural language, like a real interview
5. Keep each question under 50 words, concise and clear
6. Ask directly, do not include background descriptions or prefixes

Return in JSON format: {"questions": ["question 1", "question 2", ...]}"""

        user_prompt = f"""Interview requirement: {interview_requirement}

Simulation background: {simulation_requirement if simulation_requirement else "Not provided"}

Interviewee roles: {', '.join(agent_roles)}

Please generate 3-5 interview questions."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )

            return response.get("questions", [f"What are your thoughts on {interview_requirement}?"])

        except Exception as e:
            logger.warning(f"Failed to generate interview questions: {e}")
            return [
                f"What is your perspective on {interview_requirement}?",
                "What impact does this have on you or the group you represent?",
                "How do you think this issue should be resolved or improved?"
            ]

    def _generate_interview_summary(
        self,
        interviews: list[AgentInterview],
        interview_requirement: str
    ) -> str:
        """Generate interview summary"""

        if not interviews:
            return "No interviews were completed"

        # Collect all interview content
        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"[{interview.agent_name} ({interview.agent_role})]\n{interview.response[:500]}")

        system_prompt = """You are a professional news editor. Based on responses from multiple interviewees, generate an interview summary.

Summary requirements:
1. Distill the main viewpoints from each party
2. Identify areas of consensus and disagreement
3. Highlight valuable quotes
4. Remain objective and neutral, without favoring any side
5. Keep within 1000 words

Format constraints (must be followed):
- Use plain text paragraphs, separated by blank lines
- Do not use Markdown headings (such as #, ##, ###)
- Do not use divider lines (such as ---, ***)
- When quoting interviewees, use quotation marks
- You may use **bold** to mark keywords, but do not use other Markdown syntax"""

        user_prompt = f"""Interview topic: {interview_requirement}

Interview content:
{"".join(interview_texts)}

Please generate an interview summary."""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary

        except Exception as e:
            logger.warning(f"Failed to generate interview summary: {e}")
            # Fallback: simple concatenation
            return f"A total of {len(interviews)} interviewees were interviewed, including: " + ", ".join([i.agent_name for i in interviews])
