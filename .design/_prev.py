import pathlib
import re
import subprocess
import sys

OUT = pathlib.Path('/tmp/claude-1000/-home-rafael-Documents-GitHub-Comeni-Labs/9d6cd1fa-c2d6-4749-abe3-6862ce86bbd2/scratchpad/prev')
OUT.mkdir(parents=True, exist_ok=True)
names = sys.argv[1:] or [p.stem.replace('.dc','') for p in pathlib.Path('.').glob('Run*.dc.html')]
for n in names:
    h = pathlib.Path(f'{n}.dc.html').read_text()
    h = h.replace('{{ t.sans }}', '"Geist", system-ui, sans-serif').replace('{{ t.mono }}', '"Geist Mono", ui-monospace, monospace')
    h = re.sub(r'<script src="\./support\.js"></script>', '', h)
    h = re.sub(r'<script data-dc-script.*?</script>', '', h, flags=re.S)
    h = h.replace('<x-dc>', '').replace('<helmet>', '').replace('</helmet>', '')
    (OUT / f'{n}.html').write_text(h)
    m = re.search(r'min-height:(\d+)px', h)
    hh = int(m.group(1)) if m else 1400
    subprocess.run(['google-chrome-stable','--headless','--disable-gpu','--no-sandbox',
                    '--hide-scrollbars','--virtual-time-budget=4000',
                    f'--window-size=1400,{hh}', f'--screenshot={OUT}/{n}.png',
                    f'file://{OUT}/{n}.html'], capture_output=True)
    print('shot', n, hh)
