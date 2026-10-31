## Original run
1. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 1 --save-artifacts /your-save-path/baseline/employee/step1
- Q1 table (the first two column). 
2. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 2 --no-clean --resume last --carry last --save-artifacts /your-save-path/baseline/employee/step2
- Table in Q2
3. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 3 --no-clean --resume last --carry last --save-artifacts /your-save-path/baseline/employee/step3
- Table in Q3 (The first two columns)
4. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 4 --no-clean --resume last --carry last --save-artifacts /your-save-path/baseline/employee/step4
5. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 5 --no-clean --resume last --carry last --save-artifacts /your-save-path/baseline/employee/step5
- table in Q3 (4-5th columns)
6. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 4 --no-clean --resume last --carry last --save-artifacts /your-save-path/baseline/employee/step5-after-test
- Table in Q1 (4-9th columns)
7. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 6 --no-clean --resume last --carry last --save-artifacts /your-save-path/baseline/employee/step6
- Table1 in Q4
8. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 7 --no-clean --resume last --carry last --save-artifacts /your-save-path/baseline/employee/step7
- Table2 in Q4
9. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 8 --no-clean --resume last --carry last --save-artifacts /your-save-path/baseline/employee/step8
- Table2 in Q4
10. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 9 --no-clean --resume last --carry last --save-artifacts /your-save-path/baseline/employee/step9
- Table in Q6

## Defect parts
1. (optional) python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 10 --no-clean --save-artifacts /your-save-path/baseline/employee/step10_defect
- Table2 in Q7
2. Overwrite policy with defected policy
- cp examples/employee/smith/policy_defect.rego ./assets/policy.rego 
3. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 6 --no-clean --save-artifacts /your-save-path/baseline/employee/step6_defect
- Table2 in Q7
4. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 7 --no-clean --resume last --save-artifacts /your-save-path/baseline/employee/step7_defect
- Table2 in Q7
5. python3 .claude/skills/smith/tests/run_smith_pipeline.py --model aws/claude-sonnet-5 -e employee -s 8 --no-clean --resume last --save-artifacts /your-save-path/baseline/employee/step8_defect
- Table2 in Q7