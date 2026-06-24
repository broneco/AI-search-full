import json
import os
import re

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"
target_file_path = r"c:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend\app\page.tsx"

# Revert to clean check out
os.system(f'git checkout "{target_file_path}"')

# Read clean file
with open(target_file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Load steps
steps = []
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            steps.append(step)
        except Exception:
            pass

steps.sort(key=lambda s: s.get("step_index", 0))

def fuzzy_replace(content, target_str, replacement_str):
    if target_str in content:
        return content.replace(target_str, replacement_str), True
    
    # regex fuzzy search
    pattern_parts = []
    for char in target_str:
        if ord(char) > 127 or char == '':
            pattern_parts.append('.')
        else:
            pattern_parts.append(re.escape(char))
    pattern = "".join(pattern_parts)
    match = re.search(pattern, content)
    if match:
        start, end = match.span()
        return content[:start] + replacement_str + content[end:], True
    return content, False

print("Replaying edits up to step 398...")
for step in steps:
    step_idx = step.get("step_index", 0)
    if step_idx >= 399:
        continue
    tool_calls = step.get("tool_calls", [])
    for tc in tool_calls:
        name = tc.get("name")
        args = tc.get("args", {})
        target = args.get("TargetFile") or args.get("AbsolutePath")
        if target and "page.tsx" in target:
            if name == "write_to_file" and args.get("Overwrite"):
                content = args.get("CodeContent")
            elif name == "replace_file_content":
                target_str = args.get("TargetContent")
                replace_str = args.get("ReplacementContent")
                content, success = fuzzy_replace(content, target_str, replace_str)
                if not success:
                    print(f"Failed to apply Step {step_idx}")

# Write file at step 398
with open("scratch/page_at_398.tsx", 'w', encoding='utf-8') as f:
    f.write(content)

# Now load Step 399 target
for step in steps:
    if step.get("step_index") == 399:
        tc = step.get("tool_calls", [])[0]
        target_399 = tc["args"]["TargetContent"]
        
        print(f"Step 399 target len: {len(target_399)}")
        print(f"Is target_399 in page_at_398? {target_399 in content}")
        if target_399 not in content:
            # Let's see if we can find where they mismatch
            # Let's search for the first line of target_399 in content
            first_line = target_399.splitlines()[0]
            print(f"First line: {repr(first_line)}")
            idx = content.find(first_line)
            print(f"First line index in page_at_398: {idx}")
            if idx != -1:
                snippet = content[idx:idx + len(target_399)]
                print(f"Snippet at index len: {len(snippet)}")
                with open("scratch/compare_398_399.txt", 'w', encoding='utf-8') as outf:
                    outf.write("=== TARGET 399 ===\n")
                    outf.write(target_399)
                    outf.write("\n\n=== SNIPPET 398 ===\n")
                    outf.write(snippet)
                print("Written comparison to scratch/compare_398_399.txt")
