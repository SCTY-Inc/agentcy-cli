"""
OASIS Twitter Simulation Script
This script reads parameters from a config file to execute simulations, fully automated.

Features:
- After simulation completes, does not shut down immediately; enters command-waiting mode
- Supports receiving Interview commands via IPC
- Supports single Agent interview and batch interviews
- Supports remote environment shutdown command

Usage:
    python run_twitter_simulation.py --config /path/to/simulation_config.json
    python run_twitter_simulation.py --config /path/to/simulation_config.json --no-wait  # Shut down immediately after completion
"""

import os
import sys
from typing import Dict, List

# Add project root to path
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_scripts_dir, '..'))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, _project_root)

# Load .env file from project root
from dotenv import load_dotenv
_env_file = os.path.join(_project_root, '.env')
if os.path.exists(_env_file):
    load_dotenv(_env_file)

from agentcy_forecast.utils.oasis_llm import create_oasis_model, get_oasis_semaphore
from base_simulation_runner import BaseSimulationRunner, run_simulation_main

try:
    import oasis
    from oasis import (
        ActionType,
        ManualAction,
        generate_twitter_agent_graph,
    )
except ImportError as e:
    print(f"Error: missing dependency {e}")
    print(
        "Install the optional simulation runtime for this fork with Python 3.11: "
        "make install-forecast-simulation"
    )
    sys.exit(1)


class TwitterSimulationRunner(BaseSimulationRunner):
    """Twitter simulation runner"""

    PLATFORM_NAME = "Twitter"

    # Available Twitter actions (excludes INTERVIEW; INTERVIEW can only be
    # triggered manually via ManualAction)
    AVAILABLE_ACTIONS = [
        ActionType.CREATE_POST,
        ActionType.LIKE_POST,
        ActionType.REPOST,
        ActionType.FOLLOW,
        ActionType.DO_NOTHING,
        ActionType.QUOTE_POST,
    ]

    def _get_profile_path(self) -> str:
        """Get Profile file path (OASIS Twitter uses CSV format)"""
        return os.path.join(self.simulation_dir, "twitter_profiles.csv")

    def _get_db_path(self) -> str:
        """Get database path"""
        return os.path.join(self.simulation_dir, "twitter_simulation.db")

    def _create_model(self):
        """Create an LLM model, including CLI-backed providers."""
        return create_oasis_model(self.config, use_boost=False)

    async def _generate_agent_graph(self, profile_path: str, model, available_actions: List):
        return await generate_twitter_agent_graph(
            profile_path=profile_path,
            model=model,
            available_actions=available_actions,
        )

    def _get_oasis_platform(self):
        return oasis.DefaultPlatformType.TWITTER

    def _get_oasis_semaphore(self):
        return get_oasis_semaphore(self.config, use_boost=False)

    def _build_initial_actions(
        self, env, initial_posts: List, agent_names: Dict,
        action_logger, total_actions: int, initial_action_count: int
    ):
        """Build initial actions dict. Twitter: one ManualAction per agent slot."""
        initial_actions = {}
        for post in initial_posts:
            agent_id = post.get("poster_agent_id", 0)
            content = post.get("content", "")
            try:
                agent = env.agent_graph.get_agent(agent_id)
                initial_actions[agent] = ManualAction(
                    action_type=ActionType.CREATE_POST,
                    action_args={"content": content}
                )
                action_logger.log_action(
                    round_num=0,
                    agent_id=agent_id,
                    agent_name=agent_names.get(agent_id, f"Agent_{agent_id}"),
                    action_type="CREATE_POST",
                    action_args={"content": content},
                )
                total_actions += 1
                initial_action_count += 1
            except Exception as e:
                print(f"  Warning: unable to create initial post for Agent {agent_id}: {e}")
        return initial_actions, total_actions, initial_action_count


if __name__ == "__main__":
    run_simulation_main(TwitterSimulationRunner, "Twitter")
