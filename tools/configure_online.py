"""Set the public account-service endpoint in a client build, without credentials."""
import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse


def configure(url, project):
    url = url.strip().rstrip('/')
    parsed = urlparse(url)
    if any(ord(character) < 33 for character in url):
        raise ValueError('The service origin cannot contain whitespace or control characters.')
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('The service origin has an invalid port.')
    local = parsed.hostname in ('127.0.0.1','localhost','::1')
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path or (parsed.scheme != 'https' and not (local and parsed.scheme == 'http')):
        raise ValueError('Use an HTTPS service origin without credentials, path or query; HTTP is allowed only on loopback.')
    text = project.read_text(encoding='utf-8')
    entry = 'services/api_url='+json.dumps(url)+'\n'
    section = re.search(r'^\[network\]\s*\n(.*?)(?=^\[|\Z)',text,re.M|re.S)
    if section:
        contents = re.sub(r'^services/api_url=.*\n?', '', section[1], flags=re.M)
        text = text[:section.start(1)]+entry+contents+text[section.end(1):]
    else:
        text = text.rstrip()+'\n\n[network]\n\n'+entry
    project.write_text(text,encoding='utf-8',newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default=os.getenv('KYLR_PUBLIC_API_URL',''))
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1]/'game'/'project.godot')
    args = parser.parse_args()
    if not args.url:
        parser.error('Supply --url or KYLR_PUBLIC_API_URL.')
    try: configure(args.url,args.project)
    except ValueError as error: parser.error(str(error))
    print('Public account-service endpoint configured.')


if __name__ == '__main__': main()
