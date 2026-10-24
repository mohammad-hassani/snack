import { parseMessage } from "../lib/format-message.mjs";

function render(tokens, inline) {
  return tokens.map((token, index) => {
    if (token.type === "text") return token.value;
    if (token.type === "code" || token.type === "block") {
      return (
        <code
          key={index}
          dir="ltr"
          className={
            token.type === "block" && !inline ? "code-block" : undefined
          }
        >
          {token.value}
        </code>
      );
    }
    const Tag = token.type === "bold" ? "strong" : "em";
    return <Tag key={index}>{render(token.children, inline)}</Tag>;
  });
}

export default function MessageText({ text, inline = false }) {
  return (
    <span className="message-text">{render(parseMessage(text), inline)}</span>
  );
}
