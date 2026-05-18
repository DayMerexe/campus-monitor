import re

with open(r'C:\Users\DayMer\Downloads\王晓辉论文(设计)模板.doc', 'rb') as f:
    data = f.read()

text = data.decode('gbk', errors='ignore')

# Decode \'xx escapes
def unescape(m):
    return chr(int(m.group(1), 16))

text = re.sub(r"\\'([0-9a-fA-F]{2})", unescape, text)

# Write decoded to file
with open(r'F:\bishe\tmp_template.txt', 'w', encoding='utf-8') as f:
    f.write(text)

print(f"Written {len(text)} chars")
