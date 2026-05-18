import re

with open(r'C:\Users\DayMer\Downloads\王晓辉论文(设计)模板.doc', 'rb') as f:
    data = f.read()

# Find all \'xx sequences and collect as byte array
# But first, strip RTF control words to keep only the \'xx escapes and plain ASCII
text = data.decode('ascii', errors='ignore')

# Replace \'xx with actual byte
def unescape_all(m):
    return chr(int(m.group(1), 16))

text = re.sub(r"\\'([0-9a-fA-F]{2})", unescape_all, text)

# Now encode as latin-1 and decode as GBK
text_bytes = text.encode('latin-1', errors='ignore')
text = text_bytes.decode('gbk', errors='ignore')

# Strip RTF control words
text = re.sub(r'\\[a-zA-Z]+\d*\s?', ' ', text)
text = re.sub(r'\{|\}', '', text)
text = re.sub(r'\n\s*\n', '\n\n', text)

# Save
with open(r'F:\bishe\tmp_template2.txt', 'w', encoding='utf-8') as f:
    f.write(text)

# Find Chinese sections
matches = list(re.finditer(r'[一-鿿　-〿＀-￯]{8,}', text))
print(f"Found {len(matches)} Chinese text segments")
for m in matches[:20]:
    start = max(0, m.start()-20)
    end = min(len(text), m.end()+20)
    print(f"---\n{text[start:end]}\n")
