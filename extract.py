import json
log_path = r'C:\Users\Uday\.gemini\antigravity-ide\brain\c025b064-bcc6-4248-90fc-ff016047cd42\.system_generated\logs\transcript_full.jsonl'
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line.strip())
        if data.get('step_index') in [1121, 1127, 1130, 1072, 1002]:
            if 'tool_calls' in data:
                for call in data['tool_calls']:
                    args = call.get('arguments', {})
                    print(f"STEP {data['step_index']} - {call['name']}: {args.get('TargetFile')}")
                    if 'ReplacementChunks' in args:
                        for chunk in args['ReplacementChunks']:
                            print(chunk.get('ReplacementContent'))
