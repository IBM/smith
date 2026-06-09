import json
from collections import defaultdict
import networkx as nx
from collections import defaultdict, deque
import json
from typing import Iterable, List, Tuple, Set, Dict, Any, Hashable
from dotenv import load_dotenv
import subprocess
import os
load_dotenv()

global head_rule_index
head_rule_index={}
global filter_functions
filter_functions=['parse_resource_types','trim']
global filter_values
filter_values=['True','None', 'False', '     ', 's']
global index_to_count
index_to_count={}


from typing import Iterable, Hashable, Dict, Any, List, Set, Tuple, Optional

def compress_by_constant_index_paths(
    G: nx.MultiDiGraph,
    keep_nodes: Iterable[Hashable],
    index_attr: str = "index",
    store_path: bool = True,
) -> nx.MultiDiGraph:
    keep: Set[Hashable] = set(keep_nodes)
    H = nx.MultiDiGraph()
    for n in keep:
        if G.has_node(n):
            H.add_node(n, **G.nodes[n])
        else:
            H.add_node(n)

    index_values = {d[index_attr] for _, _, d in G.edges(data=True) if index_attr in d}

    for u, v, k, d in G.edges(keys=True, data=True):
        if u in keep and v in keep and index_attr in d:
            edge_attrs = {index_attr: d[index_attr], "hops": 1}
            if store_path:
                edge_attrs["path"] = [u, v]
            H.add_edge(u, v, **edge_attrs)

    for idx in index_values:
        Gi = nx.DiGraph()
        for u, v, d in G.edges(data=True):
            if d.get(index_attr) == idx:
                Gi.add_edge(u, v)

        for src in keep:
            if src not in Gi:
                continue
            blocked = (keep - {src})
            Gi_work = Gi.copy()
            Gi_work.remove_nodes_from([n for n in blocked if n in Gi_work])

            if src not in Gi_work:
                continue

            paths = nx.single_source_shortest_path(Gi_work, src)
            for tgt, path in paths.items():
                if tgt == src or tgt not in keep:
                    continue
                if len(path) == 2 and H.has_edge(src, tgt):
                    continue
                edge_attrs = {index_attr: idx, "hops": len(path)-1}
                if store_path:
                    edge_attrs["path"] = path
                H.add_edge(src, tgt, **edge_attrs)

    return H



def create_ast(policy_dir, opa_ast_path):
    print("docker run --rm -v "+policy_dir+":/policies openpolicyagent/opa:1.8.0-static parse /policies/policy.rego --format=json > "+opa_ast_path)
    subprocess.run(["docker run --rm -v "+policy_dir+":/policies openpolicyagent/opa:1.8.0-static parse /policies/policy.rego --format=json > "+opa_ast_path], shell=True, capture_output=True, text=True)

def load_ast(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
    
def process_node_name(node_name):
    if node_name=='':
        node_name="Null string"
    return str(get_index(node_name))+"& "+str(node_name)

def process_list_name(list_name):
    if isinstance(list_name, list):
        list_names=[]
        for name in list_name:
            if isinstance(name.get("value"), list):
                return True
            list_names.append(str(name.get("value")))
        return '.'.join(list_names)
    elif isinstance(list_name, dict):
        return ''
    else:
        return str(list_name)

def add_node(node_name, G, type=None):
    if not G.has_node(process_node_name(node_name)) and node_name is not None:
        G.add_node(process_node_name(node_name), index=get_index(node_name), type=type)
    return G

def merge_with_list(target_list, index, G):
    start=''
    end=''

    if len(target_list)==2:
        internal_start=process_list_name(target_list[0].get("value"))
        internal_end=process_list_name(target_list[1].get("value"))
        start=internal_start
        end=internal_end
        if internal_start is True:
            start, internal_end, G=merge_with_list(target_list[0].get("value"), index, G)
            G=add_node(internal_end, G)
            G=add_node(end, G)
            G=add_edge_by_refs(internal_end, end, index, ['function_parameter'], G)
        else:
            if isinstance(target_list[0].get("value"), list):
                tmp=start
                start=end
                end=tmp
            G=add_node(start, G)
            G=add_node(end, G)
            G=add_edge_by_refs(start, end, index, ['function_parameter'], G)

    elif len(target_list)==3:
        relations=process_list_name(target_list[0].get("value"))
        internal_start=process_list_name(target_list[1].get("value"))
        internal_end=process_list_name(target_list[2].get("value"))
        start=internal_start
        end=internal_end
        if isinstance(target_list[2].get("value"), dict):
            if target_list[2].get("type") == 'null':
                internal_end='null'
                end=internal_end
            else:
                if len(internal_end)!=0:
                    internal_end=internal_end.get("value")
        
        if target_list[2].get("type") == 'call':
            return start, -1, G
        
        if target_list[1].get("type") == 'call':
            return -1, end, G
        
        if internal_start is True:
            start, internal_start, G=merge_with_list(target_list[1].get("value"), index, G)

        if internal_end is True:
            internal_end, end, G=merge_with_list(target_list[2].get("value"), index, G)
        
        G=add_node(internal_start, G)
        G=add_node(internal_end, G)
        G=add_edge_by_refs(internal_start, internal_end, index, relations, G)
    
    else:
        print("check parameter errors")

    return start, end, G

def process_name_list(name_list):
    if isinstance(name_list, list):
        names=[]
        for name in name_list:
            names.append(name.get("value"))
        return '.'.join(names)
    else:
        return name_list
    
def add_relations(source, end, index, relations, G, nega=False):
    for ref in relations:
        if isinstance(ref, dict):
            G.add_edge(process_node_name(source), process_node_name(end), type=ref.get("type"), label=index, negative=nega)
        else:
            if len(ref)>0:
                G.add_edge(process_node_name(source), process_node_name(end), type=ref, label=index, negative=nega)
    return G

def add_edge_by_refs(source, end, index, relations, G, nega=False):
    if not isinstance(source, list):
        source=[source]
    if not isinstance(end, list):
        end=[end]
    for source_ in source:
        for end_ in end:
            add_relations(source_, end_, index, relations, G, nega=nega)
    return G

def merge_with_body(rule_name, rule_index, body_list, refs, G):
    for target in body_list:
        negative_flag=False
        if "negated" in target.keys():
            negative_flag=True
        target=target.get("terms")
        target_node_name=''
        if isinstance(target, list):
            final_start, final_end, G=merge_with_list(target, rule_index, G)
            if final_start==-1 or final_end==-1:
                continue
            G=add_node(final_start, G)
            G=add_node(rule_name, G)
            G=add_edge_by_refs(rule_name, final_start, rule_index, refs, G, nega=negative_flag)
            rule_name=final_end
        else:
            target_node_name=target.get("value")
            if not target_node_name:
                continue
            if isinstance(target_node_name, dict):
                if "body" in target.keys():
                    target_node_name=process_name_list(target.get("domain").get("value"))
                    G=add_node(target_node_name, G)
                    G=add_node(target.get("value").get("value"), G, type=target.get("value").get("type"))
                    G.add_edge(process_node_name(target_node_name), process_node_name(target.get("value").get("value")), type="loop", label=rule_index)
                    G=merge_with_body(target.get("value").get("value"), rule_index, target.get("body"), '', G)
            else:
                G=add_node(target_node_name, G, type=str(target.get("type")))
            G=add_edge_by_refs(rule_name, target_node_name, rule_index, refs, G, nega=negative_flag)
            rule_name=target_node_name
    return G

def clean_graph(G):
    remove_nodes=[]
    for node in G.nodes():
        if "&" not in node:
            print(node)
            continue
        for filtered_value in filter_values:
            if len(str(node).split("&"))>1 and len(str(node).split("&")[1])>2:
                if filtered_value == str(node).split("&")[1][1:]:
                    remove_nodes.append(node)
        for filtered_value in filter_functions:
            if filtered_value in str(node):
                remove_nodes.append(node)
    for node in remove_nodes:
        G.remove_node(node)

    isolated_nodes = list(nx.isolates(G))
    G.remove_nodes_from(isolated_nodes)
    return G

def get_index(node_name):
    node_name=str(node_name)
    if node_name=='':
        node_name="Null string"
    if node_name not in head_rule_index.keys():
            head_rule_index[node_name]=str(len(head_rule_index.keys()))
    return head_rule_index[node_name]

def extract_rule_calls(module, G):
    rule_name_list=[]
    rules = module.get("rules") or []
    for r in rules:
        head = r.get("head") or {}
        rule_name = str(head.get("name"))
        rule_name_list.append(process_node_name(rule_name))
        if rule_name=="audit_decision" and isinstance(head.get("value").get("value"), list):
            for value in head.get("value").get("value"):
                if len(value)==2:
                    if isinstance(value[1].get("value"),list) and isinstance(value[1].get("value")[0],list):
                        node_name=[]
                        for sub_value in value[1].get("value"):
                            node_name.append(sub_value[1].get("value"))
                            G.add_node(node_name[-1], type=sub_value[1].get("type"), index=get_index(node_name[-1]))
                        G=add_edge_by_refs(node_name, rule_name, get_index(rule_name), ['assign'], G)
                    else:
                        node_name=process_list_name(value[1].get("value"))
                        G.add_node(process_node_name(node_name), type=value[1].get("type"), index=get_index(rule_name))
                        G=add_edge_by_refs(rule_name, node_name, get_index(rule_name), ['assign'], G)
        for filter_name in filter_functions:
            if filter_name in rule_name:
                print(rule_name)
                continue
        if not rule_name:
            continue
        index=get_index(rule_name)
        if str(index) not in index_to_count.keys():
            index_to_count[str(index)]=0
        else:
            index_to_count[str(index)]=index_to_count[str(index)]+1
        head_value = head.get("value")
        node_type = head_value.get("type") if head_value else None
        G.add_node(process_node_name(rule_name), type=node_type, index=get_index(rule_name))
        found_refs = head.get("ref")
        body=r.get("body") or []
        G=merge_with_body(rule_name, str(index)+'.'+str(index_to_count[str(index)]), body, found_refs, G)
    return G, rule_name_list

def serialize_edge_attr(attr):
    try:
        return json.dumps(attr, sort_keys=True)
    except TypeError:
        return repr(attr)

def enumerate_simple_paths_from(G: nx.Graph, src) -> List[List]:
    all_paths: List[List] = []
    def dfs(path: List):
        u = path[-1]
        nxts = [v for v in G.successors(u) if v not in path]
        if not nxts:
            all_paths.append(path[:])
            return
        for v in nxts:
            path.append(v)
            dfs(path)
            path.pop()
    dfs([src])
    return all_paths

def subpaths_of(path: List, min_len: int = 2) -> Iterable[Tuple]:
    n = len(path)
    for i in range(n):
        for j in range(i + min_len, n + 1):
            yield tuple(path[i:j])

def find_first_shared_subpath(G: nx.Graph, min_subpath_len: int = 2) -> Tuple[Tuple, List[Tuple]]:
    for src in G.nodes():
        paths = enumerate_simple_paths_from(G, src)
        if len(paths) < 2:
            continue
        index_by_subpath: Dict[Tuple, Set[int]] = {}
        for pid, p in enumerate(paths):
            for sp in subpaths_of(p, min_len=min_subpath_len):
                s = index_by_subpath.setdefault(sp, set())
                s.add(pid)
                if len(s) >= 2:
                    shared_paths = [tuple(paths[i]) for i in s]
                    return sp, shared_paths

    return None, []

def merge_nodes_with_same_io_and_type(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    H = nx.MultiDiGraph()
    signature_map = defaultdict(list)
    old_to_new = {} 

    for node in G.nodes:
        node_type = G.nodes[node].get('type')
        in_edges = [
            f"{str(src)}|{serialize_edge_attr(data)}"
            for src, _, key, data in G.in_edges(node, keys=True, data=True)
        ]
        out_edges = [
            f"{str(tgt)}|{serialize_edge_attr(data)}"
            for _, tgt, key, data in G.out_edges(node, keys=True, data=True)
        ]
        signature = (
            tuple(sorted(in_edges)),
            tuple(sorted(out_edges)),
            node_type
        )
        signature_map[signature].append(node)

    for group in signature_map.values():
        group = list(group)
        new_node = '+'.join(map(str, group))
        for old in group:
            old_to_new[old] = new_node

    for group in signature_map.values():
        group = list(group)
        new_node = old_to_new[group[0]]  
        merged_attrs = defaultdict(list)
        for n in group:
            for k, v in G.nodes[n].items():
                merged_attrs[k].append(v)
        final_attrs = {}
        for k, v in merged_attrs.items():
            uniq = list(set(map(json.dumps, v)))
            parsed = [json.loads(i) for i in uniq]
            final_attrs[k] = parsed[0] if len(parsed) == 1 else parsed
        final_attrs["fullname"]=new_node
        if new_node.split("+")[0] in G.nodes.keys():
            final_attrs["index"]=G.nodes[new_node.split("+")[0]].get('index')
        else:
            final_attrs["index"]=-1
        H.add_node(new_node, **final_attrs)

    edge_map = defaultdict(list)

    for u, v, key, data in G.edges(keys=True, data=True):
        new_u = old_to_new.get(u)
        new_v = old_to_new.get(v)
        if new_u is None or new_v is None:
            continue  

        edge_map[(new_u, new_v)].append(data)

    for (src, tgt), attr_list in edge_map.items():
        merged_attr = defaultdict(list)
        for attr in attr_list:
            for k, v in attr.items():
                merged_attr[k].append(v)

        final_attr = {
            k: list(set(v)) if len(set(v)) > 1 else v[0]
            for k, v in merged_attr.items()
        }
        H.add_edge(src, tgt, **final_attr)

    return H

def parse_dot_format(graph_path):
    with open(graph_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace('":', '"')
    content=content.replace('\\\\', '\\')
    # content = content.replace('\:"', '\"')
    with open(graph_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("finished correcting dot file format")

def init_graph(opa_ast_path, policy_dir, graph_path, saver=True):
    G=nx.MultiDiGraph(data=True, align='vertical')
    if saver:
        create_ast(policy_dir, opa_ast_path)
    modules = load_ast(opa_ast_path)
    G, _ = extract_rule_calls(modules, G)
    G = merge_nodes_with_same_io_and_type(G)
    G=clean_graph(G)

    if saver:
        nx.nx_pydot.write_dot(G, graph_path)
        parse_dot_format(graph_path)
    return G


def main():
    G = nx.MultiDiGraph(data=True, align='vertical')
    # G, rule_name_list = init_graph(G, "/Users/hailunding/Documents/submit_sre/submit/sre-opa-policies/blue-agent-components/data/ast.json", '/Users/hailunding/Documents/submit_sre/submit/sre-opa-policies/policies', '')
    modules = load_ast("/Users/hailunding/Documents/submit_sre/submit/rebase/sre-opa-policies/resources/data/outputs/ast.json")
    G, rule_name_list = extract_rule_calls(modules, G)
    G=clean_graph(G)
    H = compress_by_constant_index_paths(G, rule_name_list, index_attr="label")
    nx.nx_pydot.write_dot(H, 'tmp.dot')
    parse_dot_format('tmp.dot')

    

if __name__ == "__main__":
    main()
