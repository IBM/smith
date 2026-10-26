1. python3 .claude/skills/smith/tests/run_smith_pipeline.py -e call-for-papers-mcp -s 1 --save-artifacts ./baseline/call-for-papers-mcp/step1
- Count auto fix
2. python3 .claude/skills/smith/tests/run_smith_pipeline.py -e call-for-papers-mcp -s 2 --no-clean --resume last --carry last --save-artifacts your-save-path/call-for-papers-mcp/step2
- Table in Q2
3. python3 .claude/skills/smith/tests/run_smith_pipeline.py -e call-for-papers-mcp -s 3 --no-clean --resume last --carry last --save-artifacts your-save-path/call-for-papers-mcp/step3
- Part of table in Q3
4. python3 .claude/skills/smith/tests/run_smith_pipeline.py -e call-for-papers-mcp -s 5 --no-clean --resume last --carry last --save-artifacts your-save-path/call-for-papers-mcp/step5
- table in Q3
5. python3 .claude/skills/smith/tests/run_smith_pipeline.py -e call-for-papers-mcp -s 4 --no-clean --resume last --carry last --save-artifacts your-save-path/call-for-papers-mcp/step4
- Table in Q1
6. move defected policy
- cp examples/call-for-papers-mcp/smith/smith_outputs/policy_defect.rego ./assets/policy.rego 
7. python3 .claude/skills/smith/tests/run_smith_pipeline.py -e call-for-papers-mcp -s 6 --no-clean --resume last --carry last --save-artifacts your-save-path/call-for-papers-mcp/step6
- Table1 in Q4
8. python3 .claude/skills/smith/tests/run_smith_pipeline.py -e call-for-papers-mcp -s 7 --no-clean --resume last --carry last --save-artifacts your-save-path/call-for-papers-mcp/step7
- Table2 in Q4
9. python3 .claude/skills/smith/tests/run_smith_pipeline.py -e call-for-papers-mcp -s 10 --no-clean --resume last --carry last --save-artifacts your-save-path/call-for-papers-mcp/step10
- Table in Q6