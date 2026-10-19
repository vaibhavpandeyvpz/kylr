"""Generate the English UI translation template, retaining source references."""
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LITERAL=r'"(?:\\.|[^"\\])*"'
CALL=re.compile(r'\b(?:label|button|toggle|setting_choice|field|translate)\((?:[^,\n]+,\s*)?('+LITERAL+')')

def main():
    entries={}
    for path in sorted((ROOT/'scripts').rglob('*.gd')):
        if 'ui' not in path.parts and path.name!='tutorial.gd': continue
        source=path.read_text(encoding='utf-8')
        for match in CALL.finditer(source):
            text=json.loads(match[1])
            if not text or text.startswith('res://'): continue
            reference=f'{path.relative_to(ROOT).as_posix()}:{source.count(chr(10),0,match.start())+1}'
            entries.setdefault(text,[]).append(reference)
    output=['# KYLR UI translation template.', '# Dynamic score/name values stay outside translated labels.', 'msgid ""', 'msgstr ""', '"Content-Type: text/plain; charset=UTF-8\\n"', '"Language: en\\n"', '']
    for text, references in sorted(entries.items()):
        output.extend(['#: '+' '.join(references),'msgid '+json.dumps(text,ensure_ascii=False),'msgstr ""',''])
    target=ROOT/'data'/'localization'/'ui.pot'
    target.parent.mkdir(exist_ok=True)
    target.write_text('\n'.join(output),encoding='utf-8')
    print(f'{len(entries)} translatable UI strings')

if __name__=='__main__': main()
