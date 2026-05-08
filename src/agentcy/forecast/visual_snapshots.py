"""Generate self-contained SVG snapshots for completed runs."""

from __future__ import annotations

import math
import os
from collections import defaultdict
from html import escape
from typing import Any, Dict, Iterable, List, Tuple


PALETTE = (
    "#0F4C5C",
    "#E36414",
    "#6A994E",
    "#BC4749",
    "#7B2CBF",
    "#2A9D8F",
    "#C1121F",
    "#4361EE",
)


def _write_svg(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


def _label_for_node(node: Dict[str, Any]) -> str:
    for label in node.get("labels", []):
        if label not in {"Entity", "Node"}:
            return label
    return "Entity"


def _color_map(labels: Iterable[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for index, label in enumerate(sorted(set(labels))):
        mapping[label] = PALETTE[index % len(PALETTE)]
    return mapping


def _graph_adjacency(graph_data: Dict[str, Any]) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    adjacency: Dict[str, List[str]] = defaultdict(list)
    degree: Dict[str, int] = defaultdict(int)
    for edge in graph_data.get("edges", []):
        source = edge.get("source_node_uuid") or edge.get("source_id")
        target = edge.get("target_node_uuid") or edge.get("target_id")
        if not source or not target:
            continue
        adjacency[source].append(target)
        adjacency[target].append(source)
        degree[source] += 1
        degree[target] += 1
    return adjacency, degree


def _connected_components(graph_data: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    node_map = {node.get("uuid"): node for node in graph_data.get("nodes", []) if node.get("uuid")}
    adjacency, _degree = _graph_adjacency(graph_data)
    seen: set[str] = set()
    components: List[List[Dict[str, Any]]] = []

    for node_id, node in node_map.items():
        if node_id in seen:
            continue
        stack = [node_id]
        component: List[Dict[str, Any]] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            current_node = node_map.get(current)
            if current_node is not None:
                component.append(current_node)
            for neighbor in adjacency.get(current, []):
                if neighbor not in seen:
                    stack.append(neighbor)
        if component:
            components.append(component)
    components.sort(key=len, reverse=True)
    return components


def render_swarm_overview(graph_data: Dict[str, Any], output_path: str) -> str:
    width, height = 1200, 900
    cx, cy = width / 2, height / 2
    radius = min(width, height) * 0.34
    nodes = graph_data.get("nodes", [])
    adjacency, degree = _graph_adjacency(graph_data)
    labels = [_label_for_node(node) for node in nodes]
    colors = _color_map(labels)

    positions: Dict[str, Tuple[float, float]] = {}
    total = max(len(nodes), 1)
    for index, node in enumerate(nodes):
        node_id = node.get("uuid", "")
        angle = (2 * math.pi * index / total) - (math.pi / 2)
        local_radius = radius * (0.75 + 0.25 * ((degree.get(node_id, 0) % 5) / 4 if degree.get(node_id, 0) else 0))
        positions[node_id] = (
            cx + math.cos(angle) * local_radius,
            cy + math.sin(angle) * local_radius,
        )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#F7F4EA" />',
        '<text x="48" y="64" font-family="Menlo, monospace" font-size="30" fill="#1D1D1D">Swarm Overview</text>',
        f'<text x="48" y="94" font-family="Menlo, monospace" font-size="15" fill="#555">Nodes: {graph_data.get("node_count", len(nodes))}  |  Edges: {graph_data.get("edge_count", len(graph_data.get("edges", [])))}</text>',
    ]

    for edge in graph_data.get("edges", []):
        source = edge.get("source_node_uuid") or edge.get("source_id")
        target = edge.get("target_node_uuid") or edge.get("target_id")
        if source not in positions or target not in positions:
            continue
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#BBB3A7" stroke-width="1.2" opacity="0.7" />'
        )

    for node in nodes:
        node_id = node.get("uuid", "")
        x, y = positions.get(node_id, (cx, cy))
        label = _label_for_node(node)
        color = colors[label]
        node_radius = 8 + min(degree.get(node_id, 0), 10)
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{node_radius}" fill="{color}" fill-opacity="0.92" stroke="#FFFFFF" stroke-width="2" />'
        )
        if degree.get(node_id, 0) >= 2:
            text = escape(str(node.get("name", ""))[:20])
            parts.append(
                f'<text x="{x + node_radius + 6:.2f}" y="{y + 5:.2f}" font-family="Menlo, monospace" font-size="12" fill="#222">{text}</text>'
            )

    legend_x, legend_y = 48, height - 40 - (18 * len(colors))
    for index, (label, color) in enumerate(colors.items()):
        y = legend_y + (index * 22)
        parts.append(f'<rect x="{legend_x}" y="{y}" width="14" height="14" rx="3" fill="{color}" />')
        parts.append(
            f'<text x="{legend_x + 22}" y="{y + 12}" font-family="Menlo, monospace" font-size="13" fill="#333">{escape(label)}</text>'
        )

    parts.append("</svg>")
    return _write_svg(output_path, "".join(parts))


def render_cluster_map(graph_data: Dict[str, Any], output_path: str) -> str:
    width, height = 1200, 800
    components = _connected_components(graph_data)[:8]
    components = [component for component in components if component]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FCFAF5" />',
        '<text x="48" y="64" font-family="Menlo, monospace" font-size="30" fill="#1D1D1D">Cluster Map</text>',
        '<text x="48" y="94" font-family="Menlo, monospace" font-size="15" fill="#555">Connected components in the graph, sized by member count.</text>',
    ]

    if not components:
        parts.extend(
            [
                '<rect x="160" y="180" width="880" height="420" rx="28" fill="#FFFFFF" stroke="#E6DED2" stroke-width="2" />',
                '<text x="600" y="340" text-anchor="middle" font-family="Menlo, monospace" font-size="26" fill="#1D1D1D">No graph nodes available</text>',
                '<text x="600" y="384" text-anchor="middle" font-family="Menlo, monospace" font-size="15" fill="#666">Build a graph with extracted entities to populate this snapshot.</text>',
                "</svg>",
            ]
        )
        return _write_svg(output_path, "".join(parts))

    cols = 4
    row_height = 280
    bubble_scale = 26
    for index, component in enumerate(components):
        row = index // cols
        col = index % cols
        x = 170 + col * 260
        y = 220 + row * row_height
        component_size = max(len(component), 1)
        labels = [_label_for_node(node) for node in component]
        dominant = max(set(labels), key=labels.count) if labels else "Entity"
        color = _color_map(labels).get(dominant, PALETTE[index % len(PALETTE)])
        bubble_radius = bubble_scale + min(component_size, 18) * 8
        representative = ", ".join(node.get("name", "") for node in component[:3] if node.get("name")) or "Unlabeled"

        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{bubble_radius}" fill="{color}" fill-opacity="0.88" stroke="#FFFFFF" stroke-width="3" />'
        )
        parts.append(
            f'<text x="{x}" y="{y - 6}" text-anchor="middle" font-family="Menlo, monospace" font-size="16" fill="#FFFFFF">{component_size} nodes</text>'
        )
        parts.append(
            f'<text x="{x}" y="{y + 16}" text-anchor="middle" font-family="Menlo, monospace" font-size="13" fill="#FFFFFF">{escape(dominant)}</text>'
        )
        parts.append(
            f'<text x="{x}" y="{y + bubble_radius + 28}" text-anchor="middle" font-family="Menlo, monospace" font-size="12" fill="#333">{escape(representative[:34])}</text>'
        )

    parts.append("</svg>")
    return _write_svg(output_path, "".join(parts))


def render_timeline(timeline: List[Dict[str, Any]], output_path: str) -> str:
    width, height = 1200, 700
    chart_left, chart_top = 80, 120
    chart_width, chart_height = 1050, 500
    rounds = timeline or [{"round_num": 0, "total_actions": 0}]
    max_actions = max(item.get("total_actions", 0) for item in rounds) or 1

    points = []
    for index, item in enumerate(rounds):
        x = chart_left + (chart_width * index / max(len(rounds) - 1, 1))
        y = chart_top + chart_height - (chart_height * item.get("total_actions", 0) / max_actions)
        points.append((x, y, item))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#F7F6F2" />',
        '<text x="48" y="64" font-family="Menlo, monospace" font-size="30" fill="#1D1D1D">Activity Timeline</text>',
        '<text x="48" y="94" font-family="Menlo, monospace" font-size="15" fill="#555">Total actions per simulation round.</text>',
        f'<rect x="{chart_left}" y="{chart_top}" width="{chart_width}" height="{chart_height}" fill="#FFFFFF" stroke="#DDD4C8" stroke-width="2" />',
    ]

    for step in range(6):
        y = chart_top + (chart_height * step / 5)
        value = int(round(max_actions * (5 - step) / 5))
        parts.append(f'<line x1="{chart_left}" y1="{y}" x2="{chart_left + chart_width}" y2="{y}" stroke="#ECE7DE" stroke-width="1" />')
        parts.append(
            f'<text x="{chart_left - 12}" y="{y + 5}" text-anchor="end" font-family="Menlo, monospace" font-size="12" fill="#666">{value}</text>'
        )

    if points:
        polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y, _item in points)
        parts.append(f'<polyline fill="none" stroke="#E36414" stroke-width="4" points="{polyline}" />')
        for x, y, item in points:
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="#E36414" />')
            parts.append(
                f'<text x="{x:.2f}" y="{chart_top + chart_height + 24}" text-anchor="middle" font-family="Menlo, monospace" font-size="11" fill="#444">{item.get("round_num", 0)}</text>'
            )

    parts.append("</svg>")
    return _write_svg(output_path, "".join(parts))


def render_platform_split(timeline: List[Dict[str, Any]], output_path: str) -> str:
    width, height = 1200, 720
    twitter_total = sum(item.get("twitter_actions", 0) for item in timeline)
    reddit_total = sum(item.get("reddit_actions", 0) for item in timeline)
    combined = max(twitter_total, reddit_total, 1)

    bars = [
        ("Twitter", twitter_total, "#4361EE", 320),
        ("Reddit", reddit_total, "#FF4500", 720),
    ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FAF8F2" />',
        '<text x="48" y="64" font-family="Menlo, monospace" font-size="30" fill="#1D1D1D">Platform Split</text>',
        '<text x="48" y="94" font-family="Menlo, monospace" font-size="15" fill="#555">Aggregate action volume by platform.</text>',
    ]

    for label, value, color, x in bars:
        bar_height = 360 * (value / combined)
        y = 560 - bar_height
        parts.append(f'<rect x="{x}" y="{y:.2f}" width="160" height="{bar_height:.2f}" rx="18" fill="{color}" opacity="0.9" />')
        parts.append(f'<text x="{x + 80}" y="{y - 16:.2f}" text-anchor="middle" font-family="Menlo, monospace" font-size="22" fill="#222">{value}</text>')
        parts.append(f'<text x="{x + 80}" y="604" text-anchor="middle" font-family="Menlo, monospace" font-size="18" fill="#333">{escape(label)}</text>')

    parts.append("</svg>")
    return _write_svg(output_path, "".join(parts))


def generate_visual_snapshots(
    graph_data: Dict[str, Any],
    timeline: List[Dict[str, Any]],
    output_dir: str,
) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    artifacts = {
        "swarm_overview": render_swarm_overview(graph_data, os.path.join(output_dir, "swarm-overview.svg")),
        "cluster_map": render_cluster_map(graph_data, os.path.join(output_dir, "cluster-map.svg")),
        "timeline": render_timeline(timeline, os.path.join(output_dir, "timeline.svg")),
        "platform_split": render_platform_split(timeline, os.path.join(output_dir, "platform-split.svg")),
    }
    return artifacts
