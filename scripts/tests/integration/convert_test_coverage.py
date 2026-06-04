import json
import re
import os
from dotenv import load_dotenv
load_dotenv()

base_url=os.getenv("BASE_URL")

policy_dir=base_url+os.getenv("POLICY_DIR")
policy_path = policy_dir+os.getenv("POLICY_PATH")
test_path=base_url+'scripts/tests/integration/'
file_path=test_path+'coverage/revised_policy.rego'
test_file_path=test_path+'coverage/policy_test.rego'
tn_command_path=test_path+'tn.txt'
tp_command_path=test_path+'tp.txt'

def replace_quotes_in_json(obj, old_char="'", new_char='"'):
    if 'command' not in obj.keys():
        return obj
    for k in obj['command'].keys():
        if isinstance(obj['command'][k], str):
            obj['command'][k]=obj['command'][k].replace(old_char, new_char)
        elif isinstance(obj['command'][k], list):
            for k_index in range(len(obj['command'][k])):
                if isinstance(obj['command'][k][k_index], str):
                    obj['command'][k][k_index]=obj['command'][k][k_index].replace(old_char, new_char)
                elif isinstance(obj['command'][k][k_index], dict):
                    for kk in obj['command'][k][k_index].keys():
                        if isinstance(obj['command'][k][k_index][kk], str):
                            obj['command'][k][k_index][kk]=obj['command'][k][k_index][kk].replace(old_char, new_char)
                        else:
                            obj['command'][k][k_index][kk]='null'
                else:
                    obj['command'][k][k_index]='null'

        else:
            obj['command'][k]='null'
    obj['original_command']=obj['original_command'].replace(old_char, new_char)

    return str(obj)


def fix_package_line(file_path, new_package="policy"):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = r"(?m)^package\s+[a-zA-Z0-9_.]+"
    new_content = re.sub(pattern, f"package {new_package}", content, count=1)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"[OK] Updated package in {file_path}")

def collect_test_functions(content):
    pattern = r"(?m)^\s*(test_[A-Za-z0-9_]*)\s*(\(|\{|=|if\b)"
    names = set()
    for m in re.finditer(pattern, content):
        name = m.group(1)
        names.add(name)
    return sorted(names)


def build_rename_map(names, new_prefix="_test_"):
    rename_map = {}
    for name in names:
        suffix = name[len("test_"):]  
        new_name = f"{new_prefix}{suffix}"
        rename_map[name] = new_name
    return rename_map


def apply_renames(content, rename_map):
    for old, new in rename_map.items():
        pattern = r"\b" + re.escape(old) + r"\b"
        content = re.sub(pattern, new, content)
    return content


def process_file(policy_path, file_path, new_prefix="_test_"):
    with open(policy_path, "r", encoding="utf-8") as f:
        content = f.read()
    names = collect_test_functions(content)
    if not names:
        print(f"[INFO] No test_* functions found in {file_path}")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return

    print(f"[INFO] Found in {file_path}:")
    for n in names:
        print(f"   - {n}")

    rename_map = build_rename_map(names, new_prefix=new_prefix)

    print("[INFO] Rename map:")
    for old, new in rename_map.items():
        print(f"   {old}  ->  {new}")
    new_content = apply_renames(content, rename_map)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[OK] Updated {file_path}\n")

process_file(policy_path, file_path)
fix_package_line(file_path)

final_results=[]
final_results.append("package policy_test")
final_results.append("import data.policy")

def read_files(file_path):
    with open(file_path, 'r') as f:
        lines=f.readlines()
    lines=[line.strip() for line in lines]
    return lines

def try_parse_rego_json(content):
    """Validate that content is parseable as JSON. If not, return None."""
    try:
        json.loads(content)
        return content
    except (json.JSONDecodeError, ValueError):
        return None

index=1
for bad_test_file in read_files(tp_command_path):
    middle=[]
    with open(bad_test_file, 'r') as file:
        data = json.load(file)
    middle.append('test_not_allow_'+str(index)+' if {')
    content=str(replace_quotes_in_json(data['input']))
    content=content.replace('"', '\\"')
    content=content.replace("'",'"')
    content=content.replace('"null"','null')
    if try_parse_rego_json(content) is None:
        content = json.dumps(data['input'], ensure_ascii=False)
    middle.append("    not policy.allow with input as "+content)
    middle.append('}')
    final_results.append("\n".join(middle))
    index=index+1

index=1
for benign_test_file in read_files(tn_command_path):
    middle=[]
    with open(benign_test_file, 'r') as file:
        data = json.load(file)
    middle.append('test_allow_'+str(index)+' if {')
    content=str(replace_quotes_in_json(data['input']))
    content=content.replace('"', '\\"')
    content=content.replace("'",'"')
    content=content.replace('"null"','null')
    if try_parse_rego_json(content) is None:
        content = json.dumps(data['input'], ensure_ascii=False)
    middle.append("    policy.allow with input as "+content)
    middle.append('}')
    final_results.append("\n".join(middle))
    index=index+1

with open(test_file_path, 'w') as file:
    file.write('\n\n'.join(final_results))
