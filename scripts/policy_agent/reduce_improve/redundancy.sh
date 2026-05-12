# !/bin/bash
cd ../../
make opaserver/parse
cd ./blue-agent-components/reduce_improve 
mv ../../ast.json ./
python parse_ast_to_graph.py ast.json
python ../../scripts/parse_dot_file_format.py ast.dot
python detect_redundancy.py > graph_redundancy.txt
