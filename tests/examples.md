1. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 1 --save-artifacts your_path_to_save/RagChatbot_MCPServer/step1
- Count auto fix
2. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 2 --no-clean --resume last --carry last --save-artifacts your_path_to_save/RagChatbot_MCPServer/step2
- Table in Q2
3. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 3 --no-clean --resume last --carry last --save-artifacts your_path_to_save/RagChatbot_MCPServer/step3
- Part of table in Q3
4. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 5 --no-clean --resume last --carry last --save-artifacts your_path_to_save/RagChatbot_MCPServer/step5
- table in Q3
5. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 4 --no-clean --resume last --carry last --save-artifacts your_path_to_save/RagChatbot_MCPServer/step4
- Table in Q1
6. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 6 --no-clean --resume last --carry last --save-artifacts your_path_to_save/RagChatbot_MCPServer/step6
- Table1 in Q4-1
7. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 7 --no-clean --resume last --carry last --save-artifacts your_path_to_save/RagChatbot_MCPServer/step7
- Table2 in Q4-1
8. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 8 --no-clean --resume last --carry last --save-artifacts your_path_to_save/RagChatbot_MCPServer/step8
- Table2 in Q4-1
9. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 10 --no-clean --resume last --carry last --save-artifacts your_path_to_save/RagChatbot_MCPServer/step10
- Table in Q6


1. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 11 --no-clean --save-artifacts your_path_to_save/RagChatbot_MCPServer/step11_defect
- Table2 in Q4-2
2. move defected policy (skip for RagChatbot_MCPServer example)
- cp examples/RagChatbot_MCPServer/smith/smith_outputs/policy_defect.rego ./assets/policy.rego 
3. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 6 --no-clean --save-artifacts your_path_to_save/RagChatbot_MCPServer/step6_defect
- Table2 in Q4-2
4. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 7 --no-clean --resume last --save-artifacts your_path_to_save/RagChatbot_MCPServer/step7_defect
- Table2 in Q4-2
5. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e RagChatbot_MCPServer -s 8 --no-clean --resume last --save-artifacts your_path_to_save/RagChatbot_MCPServer/step8_defect
- Table2 in Q4-2