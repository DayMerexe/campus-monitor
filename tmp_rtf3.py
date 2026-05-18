import re, sys

with open(r'C:\Users\DayMer\Downloads\王晓辉论文(设计)模板.doc', 'rb') as f:
    data = f.read()

# Build a byte buffer: for ASCII bytes pass through, for \'xx convert to actual byte
result = bytearray()
i = 0
while i < len(data):
    b = data[i]
    if b == 0x5c and i+3 < len(data) and data[i+1] == 0x27:  # \'
        hex_byte = bytes([data[i+2], data[i+3]])
        result.append(int(hex_byte, 16))
        i += 4
        continue
    elif b < 0x80:
        result.append(b)
    i += 1

# Now decode the whole thing as GBK
text = result.decode('gbk', errors='ignore')

# Write to file
with open(r'F:\bishe\tmp_template3.txt', 'w', encoding='utf-8') as f:
    f.write(text)

# Find and print Chinese text segments
chn = re.findall(r'[^\x00-\x7f\\\{\}\s]{10,}', text)
for seg in chn[:50]:
    print(seg)
