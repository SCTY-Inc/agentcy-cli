"""Minimal run-first CLI for MiroFish."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from typing import Any, Dict, Iterable, List, Optional

import logging

from .brief_v1 import ImportedBrief, import_brief_v1
from .cli_display import PipelineDisplay
from .forecast_v1 import build_completed_forecast_v1
from .config import Config
from .core.task_manager import TaskManager, TaskStatus
from .core.workbench_session import WorkbenchSession
from .resources.reports import ReportStore
from .run_artifacts import RunStore
from .run_eval import build_completed_run_eval
from .services.graph_builder import GraphBuilderService
from .smoke_mode import build_smoke_outputs
from .utils.oasis_llm import get_simulation_runtime_preflight, require_simulation_runtime
from .services.graph_db import GraphDatabase
from .services.simulation_manager import SimulationManager
from .services.simulation_runner import RunnerStatus, SimulationRunner
from .visual_snapshots import generate_visual_snapshots

DEFAULT_PROJECT_NAME = "MiroFish Run"
DEFAULT_PARALLEL_PROFILE_COUNT = 5


def _stderr(message: str) -> None:
    print(message, file=sys.stderr)


def _emit(payload: Any, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            print(f"{key}: {value}")
    else:
        print(payload)
    return 0


class LocalFileInput:
    """Minimal file wrapper compatible with ProjectManager.save_file_to_project."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.filename = os.path.basename(self.path)

    def save(self, destination: str) -> None:
        shutil.copy2(self.path, destination)


def _require_existing_files(paths: Iterable[str]) -> List[str]:
    resolved = [os.path.abspath(path) for path in paths]
    missing = [path for path in resolved if not os.path.exists(path)]
    if missing:
        raise FileNotFoundError(f"Missing input files: {', '.join(missing)}")
    return resolved


def _default_project_name(source_files: List[str]) -> str:
    if not source_files:
        return DEFAULT_PROJECT_NAME
    stem = os.path.splitext(os.path.basename(source_files[0]))[0].strip()
    if not stem:
        return DEFAULT_PROJECT_NAME
    if len(source_files) == 1:
        return stem
    return f"{stem} +{len(source_files) - 1}"


def _resolve_run_inputs(args: argparse.Namespace) -> tuple[List[str], str, ImportedBrief | None]:
    source_files = _require_existing_files(args.files)
    imported_brief = import_brief_v1(args.brief) if getattr(args, "brief", None) else None
    requirement = imported_brief.requirement if imported_brief else args.requirement
    if not requirement:
        raise ValueError("--requirement is required unless --brief is supplied")
    return source_files, requirement, imported_brief


def _wait_for_task(
    task_id: str,
    poll_interval: float = 1.0,
    on_update=None,
):
    manager = TaskManager()
    last_snapshot = None
    while True:
        task = manager.get_task(task_id)
        if task is None:
            raise RuntimeError(f"Task not found: {task_id}")
        snapshot = (task.status.value, task.progress, task.message, task.error)
        if snapshot != last_snapshot and on_update is not None:
            on_update(task)
            last_snapshot = snapshot
        if task.status == TaskStatus.COMPLETED:
            return task
        if task.status == TaskStatus.FAILED:
            raise RuntimeError(task.error or task.message or f"Task failed: {task_id}")
        time.sleep(poll_interval)


def _get_task_result(task_id: str) -> Optional[Dict[str, Any]]:
    task = TaskManager().get_task(task_id)
    return task.result if task else None


def _wait_for_simulation(simulation_id: str, poll_interval: float = 2.0, on_update=None):
    last_snapshot = None
    while True:
        state = SimulationRunner.get_run_state(simulation_id)
        if state is None:
            raise RuntimeError(f"Simulation run state not found: {simulation_id}")
        snapshot = (state.runner_status.value, state.current_round, state.total_rounds, state.error)
        if snapshot != last_snapshot and on_update is not None:
            on_update(state)
            last_snapshot = snapshot
        if state.runner_status == RunnerStatus.COMPLETED:
            return state
        if state.runner_status == RunnerStatus.FAILED:
            raise RuntimeError(state.error or f"Simulation failed: {simulation_id}")
        time.sleep(poll_interval)


def _write_action_log(output_path: str, actions: List[Any]) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ordered = sorted(actions, key=lambda action: action.timestamp)
    with open(output_path, "w", encoding="utf-8") as handle:
        for action in ordered:
            handle.write(json.dumps(action.to_dict(), ensure_ascii=False) + "\n")
    return output_path


def _top_agents(agent_stats: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    ordered = sorted(agent_stats, key=lambda item: item.get("total_actions", 0), reverse=True)
    return ordered[:limit]


def _simulation_dir(simulation_id: str) -> str:
    return os.path.join(SimulationManager.SIMULATION_DATA_DIR, simulation_id)


def _record_if_copied(store: RunStore, run_id: str, key: str, source_path: str, rel_path: str) -> None:
    copied_path = store.copy_file(run_id, source_path, rel_path)
    if copied_path:
        store.record_artifact(run_id, key, rel_path)


def _record_if_exists(store: RunStore, run_id: str, key: str, rel_path: str) -> None:
    absolute_path = os.path.join(store.run_dir(run_id), rel_path)
    if os.path.exists(absolute_path):
        store.record_artifact(run_id, key, rel_path)


def _resolve_artifact_paths(store: RunStore, manifest: Dict[str, Any]) -> Dict[str, str]:
    run_dir = store.run_dir(manifest["run_id"])
    resolved: Dict[str, str] = {}
    for key, rel_path in manifest.get("artifacts", {}).items():
        absolute_path = os.path.abspath(os.path.join(run_dir, rel_path))
        if os.path.exists(absolute_path):
            resolved[key] = absolute_path
    return resolved


def _ensure_run_eval_artifact(store: RunStore, manifest: Dict[str, Any]) -> Dict[str, Any]:
    if manifest.get("status") != "completed":
        return manifest
    if manifest.get("artifacts", {}).get("run_eval"):
        return manifest

    payload = build_completed_run_eval(manifest, store.run_dir(manifest["run_id"]))
    store.write_json(manifest["run_id"], "eval/run_eval.v1.json", payload)
    return store.record_artifact(manifest["run_id"], "run_eval", "eval/run_eval.v1.json")


def _ensure_forecast_v1_artifact(store: RunStore, manifest: Dict[str, Any]) -> Dict[str, Any]:
    if manifest.get("status") != "completed":
        return manifest
    if manifest.get("artifacts", {}).get("forecast_v1"):
        return manifest
    imported_lineage = manifest.get("imported_lineage") or {}
    if not imported_lineage.get("brief_id") or not imported_lineage.get("brand_id"):
        return manifest

    forecast = build_completed_forecast_v1(manifest, store.run_dir(manifest["run_id"]))
    store.write_json(manifest["run_id"], "forecast/forecast.v1.json", forecast.model_dump(exclude_none=True))
    manifest = store.record_artifact(manifest["run_id"], "forecast_v1", "forecast/forecast.v1.json")
    return manifest


def _refresh_run_manifest(store: RunStore, run_id: str) -> Dict[str, Any]:
    manifest = store.load(run_id)
    changed = False

    if manifest.get("status") == "graph_building" and manifest.get("graph_build_task_id"):
        task = TaskManager().get_task(manifest["graph_build_task_id"])
        if task is not None:
            manifest["task_progress"] = task.progress
            manifest["task_message"] = task.message
            if task.status == TaskStatus.COMPLETED:
                manifest["status"] = "graph_ready"
                manifest["graph_id"] = (task.result or {}).get("graph_id")
            elif task.status == TaskStatus.FAILED:
                manifest["status"] = "failed"
                manifest["error"] = task.error or task.message
            changed = True

    if manifest.get("status") == "simulation_preparing" and manifest.get("prepare_task_id"):
        task = TaskManager().get_task(manifest["prepare_task_id"])
        if task is not None:
            manifest["task_progress"] = task.progress
            manifest["task_message"] = task.message
            if task.status == TaskStatus.COMPLETED:
                manifest["status"] = "simulation_ready"
            elif task.status == TaskStatus.FAILED:
                manifest["status"] = "failed"
                manifest["error"] = task.error or task.message
            changed = True

    if manifest.get("status") == "simulation_running" and manifest.get("simulation_id"):
        state = SimulationRunner.get_run_state(manifest["simulation_id"])
        if state is not None:
            manifest["task_progress"] = state.to_dict().get("progress_percent", 0)
            manifest["task_message"] = f"{state.current_round}/{state.total_rounds} rounds"
            if state.runner_status == RunnerStatus.COMPLETED:
                manifest["status"] = "simulation_completed"
            elif state.runner_status == RunnerStatus.FAILED:
                manifest["status"] = "failed"
                manifest["error"] = state.error
            changed = True

    if manifest.get("status") == "report_generating" and manifest.get("report_task_id"):
        task = TaskManager().get_task(manifest["report_task_id"])
        if task is not None:
            manifest["task_progress"] = task.progress
            manifest["task_message"] = task.message
            if task.status == TaskStatus.COMPLETED:
                manifest["status"] = "completed"
                manifest["report_id"] = (task.result or {}).get("report_id", manifest.get("report_id"))
            elif task.status == TaskStatus.FAILED:
                manifest["status"] = "failed"
                manifest["error"] = task.error or task.message
            changed = True

    if changed:
        manifest = store.save(manifest)
    manifest = _ensure_run_eval_artifact(store, manifest)
    return _ensure_forecast_v1_artifact(store, manifest)


def _collect_run_outputs(
    store: RunStore,
    manifest: Dict[str, Any],
    graph_data: Dict[str, Any],
    graph_stats: Dict[str, Any],
    timeline: List[Dict[str, Any]],
    agent_stats: List[Dict[str, Any]],
    actions: List[Any],
    report_payload: Optional[Dict[str, Any]],
    report_markdown: str,
) -> Dict[str, Any]:
    run_id = manifest["run_id"]

    store.write_json(run_id, "graph/graph.json", graph_data)
    store.record_artifact(run_id, "graph_json", "graph/graph.json")
    store.write_json(run_id, "graph/graph_summary.json", graph_stats)
    store.record_artifact(run_id, "graph_summary", "graph/graph_summary.json")

    store.write_json(run_id, "simulation/timeline.json", timeline)
    store.record_artifact(run_id, "timeline_json", "simulation/timeline.json")
    store.write_json(run_id, "simulation/top_agents.json", _top_agents(agent_stats))
    store.record_artifact(run_id, "top_agents", "simulation/top_agents.json")
    _write_action_log(os.path.join(store.run_dir(run_id), "simulation", "actions.jsonl"), actions)
    store.record_artifact(run_id, "actions_log", "simulation/actions.jsonl")

    sim_dir = _simulation_dir(manifest["simulation_id"])
    _record_if_copied(store, run_id, "simulation_config", os.path.join(sim_dir, "simulation_config.json"), "simulation/config.json")
    _record_if_copied(store, run_id, "reddit_profiles", os.path.join(sim_dir, "reddit_profiles.json"), "simulation/reddit_profiles.json")
    _record_if_copied(store, run_id, "twitter_profiles", os.path.join(sim_dir, "twitter_profiles.csv"), "simulation/twitter_profiles.csv")
    _record_if_copied(store, run_id, "simulation_log", os.path.join(sim_dir, "simulation.log"), "logs/simulation.log")

    if report_payload is not None:
        store.write_json(run_id, "report/meta.json", report_payload)
        store.record_artifact(run_id, "report_meta", "report/meta.json")
    if report_markdown:
        store.write_text(run_id, "report/report.md", report_markdown)
        store.record_artifact(run_id, "report_markdown", "report/report.md")

    _record_if_exists(store, run_id, "llm_telemetry", "logs/llm_telemetry.jsonl")

    summary = {
        "run_id": manifest["run_id"],
        "project_id": manifest.get("project_id"),
        "graph_id": manifest.get("graph_id"),
        "simulation_id": manifest.get("simulation_id"),
        "report_id": manifest.get("report_id"),
        "node_count": graph_stats.get("node_count", 0),
        "edge_count": graph_stats.get("edge_count", 0),
        "rounds": len(timeline),
        "total_actions": sum(item.get("total_actions", 0) for item in timeline),
        "top_agents": _top_agents(agent_stats, limit=10),
    }
    store.write_json(run_id, "report/summary.json", summary)
    store.record_artifact(run_id, "report_summary", "report/summary.json")

    visuals = generate_visual_snapshots(graph_data, timeline, os.path.join(store.run_dir(run_id), "visuals"))
    for key, absolute_path in visuals.items():
        relative = os.path.relpath(absolute_path, store.run_dir(run_id))
        store.record_artifact(run_id, key, relative)

    return store.load(run_id)


def _run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    source_files, requirement, imported_brief = _resolve_run_inputs(args)
    project_name = _default_project_name(source_files)
    store = RunStore(root_dir=args.output_dir)
    manifest = store.create(
        requirement,
        source_files,
        project_name=project_name,
        brief_path=getattr(args, "brief", None),
        imported_lineage=imported_brief.lineage if imported_brief else None,
    )
    run_id = manifest["run_id"]

    display = PipelineDisplay(
        project_name=project_name,
        run_id=run_id,
        provider=Config.LLM_PROVIDER,
        platform=args.platform,
        json_mode=args.json,
    )
    display.start()

    # Suppress service-layer console noise when rich display is active
    if not args.json:
        from .utils.logger import set_console_level
        set_console_level(logging.WARNING)

    store.write_text(run_id, "input/requirement.txt", requirement)
    store.record_artifact(run_id, "requirement", "input/requirement.txt")
    store.freeze_source_files(run_id, source_files)
    store.record_artifact(run_id, "source_files_dir", "input/source_files")
    if imported_brief:
        store.write_json(run_id, "input/brief.v1.json", imported_brief.brief.model_dump(exclude_none=True))
        store.record_artifact(run_id, "brief_v1", "input/brief.v1.json")
        store.write_json(run_id, "input/brief_lineage.json", imported_brief.frozen_input)
        store.record_artifact(run_id, "brief_lineage", "input/brief_lineage.json")

    telemetry_path = os.path.join(store.run_dir(run_id), "logs", "llm_telemetry.jsonl")
    previous_telemetry_path = os.environ.get("AGENTCY_LLM_TELEMETRY_FILE")
    os.environ["AGENTCY_LLM_TELEMETRY_FILE"] = telemetry_path

    session = WorkbenchSession.open(metadata={"entrypoint": "cli.run", "run_id": run_id})
    current_step = "simulation"

    try:
        if not args.smoke:
            require_simulation_runtime()
        current_step = "ontology"
        # --- ontology ---
        display.start_step("ontology")
        project_result = session.generate_ontology(
            simulation_requirement=requirement,
            uploaded_files=[LocalFileInput(path) for path in source_files],
            project_name=project_name,
        )
        ontology = project_result.get("ontology", {})
        n_entity_types = len(ontology.get("entity_types", []))
        n_edge_types = len(ontology.get("relationship_types", ontology.get("edge_types", [])))
        display.complete_step("ontology", f"{n_entity_types} entity types, {n_edge_types} edge types")

        store.update(run_id, project_id=project_result["project_id"], status="graph_building", task_progress=0, task_message="Ontology generated")
        store.write_json(run_id, "input/ontology.json", ontology)
        store.record_artifact(run_id, "ontology", "input/ontology.json")
        store.write_text(run_id, "input/analysis_summary.txt", project_result.get("analysis_summary", ""))
        store.record_artifact(run_id, "analysis_summary", "input/analysis_summary.txt")

        # --- graph ---
        current_step = "graph"
        display.start_step("graph")
        graph_result = session.start_graph_build(project_id=project_result["project_id"])
        store.update(run_id, graph_build_task_id=graph_result["task_id"], status="graph_building")
        _wait_for_task(
            graph_result["task_id"],
            on_update=lambda task: (
                store.update(run_id, status="graph_building", task_progress=task.progress, task_message=task.message),
                display.update_step("graph", task.message or ""),
            ),
        )
        graph_id = (_get_task_result(graph_result["task_id"]) or {}).get("graph_id")
        if not graph_id:
            raise RuntimeError("Graph build completed without a graph_id")

        graph_builder = GraphBuilderService()
        graph_db = GraphDatabase()
        graph_data = graph_builder.get_graph_data(graph_id)
        graph_stats = graph_db.get_graph_statistics(graph_id)
        n_nodes = graph_stats.get("node_count", 0)
        n_edges = graph_stats.get("edge_count", 0)
        display.complete_step("graph", f"{n_nodes} nodes, {n_edges} edges")
        store.update(run_id, graph_id=graph_id, status="graph_ready", task_progress=100, task_message="Graph ready")

        # --- profiles ---
        current_step = "profiles"
        display.start_step("profiles")
        enable_twitter = args.platform in {"parallel", "twitter"}
        enable_reddit = args.platform in {"parallel", "reddit"}
        simulation_state = session.create_simulation(
            project_id=project_result["project_id"],
            graph_id=graph_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
        )
        simulation_id = simulation_state.simulation_id
        store.update(run_id, simulation_id=simulation_id, status="simulation_preparing", task_progress=0, task_message="Simulation created")

        prepare_result = session.start_simulation_preparation(
            simulation_id=simulation_id,
            use_llm_for_profiles=True,
            parallel_profile_count=DEFAULT_PARALLEL_PROFILE_COUNT,
        )
        if prepare_result.get("task_id"):
            store.update(run_id, prepare_task_id=prepare_result["task_id"], status="simulation_preparing")
            _wait_for_task(
                prepare_result["task_id"],
                on_update=lambda task: (
                    store.update(run_id, status="simulation_preparing", task_progress=task.progress, task_message=task.message),
                    display.update_step("profiles", task.message or ""),
                ),
            )

        sim_dir = _simulation_dir(simulation_id)
        agent_count = 0
        config_path = os.path.join(sim_dir, "simulation_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                agent_count = len(json.load(f).get("agent_configs", []))
        display.complete_step("profiles", f"{agent_count} agents")
        store.update(run_id, status="simulation_ready", task_progress=100, task_message="Simulation ready")

        _record_if_copied(store, run_id, "frozen_simulation_config", os.path.join(sim_dir, "simulation_config.json"), "input/simulation_config.json")
        _record_if_copied(store, run_id, "frozen_reddit_profiles", os.path.join(sim_dir, "reddit_profiles.json"), "input/reddit_profiles.json")
        _record_if_copied(store, run_id, "frozen_twitter_profiles", os.path.join(sim_dir, "twitter_profiles.csv"), "input/twitter_profiles.csv")

        # --- simulation ---
        current_step = "simulation"
        display.start_step("simulation")
        report_payload = None
        report_markdown = ""
        report_id = None

        if args.smoke:
            smoke_outputs = build_smoke_outputs(
                sim_dir,
                run_id=run_id,
                simulation_id=simulation_id,
                graph_id=graph_id,
                requirement=requirement,
                platform=args.platform,
                max_rounds=args.max_rounds,
            )
            timeline = smoke_outputs["timeline"]
            agent_stats = smoke_outputs["agent_stats"]
            actions = smoke_outputs["actions"]
            report_payload = smoke_outputs["report_payload"]
            report_markdown = smoke_outputs["report_markdown"]
            report_id = report_payload["report_id"]
            total_actions = sum(item.get("total_actions", 0) for item in timeline)
            display.complete_step(
                "simulation",
                f"smoke mode — {len(timeline)} rounds, {total_actions} actions",
            )
            store.update(
                run_id,
                status="simulation_completed",
                task_progress=100,
                task_message="Smoke simulation completed",
                smoke_mode=True,
            )

            current_step = "report"
            display.start_step("report")
            display.complete_step("report", "smoke report")
        else:
            session.start_simulation_run(
                simulation_id=simulation_id,
                platform=args.platform,
                max_rounds=args.max_rounds,
                enable_graph_memory_update=False,
                wait_for_commands=False,
            )
            _wait_for_simulation(
                simulation_id,
                on_update=lambda state: (
                    store.update(run_id, status="simulation_running", task_progress=state.to_dict().get("progress_percent", 0), task_message=f"{state.current_round}/{state.total_rounds} rounds"),
                    display.update_step("simulation", f"round {state.current_round}/{state.total_rounds}"),
                ),
            )

            timeline = SimulationRunner.get_timeline(simulation_id)
            agent_stats = SimulationRunner.get_agent_stats(simulation_id)
            actions = SimulationRunner.get_all_actions(simulation_id)
            total_actions = sum(item.get("total_actions", 0) for item in timeline)
            display.complete_step("simulation", f"{len(timeline)} rounds, {total_actions} actions")
            store.update(run_id, status="simulation_completed", task_progress=100, task_message="Simulation completed")

            # --- report ---
            current_step = "report"
            display.start_step("report")
            report_store = ReportStore()

            report_result = session.start_report_generation(simulation_id=simulation_id)
            report_id = report_result.get("report_id")
            if report_result.get("task_id"):
                store.update(run_id, report_id=report_id, report_task_id=report_result["task_id"], status="report_generating")
                report_task = _wait_for_task(
                    report_result["task_id"],
                    on_update=lambda task: (
                        store.update(run_id, status="report_generating", task_progress=task.progress, task_message=task.message),
                        display.update_step("report", task.message or ""),
                    ),
                )
                report_id = (report_task.result or {}).get("report_id", report_id)
            if report_id:
                report = report_store.get(report_id)
                if report is not None:
                    report_payload = report.to_dict()
                    report_markdown = report.markdown_content
            display.complete_step("report", "done")

        # --- visuals ---
        current_step = "visuals"
        display.start_step("visuals")
        final_manifest = store.update(run_id, report_id=report_id, status="completed", task_progress=100, task_message="Run completed")
        final_manifest = _collect_run_outputs(
            store=store,
            manifest=final_manifest,
            graph_data=graph_data,
            graph_stats=graph_stats,
            timeline=timeline,
            agent_stats=agent_stats,
            actions=actions,
            report_payload=report_payload,
            report_markdown=report_markdown,
        )
        final_manifest = _ensure_run_eval_artifact(store, final_manifest)
        final_manifest = _ensure_forecast_v1_artifact(store, final_manifest)
        visual_keys = {"swarm_overview", "cluster_map", "timeline", "platform_split"}
        n_visuals = sum(1 for k in final_manifest.get("artifacts", {}) if k in visual_keys)
        display.complete_step("visuals", f"{n_visuals} snapshots")

        display.finish()
        return final_manifest
    except Exception as exc:
        display.fail_step(current_step, str(exc)[:80])
        display.finish()
        store.update(run_id, status="failed", error=str(exc), task_message=str(exc))
        raise
    finally:
        if previous_telemetry_path is None:
            os.environ.pop("AGENTCY_LLM_TELEMETRY_FILE", None)
        else:
            os.environ["AGENTCY_LLM_TELEMETRY_FILE"] = previous_telemetry_path


def _handle_command(args: argparse.Namespace) -> Dict[str, Any]:
    if args.command == "doctor":
        preflight = get_simulation_runtime_preflight()
        return {
            "command": "doctor",
            "ready": preflight["ready"],
            "checks": preflight,
        }
    if args.command == "runs" and args.runs_command == "list":
        store = RunStore(root_dir=args.output_dir)
        manifests = [_refresh_run_manifest(store, item["run_id"]) for item in store.list(limit=args.limit)]
        return {"runs": manifests, "count": len(manifests)}
    if args.command == "runs" and args.runs_command == "status":
        store = RunStore(root_dir=args.output_dir)
        return _refresh_run_manifest(store, args.run_id)
    if args.command == "runs" and args.runs_command == "export":
        store = RunStore(root_dir=args.output_dir)
        manifest = _refresh_run_manifest(store, args.run_id)
        artifacts = _resolve_artifact_paths(store, manifest)
        if args.artifact:
            if args.artifact not in artifacts:
                raise FileNotFoundError(f"Artifact not found for run {args.run_id}: {args.artifact}")
            return {
                "run_id": args.run_id,
                "artifact": args.artifact,
                "path": artifacts[args.artifact],
            }
        return {
            "run_id": args.run_id,
            "count": len(artifacts),
            "artifacts": artifacts,
        }
    if args.command == "run":
        return _run_pipeline(args)
    raise RuntimeError("Unknown command")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentcy-echo",
        description="Minimal run-first CLI for agentcy-echo",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Check simulation runtime readiness")
    doctor_parser.add_argument("--json", action="store_true")

    run_parser = subparsers.add_parser("run", help="Run the full workflow and persist artifacts")
    run_parser.add_argument("--files", nargs="+", required=True)
    run_parser.add_argument("--requirement")
    run_parser.add_argument("--brief", help="Canonical brief.v1 JSON input; derives the simulation requirement when supplied")
    run_parser.add_argument("--platform", choices=("parallel", "twitter", "reddit"), default="parallel")
    run_parser.add_argument("--max-rounds", type=int)
    run_parser.add_argument("--smoke", action="store_true", help="Skip the live OASIS runtime and emit deterministic smoke-mode artifacts")
    run_parser.add_argument("--wait", action="store_true", help="Accepted for consistency; end-to-end run waits by default")
    run_parser.add_argument("--output-dir")
    run_parser.add_argument("--json", action="store_true")

    runs_parser = subparsers.add_parser("runs", help="Inspect persisted runs")
    runs_subparsers = runs_parser.add_subparsers(dest="runs_command", required=True)
    runs_list = runs_subparsers.add_parser("list", help="List run manifests")
    runs_list.add_argument("--limit", type=int, default=20)
    runs_list.add_argument("--output-dir")
    runs_list.add_argument("--json", action="store_true")
    runs_status = runs_subparsers.add_parser("status", help="Show run status")
    runs_status.add_argument("run_id")
    runs_status.add_argument("--output-dir")
    runs_status.add_argument("--json", action="store_true")
    runs_export = runs_subparsers.add_parser("export", help="Resolve artifact paths for a run")
    runs_export.add_argument("run_id")
    runs_export.add_argument("--artifact")
    runs_export.add_argument("--output-dir")
    runs_export.add_argument("--json", action="store_true")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        payload = _handle_command(args)
        return _emit(payload, getattr(args, "json", False))
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            _stderr(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
