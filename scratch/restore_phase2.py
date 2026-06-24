import json
import os
import re

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"
target_file_path = r"c:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend\app\page.tsx"

print("Reverting page.tsx to clean checkout state...")
os.system(f'git checkout "{target_file_path}"')

# Read original file contents (which has Phase 1 committed already)
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

def make_fuzzy_regex(target_str):
    pattern_parts = []
    for char in target_str:
        if ord(char) > 127 or char == '':
            pattern_parts.append('.')
        else:
            pattern_parts.append(re.escape(char))
    return "".join(pattern_parts)

def fuzzy_replace(content, target_str, replacement_str):
    if target_str in content:
        return content.replace(target_str, replacement_str), True
        
    # Build regex pattern
    pattern = make_fuzzy_regex(target_str)
    match = re.search(pattern, content)
    if match:
        start, end = match.span()
        new_content = content[:start] + replacement_str + content[end:]
        return new_content, True
    return content, False

print("Replaying edits from step 399 onwards...")
for step in steps:
    step_idx = step.get("step_index", 0)
    if step_idx < 399 or step_idx >= 511:
        continue
        
    tool_calls = step.get("tool_calls", [])
    for tc in tool_calls:
        name = tc.get("name")
        args = tc.get("args", {})
        target = args.get("TargetFile") or args.get("AbsolutePath")
        if target and "page.tsx" in target:
            if name == "write_to_file" and args.get("Overwrite"):
                print(f"Step {step_idx}: overwriting page.tsx")
                content = args.get("CodeContent")
            elif name == "replace_file_content":
                target_str = args.get("TargetContent")
                replace_str = args.get("ReplacementContent")
                content, success = fuzzy_replace(content, target_str, replace_str)
                if success:
                    print(f"Step {step_idx}: replaced content successfully (fuzzy)")
                else:
                    print(f"Step {step_idx}: WARNING - TargetContent not found even with fuzzy matching!")
            elif name == "multi_replace_file_content":
                chunks = args.get("ReplacementChunks", [])
                print(f"Step {step_idx}: multi-replacing {len(chunks)} chunks")
                for i, chunk in enumerate(chunks):
                    target_str = chunk.get("TargetContent")
                    replace_str = chunk.get("ReplacementContent")
                    content, success = fuzzy_replace(content, target_str, replace_str)
                    if success:
                        print(f"  Chunk {i}: replaced (fuzzy)")
                    else:
                        print(f"  Chunk {i}: WARNING - target not found!")

# Write the reconstructed page.tsx content
with open(target_file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Restored page.tsx size: {len(content)} chars, lines: {len(content.splitlines())}")
