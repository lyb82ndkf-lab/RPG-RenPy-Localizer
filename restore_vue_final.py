import json
import os

log_path = r'C:\Users\Administrator\.gemini\antigravity\brain\6f282aec-cd14-4397-9906-cf760464611f\.system_generated\logs\transcript_full.jsonl'
files = {}

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if 'tool_calls' in data:
                for call in data['tool_calls']:
                    func_name = call.get('name', '')
                    if func_name == 'write_to_file':
                        args = call.get('args', {})
                        path = args.get('TargetFile', '')
                        if 'mobile_ui_src' in path and (path.endswith('.vue') or path.endswith('.js') or path.endswith('.html') or path.endswith('.css')):
                            files[path] = args.get('CodeContent', '')
        except Exception as e:
            pass

for path, content in files.items():
    print(f'Restoring {path}')
    content = content.replace('href="/icons.svg#', 'href="icons.svg#')
    content = content.replace(':href="`/icons.svg#', ':href="`icons.svg#')
    with open(path, 'w', encoding='utf-8') as out:
        out.write(content)
