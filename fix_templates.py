import os, glob
paths = glob.glob('app/templates/**/*.html', recursive=True)
count = 0
for p in paths:
    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()
    if '<option value="month" selected>This Month</option>' in content:
        content = content.replace('<option value="month" selected>This Month</option>', '<option value="month">This Month</option>')
        content = content.replace('<option value="all">All Time</option>', '<option value="all" selected>All Time</option>')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)
        count += 1
print(f'Fixed {count} files')
