import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"
target_file_path = r"c:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\WIP - AI Search Full\frontend\app\page.tsx"

with open("scratch/restore_265.py", 'r', encoding='utf-8') as f:
    restore_code = f.read()

import subprocess
subprocess.run(["git", "checkout", target_file_path])
subprocess.run(["python", "scratch/restore_265.py"])

with open(target_file_path, 'r', encoding='utf-8') as f:
    content_265 = f.read()

# Find step 399 target
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            if step.get("step_index") == 399:
                tc = step.get("tool_calls", [])[0]
                target_str = tc["args"]["TargetContent"]
                
                start_marker = "const TRANSLATIONS = {"
                idx = content_265.find(start_marker)
                if idx != -1:
                    snippet = content_265[idx:idx + len(target_str)]
                    
                    with open("scratch/diff_context.txt", 'w', encoding='utf-8') as outf:
                        outf.write("=== TARGET CONTENT FROM INDEX 3000 TO 3200 ===\n")
                        outf.write(target_str[3000:3200])
                        outf.write("\n\n=== SNIPPET CONTENT FROM INDEX 3000 TO 3200 ===\n")
                        outf.write(snippet[3000:3200])
                else:
                    print("TRANSLATIONS not found!")
        except Exception as e:
            print(f"Error: {e}")
