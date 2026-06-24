import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            if step.get("step_index") == 163:
                tc = step.get("tool_calls", [])[0]
                args = tc["args"]
                content = args.get('ReplacementContent', '')
                with open("scratch/dump_163.txt", 'w', encoding='utf-8') as outf:
                    outf.write(content)
                print("Dumped step 163 replacement content to scratch/dump_163.txt")
        except Exception as e:
            print(f"Error: {e}")
