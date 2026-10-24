// shortcut: supports bold, italic and code only; use a Markdown library when more syntax is required.
export function parseMessage(text) {
  const pattern =
    /(?<!`)```(?!`)(?:[a-zA-Z0-9_+-]+\r?\n)?\r?\n?([\s\S]*?)```(?!`)|(?<!`)`([^`\n]+)`(?!`)|\*\*(?=\S)([\s\S]*?\S)\*\*|(?<![\p{L}\p{N}_])_(?=\S)([^_]*?\S)_(?![\p{L}\p{N}_])/gu;
  const tokens = [];
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor)
      tokens.push({ type: "text", value: text.slice(cursor, match.index) });
    const [, block, code, bold, italic] = match;
    if (block !== undefined)
      tokens.push({ type: "block", value: block.replace(/\r?\n$/, "") });
    else if (code !== undefined) tokens.push({ type: "code", value: code });
    else
      tokens.push({
        type: bold !== undefined ? "bold" : "italic",
        children: parseMessage(bold ?? italic),
      });
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length)
    tokens.push({ type: "text", value: text.slice(cursor) });
  return tokens;
}
