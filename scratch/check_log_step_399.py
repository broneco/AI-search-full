import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            if step.get("step_index") == 399:
                with open("scratch/raw_step_399.json", 'w', encoding='utf-8') as outf:
                    json.dump(step, outf, indent=2)
                print("Dumped raw step 399 JSON to scratch/raw_step_399.json")
        except Exception as e:
            print(f"Error: {e}")
