## Done

### Generate and visualize graph

- `cd ../../`
- `make opaserver/parse` - Generate json file from policies
- `cd blue_agent_components/visualization`
- `python parse_ast_to_graph.py ast.json` - Extract graph from the json file
- `python parse_graph_to_json.py` - Convert generated graph to a json format
- `python -m http.server 8000` - Start local server to view the webpage
- Check the graph in http://localhost:8000/graph.html

## TBD
- Visualize maps between requirements and policy
