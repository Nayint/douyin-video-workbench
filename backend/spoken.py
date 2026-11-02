"""Comma-separated spoken paragraphs without changing wording or punctuation."""
import re

LAYOUT_VERSION = 'spoken-compact-lines-v6'
FORMAT_REQUIREMENT = (
    '【正文排版】一个逗号一段：在每个中文或英文逗号后换行，不留空行，保留逗号。'
    '句号、问号和叹号结束后也换行，不留空行。不要为了分段添加标点，'
    '不逐字或逐词换行，不按字数拆句，不在顿号处分段，数字千位分隔符不能拆开。'
    '只输出纯文案，不加标题、编号或代码块。'
    '排版示例（只学习格式）：\n它是一个 U 型的设计，\n后面有魔术贴，'
    '\n可以调整松紧。\n围好之后，\n整个脖子能有一个支撑。'
)


def plain_body(text):
    return re.sub(r'^---\r?\n.*?\r?\n---\r?\n\s*', '', text, count=1, flags=re.S).strip()


def format_spoken(text):
    """Merge model wrapping, then separate clauses with single line breaks."""
    # Some ASR-like model responses use spaces instead of punctuation. Preserve
    # their phrase boundaries; never split Latin names or numeric separators.
    if not re.search(r'[，,。！？!?；;]', text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) > 1 and sum(len(line) <= 2 for line in lines) > len(lines) / 2:
            text = ''.join(lines)
        else:
            text = '\n'.join(lines)
        text = re.sub(r'(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])', '\n', text)
        return '\n'.join(line.strip() for line in text.splitlines() if line.strip())
    paragraphs = re.split(r'\n[ \t]*\n', text.replace('\r\n', '\n').replace('\r', '\n').strip())
    result = []
    pending = ''
    for paragraph in paragraphs:
        joined = ''
        for line in paragraph.splitlines():
            line = line.strip()
            separator = ' ' if joined and re.search(r'[A-Za-z]$', joined) and re.match(r'[A-Za-z]', line) else ''
            joined += separator + line
        if not joined:
            continue
        separator = ' ' if pending and re.search(r'[A-Za-z]$', pending) and re.match(r'[A-Za-z]', joined) else ''
        pending += separator + joined
        # A model-created blank line cannot sever an unfinished sentence.
        if re.search(r'[。！？!?][”’」』）)]*$', pending):
            result.append(_sentence_lines(pending))
            pending = ''
    if pending:
        result.append(_sentence_lines(pending))
    return '\n'.join(result)


def _sentence_lines(paragraph):
    lines, pending, quotes = [], '', []
    pairs = {'“': '”', '‘': '’', '「': '」', '『': '』', '（': '）', '(': ')'}
    endings = '。！？!?'
    for index, char in enumerate(paragraph):
        pending += char
        if char in pairs:
            quotes.append(pairs[char])
        elif quotes and char == quotes[-1]:
            quotes.pop()
        following = paragraph[index + 1:index + 2]
        numeric_comma = char == ',' and index > 0 and paragraph[index - 1].isdigit() and following.isdigit()
        comma = char in '，,' and not numeric_comma
        # Keep thousand separators, enumeration marks and punctuation runs intact.
        if (comma or (char in endings and not quotes)) and following not in endings + '，,':
            lines.append(pending.strip())
            pending = ''
    if pending:
        lines.append(pending.strip())
    return '\n'.join(lines)


def layout_document(text):
    """Apply the current presentation/export layout without rewriting old notes."""
    header = re.match(r'^---\r?\n.*?\r?\n---\r?\n', text, flags=re.S)
    body = plain_body(text)
    body = format_spoken(body)
    return (header.group(0) + '\n' if header else '') + markdown_lines(body)


def markdown_lines(text):
    lines = text.replace('\r\n', '\n').strip().splitlines()
    return '\n'.join(line.rstrip() + ('  ' if line.strip() and i + 1 < len(lines) and lines[i + 1].strip() else '')
                     for i, line in enumerate(lines))


def plain_lines(text):
    return '\n'.join(line.rstrip() for line in text.splitlines())
