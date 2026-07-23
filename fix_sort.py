import re

filepath = 'c:/chips-portal/app/templates/report/upload.html'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'let targetIdx = headers\.findIndex\(th => th\.innerText\.trim\(\)\.toLowerCase\(\)\.includes\(\'total pending\'\)\);', 
              r'''let targetIdx = headers.findIndex(th => {
            let txt = th.innerText.trim().toLowerCase();
            return txt.includes('total pending') || txt.includes('pending total');
        });''', text)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)
print("done")
