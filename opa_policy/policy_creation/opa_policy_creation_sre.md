## Details steps:

Run the following prompts one by one, step by step. After each prompt, you must ask human if they agree with your understanding. If they don't, think it again and take human suggestions to generate new response until human agree.

IMPORTANT: BEFORE YOU SEARCH ANY DOCUMENT, measure the size of the document. If it is too large (i.e., >100000), summarize them to around 100000 characters first.

## Step 1: 

Understand and create a comprehensive list of unambiguous requirements that define the specification of the SRE agent application maintained in the following code repo, read it online, do not clone or download it. Do not fetch it from api.github or rawgithub weisites, you should fetch it from github.com:
* https://github.com/itbench-hub/ITBench-SRE-Agent.git

As additional background, the authors have written a paper describing benchmark scenarios for a few agents, including this SRE agent:
* https://arxiv.org/abs/2502.05352

Specific benchmark scenarios for the SRE agent can be found here:
* https://github.com/itbench-hub/ITBench-Scenarios/blob/main/sre/docs/incident_scenarios.md

## Step 2: 
Unpack and mine security requirements (think of them as access control requirements) for the nl2kubctl tool. Specifically, I want these requirements to capture what actions against a k8s cluster should the SRE agent be allowed to execute, and which actions should be blocked or solicit human approval.

Unit of Analysis: The unit of analysis is the nl2kubectl tool of an agentic application that specializes in site realiability engineering (SRE) tasks for k8s.

When designing access control policies for the nl2kubectl tool, use the following main decision points:
allow: Commands that pass all security checks and can execute automatically
requires approval: Commands that need human approval before execution
deny: Commands that are always forbidden regardless of context
Based on the above decision points, adopt the following command classification framework:
safe: Read-only commands (get, describe, logs, top) - allow
restricted: Modification commands (apply, patch, exec) - requires approval
forbidden: Dangerous commands (delete resources, RBAC changes) - deny

Authoritative Knowledge Sources and Guides for k8s Security References you can use (only search necessary documents):
https://kubernetes.io/docs/concepts/configuration/secret/
https://cheatsheetseries.owasp.org/cheatsheets/Kubernetes_Security_Cheat_Sheet.html
https://media.defense.gov/2022/Aug/29/2003066362/-1/-1/0/CTR_KUBERNETES_HARDENING_GUIDANCE_1.2_20220829.PDF
https://www.squadcast.com/blog/kubernetes-operators-for-automated-sre#overview
https://kubernetes.io/docs/tasks/administer-cluster/securing-a-cluster/
https://duplocloud.com/blog/3-proven-methods-for-automating-kubernetes-security-compliance/
https://kubernetes.io/docs/reference/access-authn-authz/rbac/
https://kubernetes.io/docs/concepts/security/rbac-good-practices/
https://gcore.com/blog/k8s-rbac-permissions
https://thenewstack.io/kubernetes-rbac-permissions-you-might-not-know-about-but-should/
https://www.armosec.io/blog/a-guide-for-using-kubernetes-rbac/

## Step 3:
Excellent. Now, assuming that you can fully mediate the execution of these kubectl commands with the aid of an OPA (open policy agent) engine that can be used to allow commands, create a comprehensive OPA policy in rego that captures the security requirements for the nl2kubectl tool. 

**You should read a command example `assets/opa/inputs/processed_command_example.json` to understand the processed command format.** 

For example, when refering a variable 'verb' in policy, you should use input.command.verb if you follow the command format. The policy always starts with "package kubectl.policy.allow".

## Step 4:
Save the policy as ./assets/policy.rego. After saving the policy, run command
`opa fmt` to see if there is compile errors and fix errors until the policy can be run. 

## Step 5:
Then run `smith --flag policy_testing` to get comphehensive results. Notice that if you find the test case numbers are 0 or less than 10, your policy has a format issue, you should read command example resources/data/inputs/processed_command_example.json to revise your policy. 

Ignore the failed test cases, only focus on compile and format errors.






