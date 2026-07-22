import json
import os
import re

log_path = r'C:\Users\Administrator\.gemini\antigravity\brain\6f282aec-cd14-4397-9906-cf760464611f\.system_generated\logs\transcript_full.jsonl'
files = {}

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if 'tool_calls' in data:
                for call in data['tool_calls']:
                    func_name = call.get('function', {}).get('name', '')
                    if func_name in ['default_api:write_to_file', 'default_api:replace_file_content', 'default_api:multi_replace_file_content']:
                        args_str = call['function'].get('arguments', '{}')
                        args = json.loads(args_str)
                        path = args.get('TargetFile', '')
                        if 'mobile_ui_src' in path and (path.endswith('.vue') or path.endswith('.js') or path.endswith('.css') or path.endswith('.html')):
                            # If it's a write, store it
                            if func_name == 'default_api:write_to_file':
                                files[path] = args.get('CodeContent', '')
                            # if it's a replace, apply it
                            elif func_name == 'default_api:replace_file_content':
                                if path in files:
                                    target = args.get('TargetContent', '')
                                    replacement = args.get('ReplacementContent', '')
                                    files[path] = files[path].replace(target, replacement)
                            elif func_name == 'default_api:multi_replace_file_content':
                                if path in files:
                                    for chunk in args.get('ReplacementChunks', []):
                                        target = chunk.get('TargetContent', '')
                                        replacement = chunk.get('ReplacementContent', '')
                                        files[path] = files[path].replace(target, replacement)
        except Exception as e:
            pass

for path, content in files.items():
    print(f'Restoring {path}')
    content = content.replace('href="/icons.svg#', 'href="icons.svg#')
    content = content.replace(':href="`/icons.svg#', ':href="`icons.svg#')
    with open(path, 'w', encoding='utf-8') as out:
        out.write(content)
