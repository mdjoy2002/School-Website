from pathlib import Path
text = Path('tmp_admin_post_debug_out.txt').read_text(encoding='utf-8', errors='ignore')
start = text.lower().find('error')
if start != -1:
    print(text[start:start+10000])
else:
    print(text[:10000])
