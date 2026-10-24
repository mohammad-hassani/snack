import assert from "node:assert/strict";
import { parseMessage } from "./format-message.mjs";
const text = (value) => ({ type: "text", value });
assert.deepEqual(parseMessage("سلام **پررنگ** _مورب_ `code()`"), [
  text("سلام "),
  { type: "bold", children: [text("پررنگ")] },
  text(" "),
  { type: "italic", children: [text("مورب")] },
  text(" "),
  { type: "code", value: "code()" },
]);
assert.deepEqual(parseMessage("**_both_**"), [
  { type: "bold", children: [{ type: "italic", children: [text("both")] }] },
]);
assert.deepEqual(parseMessage("`**plain** _code_`"), [
  { type: "code", value: "**plain** _code_" },
]);
assert.deepEqual(parseMessage("```js\nconst x = 1;\nconsole.log(x);\n```"), [
  { type: "block", value: "const x = 1;\nconsole.log(x);" },
]);
assert.deepEqual(parseMessage("```\n**not bold**\n```"), [
  { type: "block", value: "**not bold**" },
]);
for (const value of [
  "snake_case_variable",
  "name_part",
  "**unfinished",
  "_unfinished",
  "****",
  "",
  "<script>alert(1)</script>",
]) {
  assert.deepEqual(parseMessage(value), value ? [text(value)] : [], value);
}
assert.deepEqual(parseMessage("_x_ **y**"), [
  { type: "italic", children: [text("x")] },
  text(" "),
  { type: "bold", children: [text("y")] },
]);
assert.deepEqual(parseMessage("first\n**second**\nthird"), [
  text("first\n"),
  { type: "bold", children: [text("second")] },
  text("\nthird"),
]);
assert.deepEqual(parseMessage("`".repeat(4000)), [text("`".repeat(4000))]);
console.log(
  "Message formatting tests passed: Persian, nesting, code isolation/blocks, plain text, incomplete markers, boundaries, HTML text, maximum-length input.",
);

assert.deepEqual(parseMessage("_first\nsecond_"), [
  { type: "italic", children: [text("first\nsecond")] },
]);
