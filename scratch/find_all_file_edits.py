import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

edits = []
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            step_idx = step.get("step_index", 0)
            tool_calls = step.get("tool_calls", [])
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                if name in ("write_to_file", "replace_file_content", "multi_replace_file_content"):
                    target = args.get("TargetFile") or args.get("AbsolutePath")
                    edits.append(f"Step {step_idx}: {name} targeting {target}")
        except Exception as e:
            pass

with open("scratch/all_file_edits.txt", 'w', encoding='utf-8') as f:
    f.write("\n".join(edits))
print(f"Done. Wrote {len(edits)} edits to scratch/all_file_edits.txt")
