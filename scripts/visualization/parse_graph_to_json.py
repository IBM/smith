import pydot
import json

graphs = pydot.graph_from_dot_file("ast.dot")
graph = graphs[0]

nodes = []
edges = []


def parse(index):
    if not index:
        print("skipping")
        print(index)
        return -1
    if "[" in index and "]" in index:
        print(index[2:-2].replace("'", ""))
        return index[2:-2].replace("'", "")
    return index


for node in graph.get_nodes():
    if node.get_name() not in ("node", "graph", "edge"):
        node_id = node.get_name()
        index = node.get("index")
        nodes.append({"data": {"id": node_id, "index": index}})

for edge in graph.get_edges():
    source = edge.get_source()
    target = edge.get_destination()
    index = edge.get("label")
    edges.append(
        {
            "data": {
                "id": f"{source}_{target}",
                "source": source,
                "target": target,
                "index": parse(index),
            }
        }
    )

with open("graph.json", "w") as f:
    json.dump({"nodes": nodes, "edges": edges}, f, indent=2)
