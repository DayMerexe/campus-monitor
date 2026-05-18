import re

with open(r'C:\Users\DayMer\Downloads\王晓辉论文(设计)模板.doc', 'rb') as f:
    data = f.read()

# Simple approach: just collect all \'xx hex bytes and convert to GBK
# Everything else that's ASCII we keep
out = bytearray()
i = 0
while i < len(data):
    if data[i] == 0x5c and i+3 < len(data) and data[i+1] == 0x27:
        out.append(int(bytes([data[i+2], data[i+3]]), 16))
        i += 4
        continue
    elif data[i] == 0x7b:  # {
        out.extend(b'\n{')
    elif data[i] == 0x7d:  # }
        out.extend(b'}\n')
    elif data[i] >= 0x20 and data[i] < 0x7f:
        out.append(data[i])
    i += 1

text = out.decode('gbk', errors='ignore')

# Strip all RTF groups (content between { and })
def strip_rtf(s):
    result = []
    depth = 0
    i = 0
    while i < len(s):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
        elif depth == 0:
            result.append(s[i])
        i += 1
    return ''.join(result)

# Get text only at depth 0 (outside RTF groups)
plain = strip_rtf(text)

# Remove control words
plain = re.sub(r'\\[a-zA-Z]+\d*\s?', '', plain)
plain = re.sub(r'[\\;]', '', plain)
plain = re.sub(r'\n{3,}', '\n\n', plain)
plain = re.sub(r'[ \t]{3,}', '  ', plain)

# Find lines with Chinese
lines = [l.strip() for l in plain.split('\n') if l.strip()]
for line in lines[:100]:
    if any('一' <= c <= '鿿' for c in line):
        print(line)
