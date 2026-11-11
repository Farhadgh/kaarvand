"""Workflow graph validation.

Node *types* are a fixed registry (executable in step 5); the *composition* is
data, so a supervisor agent delegating to accountant/sales agents is built in the
panel, not in code.
"""

from __future__ import annotations

from typing import Any

from app.core.errors import AppError

NODE_TYPES = {
    "start",
    "end",
    "llm",
    "tool",
    "condition",
    "human_approval",
    "parallel",
    "loop",
    "transform",
    "handoff",
}


def validate_graph(graph: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(graph, dict):
        raise AppError(code="workflow.invalid", status_code=422, params={"reason": "not_object"})

    nodes = graph.get("nodes")
    edges = graph.get("edges", [])
    if not isinstance(nodes, list) or not nodes:
        raise AppError(code="workflow.invalid", status_code=422, params={"reason": "no_nodes"})
    if not isinstance(edges, list):
        raise AppError(
            code="workflow.invalid",
            status_code=422,
            params={"reason": "edges_not_list"},
        )

    ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            raise AppError(
                code="workflow.invalid",
                status_code=422,
                params={"reason": "node_without_id"},
            )
        node_id = str(node["id"])
        if node_id in ids:
            raise AppError(
                code="workflow.invalid",
                status_code=422,
                params={"reason": "duplicate_node", "id": node_id},
            )
        ids.add(node_id)
        node_type = node.get("type")
        if node_type not in NODE_TYPES:
            raise AppError(
                code="workflow.invalid",
                status_code=422,
                params={"reason": "unknown_node_type", "type": node_type},
            )

    starts = [node for node in nodes if node.get("type") == "start"]
    if len(starts) != 1:
        raise AppError(
            code="workflow.invalid", status_code=422, params={"reason": "need_single_start"}
        )

    for edge in edges:
        if not isinstance(edge, dict):
            raise AppError(code="workflow.invalid", status_code=422, params={"reason": "bad_edge"})
        for key in ("from", "to"):
            if str(edge.get(key)) not in ids:
                raise AppError(
                    code="workflow.invalid",
                    status_code=422,
                    params={"reason": "unknown_edge_target", "value": edge.get(key)},
                )
    return graph
