# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the functions behind ``smith --flag duplication_suggestion``.

The flag looks for redundancy in the policy two independent ways and concatenates
both reports::

    BlueAgent.get_duplication_feedback()
        init_graph(ast, policy_dir, graph_path)      OPA parse -> a rule-call graph
        update_policy_analysis_feedback(...)         LLM: duplicate/cyclic rules
        write_graph_suggestion(graph, out)           GRAPH: rules unreachable from
                                                     `allow`, i.e. dead code

SCOPE: THE GRAPH HALF IS THE SUBSTANCE
--------------------------------------
The LLM half is a prompt plus a markdown render, and it is the integration lane's
business. The **graph** half is real, self-contained logic — set arithmetic over a
NetworkX graph — and it decides which policy rules get reported as dead. That is
what this file covers, offline and deterministically, by building graphs directly
rather than parsing Rego.

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order the flag executes them.

STEP 1 · ``smith.policy_agent.scripts.parse_ast_to_graph``
    ``init_graph``                      — the module-level index reset, so two
                                          graphs built in one process agree

STEP 2 · ``smith.policy_agent.reduce_improve.detect_redundancy``
    ``find_node_by_name``               — locating the ``allow`` root by substring
    ``save_unreachable_components_dot`` — reachability: what is NOT reachable from
                                          ``allow``, grouped into components
    ``clean_graph``                     — the white-list prune
    ``print_subgraphs``                 — the report a human reads, and the file

NOT COVERED HERE (integration lane — see ``test_duplication_suggestion_integration.py``)
    ``opa parse`` producing a real AST, the LLM half, and the CLI wiring.

Deliberately absent: ``expand_all_edgepaths_with_cycles`` and
``save_dead_route_components``. Both are commented out of ``write_graph_suggestion``,
so no flag reaches them — see the pinned test at the end.

Env-free: graphs are built in memory; no OPA, no Docker, no LLM.
"""

from __future__ import annotations

import networkx as nx
import pytest

from smith.policy_agent.reduce_improve.detect_redundancy import (
    clean_graph,
    find_node_by_name,
    print_subgraphs,
    save_unreachable_components_dot,
)

pytestmark = pytest.mark.unit


def policy_graph():
    """A rule-call graph in the shape ``parse_ast_to_graph`` emits."""
    graph = nx.DiGraph()
    graph.add_edge("0& allow", "1& valid_envelope")
    graph.add_edge("0& allow", "2& user_role")
    graph.add_edge("3& dead_rule", "4& orphan_var")
    return graph


# ===========================================================================
# STEP 1 · init_graph — the state reset
# ===========================================================================


def test_repeated_graph_builds_do_not_inherit_earlier_node_indices(monkeypatch):
    from smith.policy_agent.scripts import parse_ast_to_graph as ast_mod

    # Seed the module state as a previous parse would have left it.
    ast_mod.head_rule_index["stale_rule"] = "7"
    ast_mod.index_to_count["7"] = 3

    monkeypatch.setattr(ast_mod, "create_ast", lambda *a, **k: None)
    monkeypatch.setattr(ast_mod, "load_ast", lambda *a, **k: [])
    monkeypatch.setattr(ast_mod, "extract_rule_calls", lambda modules, G: (G, None))
    monkeypatch.setattr(ast_mod, "merge_nodes_with_same_io_and_type", lambda G: G)
    monkeypatch.setattr(ast_mod, "clean_graph", lambda G: G)
    monkeypatch.setattr(ast_mod.nx.drawing.nx_pydot, "write_dot", lambda *a, **k: None)

    ast_mod.init_graph("ast.json", "policy_dir", "graph.dot", saver=False)

    assert ast_mod.head_rule_index == {}, "stale rule indices survived into a new graph"
    assert ast_mod.index_to_count == {}


# ===========================================================================
# STEP 2 · find_node_by_name — locating the root
# ===========================================================================


def test_the_allow_root_is_found_by_substring():
    # Node names carry an index prefix, so the caller cannot know the exact name and
    # searches for "& allow" instead.
    assert find_node_by_name(policy_graph(), "& allow") == "0& allow"


def test_a_policy_without_an_allow_rule_yields_an_empty_root():
    """Pinned: the miss returns ``""``, not ``None`` — and that then raises.

    ``write_graph_suggestion`` passes the result straight to
    ``save_unreachable_components_dot``, which rejects a source that is not in the
    graph. So a policy with no ``allow`` rule fails with "source '' not in graph".
    """
    graph = nx.DiGraph()
    graph.add_edge("0& deny", "1& something")

    assert find_node_by_name(graph, "& allow") == ""

    with pytest.raises(ValueError, match="not in graph"):
        save_unreachable_components_dot(graph, "", save=False)


# ===========================================================================
# STEP 2 · save_unreachable_components_dot — the reachability analysis
# ===========================================================================


def test_only_rules_unreachable_from_allow_are_reported(unit_env):
    """CORRECTNESS: this set arithmetic *is* the dead-code finding.

    Anything reachable from ``allow`` participates in the decision and must never be
    reported — suggesting a live rule be deleted would break the policy. Anything
    else is unreachable and therefore redundant.
    """
    graph = policy_graph()
    root = find_node_by_name(graph, "& allow")

    result = save_unreachable_components_dot(
        graph, root, save=False, out_path=str(unit_env.root / "u.dot")
    )

    assert set(result.nodes()) == {"3& dead_rule", "4& orphan_var"}
    # The live rules are excluded, which is the half that matters most.
    for live in ("0& allow", "1& valid_envelope", "2& user_role"):
        assert live not in result.nodes()


def test_a_fully_reachable_policy_reports_nothing(unit_env):
    # The good outcome: every rule contributes. An empty result must come back as an
    # empty graph rather than raising, so the flag reports "no redundancy".
    graph = nx.DiGraph()
    graph.add_edge("0& allow", "1& valid_envelope")

    result = save_unreachable_components_dot(
        graph, "0& allow", save=False, out_path=str(unit_env.root / "u.dot")
    )

    assert len(result) == 0


def test_separate_dead_regions_are_labelled_as_separate_components(unit_env):
    # The component id is what splits the report into "subgraph 1", "subgraph 2" —
    # two unrelated dead regions are two independent things to delete, so merging
    # them would misrepresent the work.
    graph = policy_graph()
    graph.add_edge("5& other_dead", "6& other_orphan")

    result = save_unreachable_components_dot(
        graph,
        find_node_by_name(graph, "& allow"),
        save=False,
        out_path=str(unit_env.root / "u.dot"),
    )

    components = {result.nodes[n]["component"] for n in result.nodes()}
    assert len(components) == 2, f"expected two dead regions, got {components}"


def test_an_unknown_mode_is_rejected(unit_env):
    with pytest.raises(ValueError, match="only support"):
        save_unreachable_components_dot(
            policy_graph(),
            "0& allow",
            mode="sideways",
            save=False,
            out_path=str(unit_env.root / "u.dot"),
        )


def test_the_dot_file_is_written_only_when_asked(unit_env):
    # `save=False` is how a caller inspects the graph without leaving a file behind.
    out = unit_env.root / "unreachable.dot"

    save_unreachable_components_dot(
        policy_graph(), "0& allow", save=False, out_path=str(out)
    )
    assert not out.exists()

    save_unreachable_components_dot(
        policy_graph(), "0& allow", save=True, out_path=str(out)
    )
    assert out.exists()

# ===========================================================================
# STEP 2 · clean_graph — the white-list prune
# ===========================================================================


def test_white_listed_rules_are_dropped_from_the_report(unit_env):
    # These three rule names are known-good scaffolding that is legitimately
    # unreachable, so reporting them every run would be noise a reviewer learns to
    # ignore — which is how real findings get missed.
    graph = nx.DiGraph()
    graph.add_node("0& resource_violations")
    graph.add_node("1& command_structure_violations")
    graph.add_node("2& flag_violations")
    graph.add_node("3& genuinely_dead")

    result = clean_graph(graph)

    assert set(result.nodes()) == {"3& genuinely_dead"}


def test_a_rule_merely_containing_a_white_listed_name_is_kept():
    # The match is exact on the rule name, not a substring, so a differently-named
    # rule is not silently swallowed.
    graph = nx.DiGraph()
    graph.add_node("0& resource_violations_extra")

    assert set(clean_graph(graph).nodes()) == {"0& resource_violations_extra"}


# ===========================================================================
# STEP 2 · print_subgraphs — the report
# ===========================================================================


def test_the_node_list_names_the_rules_without_their_index_prefixes(unit_env):
    """CORRECTNESS: a reviewer has to recognise the rule to delete it.

    Node names carry a ``"3& "`` graph index that means nothing in the policy file,
    so the ``node:`` line strips it. Leaving it in would make the suggestion
    unactionable.
    """
    graph = nx.DiGraph()
    graph.add_edge("3& dead_rule", "4& orphan_var")
    out = unit_env.root / "suggestion.txt"

    text = print_subgraphs(graph, str(out))

    node_line = text.split("node:")[1].split("\n")[1]
    assert "dead_rule" in node_line and "orphan_var" in node_line
    assert (
        "3&" not in node_line
    ), f"the graph index leaked into the node list: {node_line}"

def test_the_report_is_written_and_returned(unit_env):
    # The return value is concatenated into the flag's stdout; the file is what a
    # reviewer keeps. They must agree.
    graph = nx.DiGraph()
    graph.add_edge("3& dead_rule", "4& orphan_var")
    out = unit_env.root / "suggestion.txt"

    text = print_subgraphs(graph, str(out))

    assert out.read_text() == text
    assert "unreachable" in text, "the report must explain what it is showing"


def test_each_dead_region_is_reported_as_its_own_subgraph(unit_env):
    # Two independent regions are two separate deletions, so the report enumerates
    # them rather than presenting one merged blob.
    graph = nx.DiGraph()
    graph.add_edge("3& dead_a", "4& dead_b")
    graph.add_edge("5& dead_c", "6& dead_d")
    out = unit_env.root / "suggestion.txt"

    text = print_subgraphs(graph, str(out))

    assert "subgraph 1:" in text and "subgraph 2:" in text


def test_a_clean_policy_still_produces_a_report_with_no_subgraphs(unit_env):
    # The "nothing to do" outcome must be stated, since an empty file is
    # indistinguishable from a run that never happened.
    out = unit_env.root / "suggestion.txt"

    text = print_subgraphs(nx.DiGraph(), str(out))

    assert "subgraph 1:" not in text
    assert text.strip(), "even a clean policy gets the explanatory header"