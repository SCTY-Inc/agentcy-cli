"""
OASIS Simulation Runner
Runs simulations in the background and records each Agent's actions, with real-time status monitoring
"""

import os
import sys
import json
import time
import threading
import subprocess
import signal
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue

from ..utils.logger import get_logger
from .graph_memory_updater import GraphMemoryManager
from .simulation_ipc import SimulationIPCClient
from .simulation_platforms import normalize_content_platform, normalize_run_platform

logger = get_logger('mirofish.simulation_runner')


def _now_iso() -> str:
    return datetime.now().isoformat()


def _load_json_file(path: str) -> Any:
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def _write_json_file(path: str, payload: Any) -> None:
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _safe_close(handle: Any) -> None:
    if not handle:
        return
    try:
        handle.close()
    except (AttributeError, OSError):
        return


def _json_object_or_none(line: str) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


# Platform detection
IS_WINDOWS = sys.platform == 'win32'


class RunnerStatus(str, Enum):
    """Runner status"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentAction:
    """Agent action record"""
    round_num: int
    timestamp: str
    platform: str  # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str  # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class RoundSummary:
    """Round summary"""
    round_num: int
    start_time: str
    end_time: Optional[str] = None
    simulated_hour: int = 0
    twitter_actions: int = 0
    reddit_actions: int = 0
    active_agents: List[int] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "simulated_hour": self.simulated_hour,
            "twitter_actions": self.twitter_actions,
            "reddit_actions": self.reddit_actions,
            "active_agents": self.active_agents,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class SimulationRunState:
    """Simulation run status (real-time)"""
    simulation_id: str
    runner_status: RunnerStatus = RunnerStatus.IDLE
    
    # Progress information
    current_round: int = 0
    total_rounds: int = 0
    simulated_hours: int = 0
    total_simulation_hours: int = 0
    
    # Per-platform independent round and simulation time (for dual-platform parallel display)
    twitter_current_round: int = 0
    reddit_current_round: int = 0
    twitter_simulated_hours: int = 0
    reddit_simulated_hours: int = 0
    
    # Platform status
    twitter_running: bool = False
    reddit_running: bool = False
    twitter_actions_count: int = 0
    reddit_actions_count: int = 0
    
    # Platform completion status (detected via simulation_end events in actions.jsonl)
    twitter_completed: bool = False
    reddit_completed: bool = False
    
    # Round summaries
    rounds: List[RoundSummary] = field(default_factory=list)
    
    # Recent actions (for real-time frontend display)
    recent_actions: List[AgentAction] = field(default_factory=list)
    max_recent_actions: int = 50
    
    # Timestamps
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=_now_iso)
    completed_at: Optional[str] = None
    
    # Error information
    error: Optional[str] = None

    # Process ID (used for stopping)
    process_pid: Optional[int] = None
    
    def add_action(self, action: AgentAction):
        """Add action to the recent actions list"""
        self.recent_actions.insert(0, action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[:self.max_recent_actions]
        
        if action.platform == "twitter":
            self.twitter_actions_count += 1
        else:
            self.reddit_actions_count += 1
        
        self.updated_at = _now_iso()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "runner_status": self.runner_status.value,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "simulated_hours": self.simulated_hours,
            "total_simulation_hours": self.total_simulation_hours,
            "progress_percent": round(self.current_round / max(self.total_rounds, 1) * 100, 1),
            # Per-platform independent rounds and time
            "twitter_current_round": self.twitter_current_round,
            "reddit_current_round": self.reddit_current_round,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "twitter_running": self.twitter_running,
            "reddit_running": self.reddit_running,
            "twitter_completed": self.twitter_completed,
            "reddit_completed": self.reddit_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "reddit_actions_count": self.reddit_actions_count,
            "total_actions_count": self.twitter_actions_count + self.reddit_actions_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "process_pid": self.process_pid,
        }
    
    def to_detail_dict(self) -> Dict[str, Any]:
        """Detailed information including recent actions"""
        result = self.to_dict()
        result["recent_actions"] = [a.to_dict() for a in self.recent_actions]
        result["rounds_count"] = len(self.rounds)
        return result


class SimulationRunner:
    """
    Simulation Runner

    Responsibilities:
    1. Run OASIS simulations in background processes
    2. Parse run logs and record each Agent's actions
    3. Provide real-time status query interface
    4. Support pause/stop/resume operations
    """
    
    # Run state storage directory
    RUN_STATE_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../uploads/simulations'
    )
    
    # Scripts directory
    SCRIPTS_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../scripts'
    )
    
    # In-memory run states
    _run_states: Dict[str, SimulationRunState] = {}
    _processes: Dict[str, subprocess.Popen] = {}
    _action_queues: Dict[str, Queue] = {}
    _monitor_threads: Dict[str, threading.Thread] = {}
    _stdout_files: Dict[str, Any] = {}  # Store stdout file handles
    _stderr_files: Dict[str, Any] = {}  # Store stderr file handles
    
    # Graph memory update configuration
    _graph_memory_enabled: Dict[str, bool] = {}  # simulation_id -> enabled
    
    @classmethod
    def get_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """Get run status"""
        if simulation_id in cls._run_states:
            return cls._run_states[simulation_id]
        
        # Try to load from file
        state = cls._load_run_state(simulation_id)
        if state:
            cls._run_states[simulation_id] = state
        return state
    
    @classmethod
    def _load_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """Load run status from file"""
        state_file = os.path.join(cls.RUN_STATE_DIR, simulation_id, "run_state.json")
        if not os.path.exists(state_file):
            return None
        
        try:
            data = _load_json_file(state_file)
            if not isinstance(data, dict):
                raise ValueError("run_state.json must contain an object")

            state = SimulationRunState(
                simulation_id=simulation_id,
                runner_status=RunnerStatus(data.get("runner_status", "idle")),
                current_round=data.get("current_round", 0),
                total_rounds=data.get("total_rounds", 0),
                simulated_hours=data.get("simulated_hours", 0),
                total_simulation_hours=data.get("total_simulation_hours", 0),
                # Per-platform independent rounds and time
                twitter_current_round=data.get("twitter_current_round", 0),
                reddit_current_round=data.get("reddit_current_round", 0),
                twitter_simulated_hours=data.get("twitter_simulated_hours", 0),
                reddit_simulated_hours=data.get("reddit_simulated_hours", 0),
                twitter_running=data.get("twitter_running", False),
                reddit_running=data.get("reddit_running", False),
                twitter_completed=data.get("twitter_completed", False),
                reddit_completed=data.get("reddit_completed", False),
                twitter_actions_count=data.get("twitter_actions_count", 0),
                reddit_actions_count=data.get("reddit_actions_count", 0),
                started_at=data.get("started_at"),
                updated_at=data.get("updated_at", _now_iso()),
                completed_at=data.get("completed_at"),
                error=data.get("error"),
                process_pid=data.get("process_pid"),
            )
            
            # Load recent actions
            actions_data = data.get("recent_actions", [])
            if not isinstance(actions_data, list):
                raise ValueError("run_state.json recent_actions must be a list")
            for action_data in actions_data:
                if not isinstance(action_data, dict):
                    continue
                state.recent_actions.append(AgentAction(
                    round_num=action_data.get("round_num", 0),
                    timestamp=action_data.get("timestamp", ""),
                    platform=action_data.get("platform", ""),
                    agent_id=action_data.get("agent_id", 0),
                    agent_name=action_data.get("agent_name", ""),
                    action_type=action_data.get("action_type", ""),
                    action_args=action_data.get("action_args", {}),
                    result=action_data.get("result"),
                    success=action_data.get("success", True),
                ))

            return state
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.error(f"Failed to load run status: {str(exc)}")
            return None
    
    @classmethod
    def _save_run_state(cls, state: SimulationRunState):
        """Save run status to file"""
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        state_file = os.path.join(sim_dir, "run_state.json")
        
        data = state.to_detail_dict()
        
        _write_json_file(state_file, data)
        
        cls._run_states[state.simulation_id] = state
    
    @classmethod
    def _stop_graph_updater(cls, simulation_id: str) -> None:
        if not cls._graph_memory_enabled.get(simulation_id, False):
            return
        try:
            GraphMemoryManager.stop_updater(simulation_id)
            logger.info(f"Graph memory update stopped: simulation_id={simulation_id}")
        except (OSError, RuntimeError, ValueError) as exc:
            logger.error(f"Failed to stop graph memory updater: {exc}")
        finally:
            cls._graph_memory_enabled.pop(simulation_id, None)

    @staticmethod
    def _terminate_process_fallback(process: subprocess.Popen, timeout: int = 5) -> None:
        try:
            process.terminate()
            process.wait(timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            process.kill()

    @classmethod
    def start_simulation(
        cls,
        simulation_id: str,
        platform: str = "parallel",  # twitter / reddit / parallel
        max_rounds: int = None,  # Max simulation rounds (optional, to truncate overly long simulations)
        enable_graph_memory_update: bool = False,  # Whether to update activities to the graph
        graph_id: str = None,  # Graph ID (required when graph update is enabled)
        wait_for_commands: bool = True,
    ) -> SimulationRunState:
        """
        Start a simulation

        Args:
            simulation_id: Simulation ID
            platform: Running platform (twitter/reddit/parallel)
            max_rounds: Max simulation rounds (optional, to truncate overly long simulations)
            enable_graph_memory_update: Whether to dynamically update Agent activities to the graph
            graph_id: Graph ID (required when graph update is enabled)
            wait_for_commands: Whether the subprocess should stay alive for IPC interviews after completion

        Returns:
            SimulationRunState
        """
        platform = normalize_run_platform(platform, default="parallel")

        existing = cls.get_run_state(simulation_id)
        if existing and existing.runner_status in [RunnerStatus.RUNNING, RunnerStatus.STARTING]:
            raise ValueError(f"Simulation is already running: {simulation_id}")
        
        # Load simulation configuration
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            raise ValueError(f"Simulation configuration does not exist, please call /prepare first")
        
        config = _load_json_file(config_path)
        if not isinstance(config, dict):
            raise ValueError("simulation_config.json must contain an object")
        
        time_config = config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = int(total_hours * 60 / minutes_per_round)
        
        # If max rounds specified, truncate
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                logger.info(f"Rounds truncated: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")
        
        state = SimulationRunState(
            simulation_id=simulation_id,
            runner_status=RunnerStatus.STARTING,
            total_rounds=total_rounds,
            total_simulation_hours=total_hours,
            started_at=_now_iso(),
        )
        
        cls._save_run_state(state)
        
        # If graph memory update is enabled, create the updater
        if enable_graph_memory_update:
            if not graph_id:
                raise ValueError("graph_id is required when graph memory update is enabled")
            
            try:
                GraphMemoryManager.create_updater(simulation_id, graph_id)
                cls._graph_memory_enabled[simulation_id] = True
                logger.info(f"Graph memory update enabled: simulation_id={simulation_id}, graph_id={graph_id}")
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                logger.error(f"Failed to create graph memory updater: {exc}")
                cls._graph_memory_enabled[simulation_id] = False
        else:
            cls._graph_memory_enabled[simulation_id] = False
        
        # Determine which script to run (scripts are in scripts/ directory)
        if platform == "twitter":
            script_name = "run_twitter_simulation.py"
            state.twitter_running = True
        elif platform == "reddit":
            script_name = "run_reddit_simulation.py"
            state.reddit_running = True
        else:
            script_name = "run_parallel_simulation.py"
            state.twitter_running = True
            state.reddit_running = True
        
        script_path = os.path.join(cls.SCRIPTS_DIR, script_name)
        
        if not os.path.exists(script_path):
            raise ValueError(f"Script does not exist: {script_path}")
        
        # Create action queue
        action_queue = Queue()
        cls._action_queues[simulation_id] = action_queue
        
        # Start simulation process
        try:
            # Build run command using full paths
            # New log structure:
            #   twitter/actions.jsonl - Twitter action log
            #   reddit/actions.jsonl  - Reddit action log
            #   simulation.log        - Main process log
            
            cmd = [
                sys.executable,  # Python interpreter
                script_path,
                "--config", config_path,  # Use full configuration file path
            ]
            
            # If max rounds specified, add to command line arguments
            if max_rounds is not None and max_rounds > 0:
                cmd.extend(["--max-rounds", str(max_rounds)])
            if not wait_for_commands:
                cmd.append("--no-wait")
            
            # Create main log file to avoid process blocking due to stdout/stderr pipe buffer full
            main_log_path = os.path.join(sim_dir, "simulation.log")
            main_log_file = open(main_log_path, 'w', encoding='utf-8')
            
            # Set subprocess environment variables to ensure UTF-8 encoding on Windows
            # This fixes issues where third-party libraries (e.g. OASIS) read files without specifying encoding
            env = os.environ.copy()
            env['PYTHONUTF8'] = '1'  # Python 3.7+ support, makes all open() default to UTF-8
            env['PYTHONIOENCODING'] = 'utf-8'  # Ensure stdout/stderr use UTF-8
            
            # Set working directory to simulation directory (databases and other files are generated here)
            # Use start_new_session=True to create a new process group, ensuring all child processes can be terminated via os.killpg
            process = subprocess.Popen(
                cmd,
                cwd=sim_dir,
                stdout=main_log_file,
                stderr=subprocess.STDOUT,  # stderr also writes to the same file
                text=True,
                encoding='utf-8',  # Explicitly specify encoding
                bufsize=1,
                env=env,  # Pass environment variables with UTF-8 settings
                start_new_session=True,  # Create new process group to ensure all related processes can be terminated on server shutdown
            )
            
            # Save file handles for later cleanup
            cls._stdout_files[simulation_id] = main_log_file
            cls._stderr_files[simulation_id] = None  # Separate stderr no longer needed
            
            state.process_pid = process.pid
            state.runner_status = RunnerStatus.RUNNING
            cls._processes[simulation_id] = process
            cls._save_run_state(state)
            
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=cls._monitor_simulation,
                args=(simulation_id,),
                daemon=True
            )
            monitor_thread.start()
            cls._monitor_threads[simulation_id] = monitor_thread
            
            logger.info(f"Simulation started successfully: {simulation_id}, pid={process.pid}, platform={platform}")
            
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError) as exc:
            _safe_close(locals().get('main_log_file'))
            state.runner_status = RunnerStatus.FAILED
            state.error = str(exc)
            cls._save_run_state(state)
            raise
        
        return state
    
    @classmethod
    def _monitor_simulation(cls, simulation_id: str):
        """Monitor simulation process, parse action logs"""
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        # New log structure: per-platform action logs
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        process = cls._processes.get(simulation_id)
        state = cls.get_run_state(simulation_id)
        
        if not process or not state:
            return
        
        twitter_position = 0
        reddit_position = 0
        
        try:
            while process.poll() is None:  # Process is still running
                # Read Twitter action log
                if os.path.exists(twitter_actions_log):
                    twitter_position = cls._read_action_log(
                        twitter_actions_log, twitter_position, state, "twitter"
                    )
                
                # Read Reddit action log
                if os.path.exists(reddit_actions_log):
                    reddit_position = cls._read_action_log(
                        reddit_actions_log, reddit_position, state, "reddit"
                    )
                
                # Update state
                cls._save_run_state(state)
                time.sleep(2)
            
            # After process ends, read logs one final time
            if os.path.exists(twitter_actions_log):
                cls._read_action_log(twitter_actions_log, twitter_position, state, "twitter")
            if os.path.exists(reddit_actions_log):
                cls._read_action_log(reddit_actions_log, reddit_position, state, "reddit")
            
            # Process ended
            exit_code = process.returncode
            
            if exit_code == 0:
                state.runner_status = RunnerStatus.COMPLETED
                state.completed_at = _now_iso()
                logger.info(f"Simulation completed: {simulation_id}")
            else:
                state.runner_status = RunnerStatus.FAILED
                # Read error information from main log file
                main_log_path = os.path.join(sim_dir, "simulation.log")
                error_info = ""
                try:
                    if os.path.exists(main_log_path):
                        with open(main_log_path, 'r', encoding='utf-8') as f:
                            error_info = f.read()[-2000:]  # Get last 2000 characters
                except OSError:
                    pass
                state.error = f"Process exit code: {exit_code}, error: {error_info}"
                logger.error(f"Simulation failed: {simulation_id}, error={state.error}")
            
            state.twitter_running = False
            state.reddit_running = False
            cls._save_run_state(state)
            
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError) as exc:
            logger.error(f"Monitor thread exception: {simulation_id}, error={str(exc)}")
            state.runner_status = RunnerStatus.FAILED
            state.error = str(exc)
            cls._save_run_state(state)
        
        finally:
            cls._stop_graph_updater(simulation_id)

            # Clean up process resources
            cls._processes.pop(simulation_id, None)
            cls._action_queues.pop(simulation_id, None)
            
            # Close log file handles
            if simulation_id in cls._stdout_files:
                _safe_close(cls._stdout_files[simulation_id])
                cls._stdout_files.pop(simulation_id, None)
            if simulation_id in cls._stderr_files and cls._stderr_files[simulation_id]:
                _safe_close(cls._stderr_files[simulation_id])
                cls._stderr_files.pop(simulation_id, None)
    
    @classmethod
    def _read_action_log(
        cls, 
        log_path: str, 
        position: int, 
        state: SimulationRunState,
        platform: str
    ) -> int:
        """
        Read action log file

        Args:
            log_path: Log file path
            position: Last read position
            state: Run state object
            platform: Platform name (twitter/reddit)

        Returns:
            New read position
        """
        graph_memory_enabled = cls._graph_memory_enabled.get(state.simulation_id, False)
        graph_updater = None
        if graph_memory_enabled:
            graph_updater = GraphMemoryManager.get_updater(state.simulation_id)
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                f.seek(position)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    action_data = _json_object_or_none(line)
                    if action_data is None:
                        continue

                    if "event_type" in action_data:
                        event_type = action_data.get("event_type")

                        if event_type == "simulation_end":
                            if platform == "twitter":
                                state.twitter_completed = True
                                state.twitter_running = False
                                logger.info(f"Twitter simulation completed: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                            elif platform == "reddit":
                                state.reddit_completed = True
                                state.reddit_running = False
                                logger.info(f"Reddit simulation completed: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")

                            all_completed = cls._check_all_platforms_completed(state)
                            if all_completed:
                                state.runner_status = RunnerStatus.COMPLETED
                                state.completed_at = _now_iso()
                                logger.info(f"All platform simulations completed: {state.simulation_id}")

                        elif event_type == "round_end":
                            round_num = action_data.get("round", 0)
                            simulated_hours = action_data.get("simulated_hours", 0)

                            if platform == "twitter":
                                if round_num > state.twitter_current_round:
                                    state.twitter_current_round = round_num
                                state.twitter_simulated_hours = simulated_hours
                            elif platform == "reddit":
                                if round_num > state.reddit_current_round:
                                    state.reddit_current_round = round_num
                                state.reddit_simulated_hours = simulated_hours

                            if round_num > state.current_round:
                                state.current_round = round_num
                            state.simulated_hours = max(state.twitter_simulated_hours, state.reddit_simulated_hours)

                        continue

                    action = AgentAction(
                        round_num=action_data.get("round", 0),
                        timestamp=action_data.get("timestamp", _now_iso()),
                        platform=platform,
                        agent_id=action_data.get("agent_id", 0),
                        agent_name=action_data.get("agent_name", ""),
                        action_type=action_data.get("action_type", ""),
                        action_args=action_data.get("action_args", {}),
                        result=action_data.get("result"),
                        success=action_data.get("success", True),
                    )
                    state.add_action(action)

                    if action.round_num and action.round_num > state.current_round:
                        state.current_round = action.round_num

                    if graph_updater:
                        graph_updater.add_activity_from_dict(action_data, platform)
                return f.tell()
        except OSError as exc:
            logger.warning(f"Failed to read action log: {log_path}, error={exc}")
            return position
    
    @classmethod
    def _check_all_platforms_completed(cls, state: SimulationRunState) -> bool:
        """
        Check if all enabled platforms have completed the simulation

        Determines if a platform is enabled by checking whether the corresponding actions.jsonl file exists

        Returns:
            True if all enabled platforms have completed
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        twitter_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        # Check which platforms are enabled (determined by file existence)
        twitter_enabled = os.path.exists(twitter_log)
        reddit_enabled = os.path.exists(reddit_log)
        
        # If a platform is enabled but not completed, return False
        if twitter_enabled and not state.twitter_completed:
            return False
        if reddit_enabled and not state.reddit_completed:
            return False
        
        # At least one platform is enabled and completed
        return twitter_enabled or reddit_enabled
    
    @classmethod
    def _terminate_process(cls, process: subprocess.Popen, simulation_id: str, timeout: int = 10):
        """
        Cross-platform terminate process and its child processes

        Args:
            process: Process to terminate
            simulation_id: Simulation ID (for logging)
            timeout: Timeout in seconds to wait for process to exit
        """
        if IS_WINDOWS:
            # Windows: Use taskkill command to terminate process tree
            # /F = force terminate, /T = terminate process tree (including child processes)
            logger.info(f"Terminating process tree (Windows): simulation={simulation_id}, pid={process.pid}")
            try:
                # First try graceful termination
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T'],
                    capture_output=True,
                    timeout=5
                )
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Force terminate
                    logger.warning(f"Process not responding, force terminating: {simulation_id}")
                    subprocess.run(
                        ['taskkill', '/F', '/PID', str(process.pid), '/T'],
                        capture_output=True,
                        timeout=5
                    )
                    process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError) as exc:
                logger.warning(f"taskkill failed, trying terminate: {exc}")
                cls._terminate_process_fallback(process)
        else:
            # Unix: Use process group termination
            # Since start_new_session=True was used, process group ID equals main process PID
            pgid = os.getpgid(process.pid)
            logger.info(f"Terminating process group (Unix): simulation={simulation_id}, pgid={pgid}")
            
            # First send SIGTERM to the entire process group
            os.killpg(pgid, signal.SIGTERM)
            
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # If still running after timeout, force send SIGKILL
                logger.warning(f"Process group did not respond to SIGTERM, force terminating: {simulation_id}")
                os.killpg(pgid, signal.SIGKILL)
                process.wait(timeout=5)
    
    @classmethod
    def stop_simulation(cls, simulation_id: str) -> SimulationRunState:
        """Stop simulation"""
        state = cls.get_run_state(simulation_id)
        if not state:
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        if state.runner_status not in [RunnerStatus.RUNNING, RunnerStatus.PAUSED]:
            raise ValueError(f"Simulation is not running: {simulation_id}, status={state.runner_status}")
        
        state.runner_status = RunnerStatus.STOPPING
        cls._save_run_state(state)
        
        # Terminate process
        process = cls._processes.get(simulation_id)
        if process and process.poll() is None:
            try:
                cls._terminate_process(process, simulation_id)
            except ProcessLookupError:
                # Process no longer exists
                pass
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
                logger.error(f"Failed to terminate process group: {simulation_id}, error={exc}")
                cls._terminate_process_fallback(process)
        
        state.runner_status = RunnerStatus.STOPPED
        state.twitter_running = False
        state.reddit_running = False
        state.completed_at = _now_iso()
        cls._save_run_state(state)

        cls._stop_graph_updater(simulation_id)

        logger.info(f"Simulation stopped: {simulation_id}")
        return state
    
    @classmethod
    def _read_actions_from_file(
        cls,
        file_path: str,
        default_platform: Optional[str] = None,
        platform_filter: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        Read actions from a single action file

        Args:
            file_path: Action log file path
            default_platform: Default platform (used when action record has no platform field)
            platform_filter: Filter by platform
            agent_id: Filter by Agent ID
            round_num: Filter by round
        """
        if not os.path.exists(file_path):
            return []
        
        actions = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Skip non-action records (e.g. simulation_start, round_start, round_end events)
                    if "event_type" in data:
                        continue
                    
                    # Skip records without agent_id (non-Agent actions)
                    if "agent_id" not in data:
                        continue
                    
                    # Get platform: prefer platform from record, otherwise use default
                    record_platform = data.get("platform") or default_platform or ""
                    
                    # Filter
                    if platform_filter and record_platform != platform_filter:
                        continue
                    if agent_id is not None and data.get("agent_id") != agent_id:
                        continue
                    if round_num is not None and data.get("round") != round_num:
                        continue
                    
                    actions.append(AgentAction(
                        round_num=data.get("round", 0),
                        timestamp=data.get("timestamp", ""),
                        platform=record_platform,
                        agent_id=data.get("agent_id", 0),
                        agent_name=data.get("agent_name", ""),
                        action_type=data.get("action_type", ""),
                        action_args=data.get("action_args", {}),
                        result=data.get("result"),
                        success=data.get("success", True),
                    ))
                    
                except json.JSONDecodeError:
                    continue
        
        return actions
    
    @classmethod
    def get_all_actions(
        cls,
        simulation_id: str,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        Get complete action history for all platforms (no pagination limit)

        Args:
            simulation_id: Simulation ID
            platform: Filter by platform (twitter/reddit)
            agent_id: Filter by Agent
            round_num: Filter by round

        Returns:
            Complete action list (sorted by timestamp, newest first)
        """
        platform = normalize_content_platform(platform, allow_none=True)
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        actions = []
        
        # Read Twitter action file (automatically set platform to twitter based on file path)
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        if not platform or platform == "twitter":
            actions.extend(cls._read_actions_from_file(
                twitter_actions_log,
                default_platform="twitter",  # Auto-fill platform field
                platform_filter=platform,
                agent_id=agent_id, 
                round_num=round_num
            ))
        
        # Read Reddit action file (automatically set platform to reddit based on file path)
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        if not platform or platform == "reddit":
            actions.extend(cls._read_actions_from_file(
                reddit_actions_log,
                default_platform="reddit",  # Auto-fill platform field
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            ))
        
        # If per-platform files don't exist, try reading old single-file format
        if not actions:
            actions_log = os.path.join(sim_dir, "actions.jsonl")
            actions = cls._read_actions_from_file(
                actions_log,
                default_platform=None,  # Old format files should have a platform field
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            )
        
        # Sort by timestamp (newest first)
        actions.sort(key=lambda x: x.timestamp, reverse=True)
        
        return actions
    
    @classmethod
    def get_actions(
        cls,
        simulation_id: str,
        limit: int = 100,
        offset: int = 0,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        Get action history (with pagination)

        Args:
            simulation_id: Simulation ID
            limit: Return count limit
            offset: Offset
            platform: Filter by platform
            agent_id: Filter by Agent
            round_num: Filter by round

        Returns:
            Action list
        """
        actions = cls.get_all_actions(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        # Paginate
        return actions[offset:offset + limit]
    
    @classmethod
    def get_timeline(
        cls,
        simulation_id: str,
        start_round: int = 0,
        end_round: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get simulation timeline (summarized by round)

        Args:
            simulation_id: Simulation ID
            start_round: Start round
            end_round: End round

        Returns:
            Summary information for each round
        """
        actions = cls.get_all_actions(simulation_id)
        actions.sort(key=lambda x: x.timestamp)

        # Group by round
        rounds: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            round_num = action.round_num
            
            if round_num < start_round:
                continue
            if end_round is not None and round_num > end_round:
                continue
            
            if round_num not in rounds:
                rounds[round_num] = {
                    "round_num": round_num,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "active_agents": set(),
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            r = rounds[round_num]
            
            if action.platform == "twitter":
                r["twitter_actions"] += 1
            else:
                r["reddit_actions"] += 1
            
            r["active_agents"].add(action.agent_id)
            r["action_types"][action.action_type] = r["action_types"].get(action.action_type, 0) + 1
            if action.timestamp < r["first_action_time"]:
                r["first_action_time"] = action.timestamp
            if action.timestamp > r["last_action_time"]:
                r["last_action_time"] = action.timestamp
        
        # Convert to list
        # Ensure all rounds appear in timeline (including empty ones)
        run_state = cls.get_run_state(simulation_id)
        total_rounds = run_state.total_rounds if run_state else 0
        max_round = max(max(rounds.keys(), default=-1) + 1, total_rounds)
        actual_end = end_round if end_round is not None else max_round

        result = []
        for round_num in range(start_round, actual_end):
            if round_num in rounds:
                r = rounds[round_num]
                result.append({
                    "round_num": round_num,
                    "twitter_actions": r["twitter_actions"],
                    "reddit_actions": r["reddit_actions"],
                    "total_actions": r["twitter_actions"] + r["reddit_actions"],
                    "active_agents_count": len(r["active_agents"]),
                    "active_agents": list(r["active_agents"]),
                    "action_types": r["action_types"],
                    "first_action_time": r["first_action_time"],
                    "last_action_time": r["last_action_time"],
                })
            else:
                result.append({
                    "round_num": round_num,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "total_actions": 0,
                    "active_agents_count": 0,
                    "active_agents": [],
                    "action_types": {},
                    "first_action_time": None,
                    "last_action_time": None,
                })

        return result
    
    @classmethod
    def get_agent_stats(cls, simulation_id: str) -> List[Dict[str, Any]]:
        """
        Get statistics for each Agent

        Returns:
            Agent statistics list
        """
        actions = cls.get_all_actions(simulation_id)
        actions.sort(key=lambda x: x.timestamp)

        agent_stats: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            agent_id = action.agent_id
            
            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": action.agent_name,
                    "total_actions": 0,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            stats = agent_stats[agent_id]
            stats["total_actions"] += 1
            
            if action.platform == "twitter":
                stats["twitter_actions"] += 1
            else:
                stats["reddit_actions"] += 1
            
            stats["action_types"][action.action_type] = stats["action_types"].get(action.action_type, 0) + 1
            if action.timestamp < stats["first_action_time"]:
                stats["first_action_time"] = action.timestamp
            if action.timestamp > stats["last_action_time"]:
                stats["last_action_time"] = action.timestamp
        
        # Sort by total action count
        result = sorted(agent_stats.values(), key=lambda x: x["total_actions"], reverse=True)
        
        return result
    
    @classmethod
    def cleanup_simulation_logs(cls, simulation_id: str) -> Dict[str, Any]:
        """
        Clean up simulation run logs (for forcing a fresh restart of simulation)

        Will delete the following files:
        - run_state.json
        - twitter/actions.jsonl
        - reddit/actions.jsonl
        - simulation.log
        - stdout.log / stderr.log
        - twitter_simulation.db (simulation database)
        - reddit_simulation.db (simulation database)
        - env_status.json (environment status)

        Note: Will not delete configuration files (simulation_config.json) and profile files

        Args:
            simulation_id: Simulation ID

        Returns:
            Cleanup result information
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return {"success": True, "message": "Simulation directory does not exist, no cleanup needed"}
        
        cleaned_files = []
        errors = []
        
        # List of files to delete (including database files)
        files_to_delete = [
            "run_state.json",
            "simulation.log",
            "stdout.log",
            "stderr.log",
            "twitter_simulation.db",  # Twitter platform database
            "reddit_simulation.db",   # Reddit platform database
            "env_status.json",        # Environment status file
        ]
        
        # List of directories to clean (containing action logs)
        dirs_to_clean = ["twitter", "reddit"]
        
        # Delete files
        for filename in files_to_delete:
            file_path = os.path.join(sim_dir, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned_files.append(filename)
                except OSError as exc:
                    errors.append(f"Failed to delete {filename}: {str(exc)}")
        
        # Clean up action logs in platform directories
        for dir_name in dirs_to_clean:
            dir_path = os.path.join(sim_dir, dir_name)
            if os.path.exists(dir_path):
                actions_file = os.path.join(dir_path, "actions.jsonl")
                if os.path.exists(actions_file):
                    try:
                        os.remove(actions_file)
                        cleaned_files.append(f"{dir_name}/actions.jsonl")
                    except OSError as exc:
                        errors.append(f"Failed to delete {dir_name}/actions.jsonl: {str(exc)}")
        
        # Clean up in-memory run state
        if simulation_id in cls._run_states:
            del cls._run_states[simulation_id]
        
        logger.info(f"Simulation log cleanup completed: {simulation_id}, deleted files: {cleaned_files}")
        
        return {
            "success": len(errors) == 0,
            "cleaned_files": cleaned_files,
            "errors": errors if errors else None
        }
    
    # Flag to prevent duplicate cleanup
    _cleanup_done = False
    
    @classmethod
    def cleanup_all_simulations(cls):
        """
        Clean up all running simulation processes

        Called on server shutdown to ensure all child processes are terminated
        """
        # Prevent duplicate cleanup
        if cls._cleanup_done:
            return
        cls._cleanup_done = True
        
        has_processes = bool(cls._processes)
        has_updaters = bool(cls._graph_memory_enabled)
        
        if not has_processes and not has_updaters:
            return  # Nothing to clean up, return silently
        
        logger.info("Cleaning up all simulation processes...")
        
        # First stop all graph memory updaters (stop_all prints logs internally)
        try:
            GraphMemoryManager.stop_all()
        except RuntimeError as exc:
            logger.error(f"Failed to stop graph memory updaters: {exc}")
        cls._graph_memory_enabled.clear()

        # Copy dict to avoid modification during iteration
        processes = list(cls._processes.items())
        
        for simulation_id, process in processes:
            try:
                if process.poll() is None:  # Process is still running
                    logger.info(f"Terminating simulation process: {simulation_id}, pid={process.pid}")
                    
                    try:
                        # Use cross-platform process termination method
                        cls._terminate_process(process, simulation_id, timeout=5)
                    except (ProcessLookupError, OSError):
                        # Process may no longer exist, try direct termination
                        try:
                            process.terminate()
                            process.wait(timeout=3)
                        except (OSError, subprocess.SubprocessError):
                            process.kill()
                    
                    # Update run_state.json
                    state = cls.get_run_state(simulation_id)
                    if state:
                        state.runner_status = RunnerStatus.STOPPED
                        state.twitter_running = False
                        state.reddit_running = False
                        state.completed_at = _now_iso()
                        state.error = "Server shutdown, simulation was terminated"
                        cls._save_run_state(state)
                    
                    # Also update state.json, set status to stopped
                    try:
                        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
                        state_file = os.path.join(sim_dir, "state.json")
                        logger.info(f"Attempting to update state.json: {state_file}")
                        if os.path.exists(state_file):
                            state_data = _load_json_file(state_file)
                            if not isinstance(state_data, dict):
                                raise ValueError("state.json must contain an object")
                            state_data['status'] = 'stopped'
                            state_data['updated_at'] = _now_iso()
                            _write_json_file(state_file, state_data)
                            logger.info(f"Updated state.json status to stopped: {simulation_id}")
                        else:
                            logger.warning(f"state.json does not exist: {state_file}")
                    except (OSError, ValueError, TypeError, json.JSONDecodeError) as state_err:
                        logger.warning(f"Failed to update state.json: {simulation_id}, error={state_err}")

            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
                logger.error(f"Failed to clean up process: {simulation_id}, error={exc}")
        
        # Clean up file handles
        for _simulation_id, file_handle in list(cls._stdout_files.items()):
            _safe_close(file_handle)
        cls._stdout_files.clear()

        for _simulation_id, file_handle in list(cls._stderr_files.items()):
            _safe_close(file_handle)
        cls._stderr_files.clear()
        
        # Clean up in-memory state
        cls._processes.clear()
        cls._action_queues.clear()
        
        logger.info("Simulation process cleanup completed")
    
    # ============== Interview Features ==============

    @classmethod
    def check_env_alive(cls, simulation_id: str) -> bool:
        """
        Check if simulation environment is alive (can receive Interview commands)

        Args:
            simulation_id: Simulation ID

        Returns:
            True if environment is alive, False if environment is closed
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return False

        ipc_client = SimulationIPCClient(sim_dir)
        return ipc_client.check_env_alive()

    @classmethod
    def interview_agents_batch(
        cls,
        simulation_id: str,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        Batch interview multiple Agents

        Args:
            simulation_id: Simulation ID
            interviews: Interview list, each element contains {"agent_id": int, "prompt": str, "platform": str (optional)}
            platform: Default platform (optional, overridden by each interview item's platform)
                - "twitter": Default to interview on Twitter platform only
                - "reddit": Default to interview on Reddit platform only
                - None: In dual-platform simulation, interview each Agent on both platforms
            timeout: Timeout in seconds

        Returns:
            Batch interview result dict

        Raises:
            ValueError: Simulation does not exist or environment is not running
            TimeoutError: Timed out waiting for response
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"Simulation environment is not running or has been closed, cannot perform Interview: {simulation_id}")

        logger.info(f"Sending batch Interview command: simulation_id={simulation_id}, count={len(interviews)}, platform={platform}")

        response = ipc_client.send_batch_interview(
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "interviews_count": len(interviews),
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "interviews_count": len(interviews),
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    
    @classmethod
    def _get_interview_history_from_db(
        cls,
        db_path: str,
        platform_name: str,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get Interview history from a single database"""
        import sqlite3
        
        if not os.path.exists(db_path):
            return []
        
        results = []
        
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                if agent_id is not None:
                    cursor.execute("""
                        SELECT user_id, info, created_at
                        FROM trace
                        WHERE action = 'interview' AND user_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (agent_id, limit))
                else:
                    cursor.execute("""
                        SELECT user_id, info, created_at
                        FROM trace
                        WHERE action = 'interview'
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))

                for user_id, info_json, created_at in cursor.fetchall():
                    try:
                        info = json.loads(info_json) if info_json else {}
                    except json.JSONDecodeError:
                        info = {"raw": info_json}

                    results.append({
                        "agent_id": user_id,
                        "response": info.get("response", info),
                        "prompt": info.get("prompt", ""),
                        "timestamp": created_at,
                        "platform": platform_name
                    })

        except (OSError, sqlite3.Error) as exc:
            logger.error(f"Failed to read Interview history ({platform_name}): {exc}")
        
        return results

    @classmethod
    def get_interview_history(
        cls,
        simulation_id: str,
        platform: str = None,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get Interview history (read from database)

        Args:
            simulation_id: Simulation ID
            platform: Platform type (reddit/twitter/None)
                - "reddit": Only get Reddit platform history
                - "twitter": Only get Twitter platform history
                - None: Get history from both platforms
            agent_id: Specify Agent ID (optional, only get this Agent's history)
            limit: Return count limit per platform

        Returns:
            Interview history record list
        """
        platform = normalize_content_platform(platform, allow_none=True)
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        results = []
        
        # Determine which platforms to query
        if platform in ("reddit", "twitter"):
            platforms = [platform]
        else:
            # When platform is not specified, query both platforms
            platforms = ["twitter", "reddit"]
        
        for p in platforms:
            db_path = os.path.join(sim_dir, f"{p}_simulation.db")
            platform_results = cls._get_interview_history_from_db(
                db_path=db_path,
                platform_name=p,
                agent_id=agent_id,
                limit=limit
            )
            results.extend(platform_results)
        
        # Sort by time descending
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # If multiple platforms were queried, limit total count
        if len(platforms) > 1 and len(results) > limit:
            results = results[:limit]
        
        return results
