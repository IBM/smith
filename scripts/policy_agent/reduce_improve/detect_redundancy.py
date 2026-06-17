import networkx as nx
from typing import List, Union, Set, Iterable, Optional, Hashable, Tuple


def read_graph(file_path):
    G = nx.MultiDiGraph(nx.drawing.nx_pydot.read_dot(file_path))
    return G


def save_unreachable_components_dot(
    G: nx.DiGraph,
    source,
    *,
    mode: str = "weak",
    out_path: str = "unreachable.dot",
    save=False,
):

    if source not in G:
        raise ValueError(f"source {source!r} not in graph")

    reachable = {source} | nx.descendants(G, source)
    unreachable_nodes = set(G.nodes()) - reachable
    H_all = G.subgraph(unreachable_nodes).copy()
    if len(H_all) == 0:
        nx.drawing.nx_pydot.write_dot(H_all, out_path)
        return H_all

    if mode == "weak":
        comps = list(nx.weakly_connected_components(H_all))
    elif mode == "strong":
        comps = list(nx.strongly_connected_components(H_all))
    else:
        raise ValueError("only support 'weak' or 'strong'")

    for idx, nodes in enumerate(comps, start=1):
        for n in nodes:
            H_all.nodes[n]["component"] = idx

    H_all.graph["mode"] = mode
    H_all.graph["source"] = source

    if save:
        nx.drawing.nx_pydot.write_dot(H_all, out_path)
    return H_all


def find_node_by_name(G, node_name):
    for i in G.nodes():
        if node_name in i:
            return i
    return ""


EdgeStep = Tuple[Hashable, Optional[object], str, Hashable]


def parse_index(node: Hashable) -> str:
    s = str(node)
    return s.split("&", 1)[0].strip() if "&" in s else s.strip()


def _normalize_labels(x: Union[str, List[str], Tuple[str, ...], None]) -> List[str]:
    if x is None:
        return []
    if "[" in x and "]" in x:
        str_list = x.split(", ")
        str_list[0] = str_list[0][2:]
        str_list[-1] = str_list[-1][:-2]
        for str_list_index in range(len(str_list)):
            str_list[str_list_index] = str_list[str_list_index][1:-1]
        return str_list
    else:
        return [x]


def _eligible_edge_labels_for_node_index(
    edge_labels: Iterable[str], node_idx: int
) -> List[str]:
    prefix = f"{node_idx}"
    return [
        lab
        for lab in edge_labels
        if isinstance(lab, str) and lab.split(".")[0] == prefix
    ]


def outgoing_edges_with_data(G, u):
    for _, v, key, data in G.out_edges(u, keys=True, data=True):
        yield u, v, key, data


def fetch_edge_subpaths(G, root) -> List[List[EdgeStep]]:
    paths: List[List[EdgeStep]] = []

    def dfs(G, u: Hashable, u_idx, acc: List[EdgeStep]):
        eligible_steps: List[EdgeStep] = []
        for uu, v, key, data in outgoing_edges_with_data(G, u):
            labs = _normalize_labels(data.get("label"))
            match_labels = _eligible_edge_labels_for_node_index(labs, u_idx)
            for lab in match_labels:
                eligible_steps.append((uu, key, lab, v))  # store (u,key,label,v)
        if not eligible_steps:
            paths.append(list(acc))
            return
        for uu, key, lab, v in eligible_steps:
            acc.append((uu, key, lab, v))
            dfs(G, v, u_idx, acc)
            acc.pop()

    u_idx = parse_index(root)
    dfs(G, root, u_idx, [])
    return paths


def _cycle_canonical_signature(cycle_edges: List[EdgeStep]) -> Tuple:
    if not cycle_edges:
        return ()
    seq = tuple(cycle_edges)

    def rotations(t):
        n = len(t)
        for i in range(n):
            yield t[i:] + t[:i]

    def reverse_edges(t):
        return tuple((v, k, lab, u) for (u, k, lab, v) in reversed(t))

    candidates = list(rotations(seq))
    rev_candidates = list(rotations(reverse_edges(seq)))
    best = min(candidates + rev_candidates)
    return best


def process_fetch_edge_subpaths(fetch_list):
    if len(fetch_list) == 1 and len(fetch_list[0]) == 0:
        return fetch_list[0]
    return fetch_list


def expand_all_edgepaths_with_cycles(
    G, root, allow_revisits=False, max_visits_per_node=3
):
    results: List[List[EdgeStep]] = []
    visit_count = {}
    total_steps = 0
    cycles_G = nx.MultiDiGraph()
    seen_cycle_sigs: Set[Tuple] = set()

    def can_visit(node: Hashable) -> bool:
        if allow_revisits:
            return visit_count.get(node, 0) < max_visits_per_node
        return visit_count.get(node, 0) == 0

    def inc(node: Hashable):
        visit_count[node] = visit_count.get(node, 0) + 1

    def dec(node: Hashable):
        visit_count[node] -= 1
        if visit_count[node] <= 0:
            visit_count.pop(node, None)

    def add_cycle(cycle_edges: List[EdgeStep]):
        if not cycle_edges:
            return
        sig = _cycle_canonical_signature(cycle_edges)
        if sig in seen_cycle_sigs:
            return
        seen_cycle_sigs.add(sig)
        for u, k, lab, v in cycle_edges:
            if k is None:
                cycles_G.add_edge(u, v, label=lab)
            else:
                cycles_G.add_edge(u, v, key=k, label=lab)

    def dfs(G, paths, acc_edges, acc_nodes):
        nonlocal total_steps
        candidates = []
        results = []
        fetched = list(process_fetch_edge_subpaths(fetch_edge_subpaths(G, node)))
        candidates.extend(fetched)
        if len(candidates) == 0:
            results.extend(list(acc_edges))
            return results, cycles_G
        for seg in candidates:
            if not seg:
                continue
            for i, (u, k, lab, v) in enumerate(seg):
                if v in acc_nodes:
                    idx = acc_nodes.index(v)
                    cycle_edges = acc_edges[idx:] + [(u, k, lab, v)]
                    add_cycle(cycle_edges)
                if not can_visit(v):
                    break
                inc(v)
                acc_edges.append((u, k, lab, v))
                acc_nodes.append(v)
                dfs(G, v, acc_edges, acc_nodes)
                acc_edges.pop()
                acc_nodes.pop()
                dec(v)

    inc(root)
    dfs(G, root, [], [root])
    dec(root)

    return results, cycles_G


def save_dead_route_components(G, node_name, mode):
    results = []
    for n in G.predecessors(node_name):
        out_edges = list(G.out_edges(n))
        in_edges = list(G.in_edges(n))
        if len(out_edges) == 1 and len(in_edges) == 0:
            results.append(n)
    H_all = G.subgraph(results).copy()
    nx.drawing.nx_pydot.write_dot(H_all, "dead_route_" + mode + ".dot")
    return H_all


import networkx as nx


def print_subgraphs(G: nx.Graph, suggestion_path):
    print_results = []
    print_results.append(
        "Each subgraph represents unreachable (impossible to reach) parts in policy, which should be considered as redundant. The node represents a rule or a variable. The edges are relations between them"
    )
    if G.is_directed():
        components = nx.weakly_connected_components(G)
    else:
        components = nx.connected_components(G)
    for i, nodes in enumerate(components, 1):
        subG = G.subgraph(nodes)
        nodes = []
        for sub_node in list(subG.nodes()):
            if len(sub_node.split("& ")) > 1:
                nodes.append(sub_node.split("& ")[1])
        print_results.append(f"subgraph {i}:")
        print_results.append("node:")
        print_results.append(str(nodes))
        if len(list(subG.edges())) != 0:
            print_results.append("edge:")
            print_results.append(str(list(subG.edges())))
        print_results.append("\n")

    with open(suggestion_path, "w", encoding="utf-8") as f:
        f.write("\n".join(print_results))
    return "\n".join(print_results)


white_list = ["resource_violations", "command_structure_violations", "flag_violations"]


def clean_graph(G):
    remove_nodes = []
    for node in G.nodes():
        for filtered_value in white_list:
            if len(str(node).split("&")) > 1 and len(str(node).split("&")[1]) > 2:
                if filtered_value == str(node).split("&")[1][1:]:
                    remove_nodes.append(node)
    for node in remove_nodes:
        G.remove_node(node)
    return G


def write_graph_suggestion(file_path, suggestion_path):
    G = read_graph(file_path=file_path)
    G_allow = save_unreachable_components_dot(
        G, find_node_by_name(G, "& allow"), save=True
    )
    G_allow = clean_graph(G_allow)
    return print_subgraphs(G_allow, suggestion_path)
    # G_deny=save_unreachable_components_dot(G, find_node_by_name(G, '& deny'))
    # G_unreachable=save_unreachable_components_dot(G_allow, find_node_by_name(G, '& deny'), save=True)
    # G_dead_route_part_deny=save_dead_route_components(G_allow, find_node_by_name(G, '& deny'), 'deny')
    # G_dead_route_part_allow=save_dead_route_components(G_allow, find_node_by_name(G, '& allow'), 'allow')
    # tracks=expand_from_root_with_refinement(G, "0& allow")
    # paths, cycles = expand_all_edgepaths_with_cycles(G, '0& allow')
    # # print(cycles.edges())
    # # for path in paths[1]:
    # #     print(path[2])
