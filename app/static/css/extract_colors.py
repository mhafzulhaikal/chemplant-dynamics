import os
import re
from collections import defaultdict

color_pattern = re.compile(r'(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\))')
colors = set()

for root, _, files in os.walk(r'C:\process-control\chemplant-dynamics\app\static\css'):
    for f in files:
        if f.endswith('.css'):
            try:
                content = open(os.path.join(root, f), 'r', encoding='utf-8').read()
                for match in color_pattern.findall(content):
                    colors.add((match.lower().strip(), f))
            except Exception as e:
                pass

d = defaultdict(list)
for c, f in colors:
    d[c].append(f)

for c in sorted(d.keys()):
    print(f"{c}: {', '.join(set(d[c]))}")
