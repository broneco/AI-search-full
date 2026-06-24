import json
import os
import difflib

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"
target_file_path = r"c:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend\app\page.tsx"

import subprocess
subprocess.run(["git", "checkout", target_file_path])

# Replay up to step 264
with open("scratch/restore_fuzzy.py", 'r', encoding='utf-8') as f:
    restore_code = f.read()

restore_code_265 = restore_code.replace("step_idx >= 511", "step_idx >= 265")
with open("scratch/restore_265.py", 'w', encoding='utf-8') as f:
    f.write(restore_code_265)

subprocess.run(["python", "scratch/restore_265.py"])

with open(target_file_path, 'r', encoding='utf-8') as f:
    content_265 = f.read()

output_lines = []

# Now find step 399 target
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            if step.get("step_index") == 399:
                tc = step.get("tool_calls", [])[0]
                target_str = tc["args"]["TargetContent"]
                
                output_lines.append(f"Step 399 Target Content Length: {len(target_str)}")
                start_marker = "const TRANSLATIONS = {"
                idx = content_265.find(start_marker)
                if idx != -1:
                    snippet = content_265[idx:idx + len(target_str)]
                    output_lines.append(f"Snippet in page.tsx at TRANSLATIONS length: {len(snippet)}")
                    
                    # Compare char by char
                    output_lines.append("Comparing characters:")
                    for i in range(min(len(target_str), len(snippet))):
                        tc_char = target_str[i]
                        sn_char = snippet[i]
                        if tc_char != sn_char:
                            output_lines.append(f"Diff at index {i}: Target={repr(tc_char)} (ord {ord(tc_char)}) vs Snippet={repr(sn_char)} (ord {ord(sn_char)})")
                else:
                    output_lines.append("TRANSLATIONS not found in content_265!")
        except Exception as e:
            output_lines.append(f"Error: {e}")

with open("scratch/debug_fuzzy_output.txt", 'w', encoding='utf-8') as f:
    f.write("\n".join(output_lines))
print("Done. Diagnostic output written to scratch/debug_fuzzy_output.txt")
