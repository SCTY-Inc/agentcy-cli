"""
Base simulation runner shared by run_twitter_simulation.py and run_reddit_simulation.py.

Provides:
- UnicodeFormatter, MaxTokensWarningFilter, setup_oasis_logging
- IPC constants, CommandType, IPCHandler
- BaseSimulationRunner (abstract base class)
- setup_signal_handlers, run_simulation_main (entrypoint helper)

Platform scripts subclass BaseSimulationRunner and override the small set of
platform-specific hooks; everything else is inherited unchanged.
"""

import asyncio
import json
import logging
import os
import random
import re
import signal
import sqlite3
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Global signal-handling state (written by the platform scripts via module ref)
# ---------------------------------------------------------------------------
_shutdown_event = None
_cleanup_done = False


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

class UnicodeFormatter(logging.Formatter):
    """Custom formatter that converts Unicode escape sequences to readable characters"""

    UNICODE_ESCAPE_PATTERN = re.compile(r'\\u([0-9a-fA-F]{4})')

    def format(self, record):
        result = super().format(record)

        def replace_unicode(match):
            try:
                return chr(int(match.group(1), 16))
            except (ValueError, OverflowError):
                return match.group(0)

        return self.UNICODE_ESCAPE_PATTERN.sub(replace_unicode, result)


class MaxTokensWarningFilter(logging.Filter):
    """Filter out camel-ai warnings about max_tokens"""

    def filter(self, record):
        if "max_tokens" in record.getMessage() and "Invalid or missing" in record.getMessage():
            return False
        return True


# Apply filter at import time so it is in effect before camel code runs.
logging.getLogger().addFilter(MaxTokensWarningFilter())


def setup_oasis_logging(log_dir: str):
    """Configure OASIS logging with fixed-name log files, cleaning up old logs."""
    os.makedirs(log_dir, exist_ok=True)

    for f in os.listdir(log_dir):
        old_log = os.path.join(log_dir, f)
        if os.path.isfile(old_log) and f.endswith('.log'):
            try:
                os.remove(old_log)
            except OSError:
                pass

    formatter = UnicodeFormatter("%(levelname)s - %(asctime)s - %(name)s - %(message)s")

    loggers_config = {
        "social.agent": os.path.join(log_dir, "social.agent.log"),
        "social.twitter": os.path.join(log_dir, "social.twitter.log"),
        "social.rec": os.path.join(log_dir, "social.rec.log"),
        "oasis.env": os.path.join(log_dir, "oasis.env.log"),
        "table": os.path.join(log_dir, "table.log"),
    }

    for logger_name, log_file in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.propagate = False


# ---------------------------------------------------------------------------
# IPC
# ---------------------------------------------------------------------------

IPC_COMMANDS_DIR = "ipc_commands"
IPC_RESPONSES_DIR = "ipc_responses"
ENV_STATUS_FILE = "env_status.json"


class CommandType:
    """Command type constants"""
    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"


class IPCHandler:
    """IPC command handler (platform-agnostic; db_path supplied by caller)."""

    def __init__(self, simulation_dir: str, env, agent_graph, db_path: str):
        self.simulation_dir = simulation_dir
        self.env = env
        self.agent_graph = agent_graph
        self.db_path = db_path
        self.commands_dir = os.path.join(simulation_dir, IPC_COMMANDS_DIR)
        self.responses_dir = os.path.join(simulation_dir, IPC_RESPONSES_DIR)
        self.status_file = os.path.join(simulation_dir, ENV_STATUS_FILE)
        self._running = True

        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

    def update_status(self, status: str):
        """Update environment status"""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

    def poll_command(self) -> Optional[Dict[str, Any]]:
        """Poll for pending commands"""
        if not os.path.exists(self.commands_dir):
            return None

        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))

        command_files.sort(key=lambda x: x[1])

        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

        return None

    def send_response(self, command_id: str, status: str, result: Dict = None, error: str = None):
        """Send a response"""
        response = {
            "command_id": command_id,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }

        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=2)

        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass

    async def handle_interview(self, command_id: str, agent_id: int, prompt: str) -> bool:
        """Handle a single Agent interview command."""
        # Import here to avoid top-level oasis dependency in the base module
        from oasis import ActionType, ManualAction
        try:
            agent = self.agent_graph.get_agent(agent_id)
            interview_action = ManualAction(
                action_type=ActionType.INTERVIEW,
                action_args={"prompt": prompt}
            )
            actions = {agent: interview_action}
            await self.env.step(actions)
            result = self._get_interview_result(agent_id)
            self.send_response(command_id, "completed", result=result)
            print(f"  Interview completed: agent_id={agent_id}")
            return True
        except Exception as e:
            error_msg = str(e)
            print(f"  Interview failed: agent_id={agent_id}, error={error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False

    async def handle_batch_interview(self, command_id: str, interviews: List[Dict]) -> bool:
        """Handle a batch interview command."""
        from oasis import ActionType, ManualAction
        try:
            actions = {}
            agent_prompts = {}

            for interview in interviews:
                agent_id = interview.get("agent_id")
                prompt = interview.get("prompt", "")
                try:
                    agent = self.agent_graph.get_agent(agent_id)
                    actions[agent] = ManualAction(
                        action_type=ActionType.INTERVIEW,
                        action_args={"prompt": prompt}
                    )
                    agent_prompts[agent_id] = prompt
                except Exception as e:
                    print(f"  Warning: unable to get Agent {agent_id}: {e}")

            if not actions:
                self.send_response(command_id, "failed", error="No valid Agents")
                return False

            await self.env.step(actions)

            results = {}
            for agent_id in agent_prompts.keys():
                results[agent_id] = self._get_interview_result(agent_id)

            self.send_response(command_id, "completed", result={
                "interviews_count": len(results),
                "results": results
            })
            print(f"  Batch Interview completed: {len(results)} Agents")
            return True
        except Exception as e:
            error_msg = str(e)
            print(f"  Batch Interview failed: {error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False

    def _get_interview_result(self, agent_id: int) -> Dict[str, Any]:
        """Get the latest Interview result from the database"""
        from oasis import ActionType
        result = {
            "agent_id": agent_id,
            "response": None,
            "timestamp": None
        }

        if not os.path.exists(self.db_path):
            return result

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, info, created_at
                FROM trace
                WHERE action = ? AND user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (ActionType.INTERVIEW.value, agent_id))

            row = cursor.fetchone()
            if row:
                user_id, info_json, created_at = row
                try:
                    info = json.loads(info_json) if info_json else {}
                    result["response"] = info.get("response", info)
                    result["timestamp"] = created_at
                except json.JSONDecodeError:
                    result["response"] = info_json

            conn.close()
        except Exception as e:
            print(f"  Failed to read Interview result: {e}")

        return result

    async def process_commands(self) -> bool:
        """
        Process all pending commands.

        Returns:
            True to continue running, False to exit.
        """
        command = self.poll_command()
        if not command:
            return True

        command_id = command.get("command_id")
        command_type = command.get("command_type")
        args = command.get("args", {})

        print(f"\nReceived IPC command: {command_type}, id={command_id}")

        if command_type == CommandType.INTERVIEW:
            await self.handle_interview(
                command_id,
                args.get("agent_id", 0),
                args.get("prompt", "")
            )
            return True

        elif command_type == CommandType.BATCH_INTERVIEW:
            await self.handle_batch_interview(
                command_id,
                args.get("interviews", [])
            )
            return True

        elif command_type == CommandType.CLOSE_ENV:
            print("Received close environment command")
            self.send_response(command_id, "completed", result={"message": "Environment is shutting down"})
            return False

        else:
            self.send_response(command_id, "failed", error=f"Unknown command type: {command_type}")
            return True


# ---------------------------------------------------------------------------
# Base runner
# ---------------------------------------------------------------------------

class BaseSimulationRunner(ABC):
    """
    Shared simulation lifecycle for OASIS platforms.

    Subclasses must implement:
      - PLATFORM_NAME: str          — human label ("Twitter" / "Reddit")
      - AVAILABLE_ACTIONS: list     — ActionType members available to agents
      - _get_profile_path() -> str  — path to agent profile file
      - _get_db_path() -> str       — path to simulation database
      - _create_model()             — returns an OASIS-compatible LLM model
      - _generate_agent_graph(profile_path, model, available_actions) — coroutine
      - _get_oasis_platform()       — oasis.DefaultPlatformType value
      - _get_oasis_semaphore()      — semaphore for oasis.make()
      - _build_initial_actions(env, initial_posts, agent_names, action_logger,
                               total_actions, initial_action_count)
            -> (initial_actions dict, total_actions int, initial_action_count int)
    """

    PLATFORM_NAME: str = ""
    AVAILABLE_ACTIONS: List = []

    def __init__(self, config_path: str, wait_for_commands: bool = True):
        self.config_path = config_path
        self.config = self._load_config()
        self.simulation_dir = os.path.dirname(config_path)
        self.wait_for_commands = wait_for_commands
        self.env = None
        self.agent_graph = None
        self.ipc_handler = None

    # ------------------------------------------------------------------
    # Concrete shared helpers
    # ------------------------------------------------------------------

    def _load_config(self) -> Dict[str, Any]:
        """Load the configuration file"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_active_agents_for_round(self, env, current_hour: int, round_num: int) -> List:
        """
        Determine which Agents to activate for this round based on time and config.
        """
        time_config = self.config.get("time_config", {})
        agent_configs = self.config.get("agent_configs", [])

        base_min = time_config.get("agents_per_hour_min", 5)
        base_max = time_config.get("agents_per_hour_max", 20)

        peak_hours = time_config.get("peak_hours", [9, 10, 11, 14, 15, 20, 21, 22])
        off_peak_hours = time_config.get("off_peak_hours", [0, 1, 2, 3, 4, 5])

        if current_hour in peak_hours:
            multiplier = time_config.get("peak_activity_multiplier", 1.5)
        elif current_hour in off_peak_hours:
            multiplier = time_config.get("off_peak_activity_multiplier", 0.3)
        else:
            multiplier = 1.0

        target_count = int(random.uniform(base_min, base_max) * multiplier)

        candidates = []
        for cfg in agent_configs:
            agent_id = cfg.get("agent_id", 0)
            active_hours = cfg.get("active_hours", list(range(8, 23)))
            activity_level = cfg.get("activity_level", 0.5)

            if current_hour not in active_hours:
                continue

            if random.random() < activity_level:
                candidates.append(agent_id)

        selected_ids = random.sample(
            candidates,
            min(target_count, len(candidates))
        ) if candidates else []

        active_agents = []
        for agent_id in selected_ids:
            try:
                agent = env.agent_graph.get_agent(agent_id)
                active_agents.append((agent_id, agent))
            except Exception:
                pass

        return active_agents

    # ------------------------------------------------------------------
    # Abstract hooks
    # ------------------------------------------------------------------

    @abstractmethod
    def _get_profile_path(self) -> str:
        """Return path to the agent profile file."""

    @abstractmethod
    def _get_db_path(self) -> str:
        """Return path to the simulation SQLite database."""

    @abstractmethod
    def _create_model(self):
        """Create and return an OASIS-compatible LLM model."""

    @abstractmethod
    async def _generate_agent_graph(self, profile_path: str, model, available_actions: List):
        """Generate and return the platform-specific agent graph."""

    @abstractmethod
    def _get_oasis_platform(self):
        """Return the oasis.DefaultPlatformType for this platform."""

    @abstractmethod
    def _get_oasis_semaphore(self):
        """Return the semaphore for oasis.make()."""

    @abstractmethod
    def _build_initial_actions(
        self, env, initial_posts: List, agent_names: Dict,
        action_logger, total_actions: int, initial_action_count: int
    ):
        """
        Build the initial_actions dict from initial_posts config, logging each action.

        Returns (initial_actions, total_actions, initial_action_count).
        Platform scripts differ here: Reddit supports multiple posts per agent.
        """

    # ------------------------------------------------------------------
    # Main run loop (shared)
    # ------------------------------------------------------------------

    async def run(self, max_rounds: int = None):
        """Run simulation. Platform name comes from PLATFORM_NAME."""
        import oasis
        from oasis import LLMAction
        from action_logger import PlatformActionLogger
        from action_trace import fetch_new_actions_from_db, get_agent_names_from_config

        print("=" * 60)
        print(f"OASIS {self.PLATFORM_NAME} Simulation")
        print(f"Config file: {self.config_path}")
        print(f"Simulation ID: {self.config.get('simulation_id', 'unknown')}")
        print(f"Command-waiting mode: {'enabled' if self.wait_for_commands else 'disabled'}")
        print("=" * 60)

        time_config = self.config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = (total_hours * 60) // minutes_per_round

        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                print(f"\nRounds truncated: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")

        print(f"\nSimulation parameters:")
        print(f"  - Total simulation duration: {total_hours} hours")
        print(f"  - Time per round: {minutes_per_round} minutes")
        print(f"  - Total rounds: {total_rounds}")
        if max_rounds:
            print(f"  - Max rounds limit: {max_rounds}")
        print(f"  - Agent count: {len(self.config.get('agent_configs', []))}")

        print("\nInitializing LLM model...")
        model = self._create_model()

        print("Loading Agent Profile...")
        profile_path = self._get_profile_path()
        if not os.path.exists(profile_path):
            print(f"Error: Profile file does not exist: {profile_path}")
            return

        self.agent_graph = await self._generate_agent_graph(
            profile_path=profile_path,
            model=model,
            available_actions=self.AVAILABLE_ACTIONS,
        )

        db_path = self._get_db_path()
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"Deleted old database: {db_path}")

        print("Creating OASIS environment...")
        self.env = oasis.make(
            agent_graph=self.agent_graph,
            platform=self._get_oasis_platform(),
            database_path=db_path,
            semaphore=self._get_oasis_semaphore(),
        )

        await self.env.reset()
        print("Environment initialized\n")

        self.ipc_handler = IPCHandler(self.simulation_dir, self.env, self.agent_graph, db_path)
        self.ipc_handler.update_status("running")
        action_logger = PlatformActionLogger(self.PLATFORM_NAME.lower(), self.simulation_dir)
        agent_names = get_agent_names_from_config(self.config)
        action_logger.log_simulation_start(self.config)
        total_actions = 0
        last_rowid = 0

        event_config = self.config.get("event_config", {})
        initial_posts = event_config.get("initial_posts", [])
        action_logger.log_round_start(0, 0)
        initial_action_count = 0

        if initial_posts:
            print(f"Executing initial events ({len(initial_posts)} initial posts)...")
            initial_actions, total_actions, initial_action_count = self._build_initial_actions(
                self.env, initial_posts, agent_names, action_logger,
                total_actions, initial_action_count
            )
            if initial_actions:
                await self.env.step(initial_actions)
                print(f"  Published {len(initial_actions)} initial posts")

        action_logger.log_round_end(0, initial_action_count)

        print("\nStarting simulation loop...")
        start_time = datetime.now()

        for round_num in range(total_rounds):
            simulated_minutes = round_num * minutes_per_round
            simulated_hour = (simulated_minutes // 60) % 24
            simulated_day = simulated_minutes // (60 * 24) + 1

            active_agents = self._get_active_agents_for_round(
                self.env, simulated_hour, round_num
            )
            action_logger.log_round_start(round_num + 1, simulated_hour)

            if not active_agents:
                action_logger.log_round_end(round_num + 1, 0)
                continue

            actions = {agent: LLMAction() for _, agent in active_agents}

            await self.env.step(actions)
            actual_actions, last_rowid = fetch_new_actions_from_db(
                db_path,
                last_rowid,
                agent_names,
            )
            round_action_count = 0
            for action_data in actual_actions:
                action_logger.log_action(
                    round_num=round_num + 1,
                    agent_id=action_data["agent_id"],
                    agent_name=action_data["agent_name"],
                    action_type=action_data["action_type"],
                    action_args=action_data["action_args"],
                )
                total_actions += 1
                round_action_count += 1
            action_logger.log_round_end(round_num + 1, round_action_count)

            if (round_num + 1) % 10 == 0 or round_num == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                progress = (round_num + 1) / total_rounds * 100
                print(f"  [Day {simulated_day}, {simulated_hour:02d}:00] "
                      f"Round {round_num + 1}/{total_rounds} ({progress:.1f}%) "
                      f"- {len(active_agents)} agents active "
                      f"- elapsed: {elapsed:.1f}s")

        action_logger.log_simulation_end(total_rounds, total_actions)
        total_elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\nSimulation loop completed!")
        print(f"  - Total time elapsed: {total_elapsed:.1f}s")
        print(f"  - Database: {db_path}")

        if self.wait_for_commands:
            print("\n" + "=" * 60)
            print("Entering command-waiting mode - environment stays running")
            print("Supported commands: interview, batch_interview, close_env")
            print("=" * 60)

            self.ipc_handler.update_status("alive")

            try:
                while not _shutdown_event.is_set():
                    should_continue = await self.ipc_handler.process_commands()
                    if not should_continue:
                        break
                    try:
                        await asyncio.wait_for(_shutdown_event.wait(), timeout=0.5)
                        break
                    except asyncio.TimeoutError:
                        pass
            except KeyboardInterrupt:
                print("\nReceived interrupt signal")
            except asyncio.CancelledError:
                print("\nTask was cancelled")
            except Exception as e:
                print(f"\nCommand processing error: {e}")

            print("\nShutting down environment...")

        self.ipc_handler.update_status("stopped")
        await self.env.close()

        print("Environment closed")
        print("=" * 60)


# ---------------------------------------------------------------------------
# Signal handling + entrypoint helpers (reused verbatim by both scripts)
# ---------------------------------------------------------------------------

def setup_signal_handlers(shutdown_event_ref):
    """
    Set up signal handlers to ensure proper exit on SIGTERM/SIGINT.

    Args:
        shutdown_event_ref: a mutable container (list with one element) so the
            handler can reach the asyncio.Event set by main().  Pass [None] and
            update index-0 after creating the event.
    """
    global _cleanup_done

    def signal_handler(signum, frame):
        global _cleanup_done
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\nReceived {sig_name} signal, exiting...")
        if not _cleanup_done:
            _cleanup_done = True
            ev = shutdown_event_ref[0]
            if ev is not None:
                ev.set()
        else:
            print("Force exiting...")
            sys.exit(1)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def run_simulation_main(runner_class, platform_label: str):
    """
    Standard entrypoint used by both platform scripts.

    Args:
        runner_class: the concrete subclass to instantiate
        platform_label: short label for argparse description, e.g. "Twitter"
    """
    import argparse

    # Shared event container so the signal handler can reach the asyncio event.
    _event_ref = [None]
    setup_signal_handlers(_event_ref)

    async def _main():
        global _shutdown_event
        parser = argparse.ArgumentParser(description=f'OASIS {platform_label} Simulation')
        parser.add_argument(
            '--config',
            type=str,
            required=True,
            help='Config file path (simulation_config.json)'
        )
        parser.add_argument(
            '--max-rounds',
            type=int,
            default=None,
            help='Maximum simulation rounds (optional, to truncate excessively long simulations)'
        )
        parser.add_argument(
            '--no-wait',
            action='store_true',
            default=False,
            help='Shut down environment immediately after simulation, do not enter command-waiting mode'
        )

        args = parser.parse_args()

        _shutdown_event = asyncio.Event()
        _event_ref[0] = _shutdown_event

        if not os.path.exists(args.config):
            print(f"Error: config file does not exist: {args.config}")
            sys.exit(1)

        simulation_dir = os.path.dirname(args.config) or "."
        setup_oasis_logging(os.path.join(simulation_dir, "log"))

        runner = runner_class(
            config_path=args.config,
            wait_for_commands=not args.no_wait
        )
        await runner.run(max_rounds=args.max_rounds)

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nProgram interrupted")
    except SystemExit:
        pass
    finally:
        print("Simulation process exited")
