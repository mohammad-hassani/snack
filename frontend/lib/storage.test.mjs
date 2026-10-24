import assert from "node:assert/strict";
import { migrateStorage } from "./storage.mjs";
const values = {
  "teamflow:1:2:3": '{"body":"unsent draft","clientId":"stable-id"}',
  "teamflow-channel:2": "3",
  "teamflow:existing": "old draft",
  "snack:existing": "new draft",
  "other-app": "untouched",
};
const storage = new Proxy(values, {
  get(target, key) {
    if (key === "getItem") return (key) => target[key] ?? null;
    if (key === "setItem")
      return (key, value) => {
        target[key] = value;
      };
    if (key === "removeItem")
      return (key) => {
        delete target[key];
      };
    return target[key];
  },
});
migrateStorage(storage);
assert.deepEqual(values, {
  "teamflow:existing": "old draft",
  "snack:1:2:3": '{"body":"unsent draft","clientId":"stable-id"}',
  "snack-channel:2": "3",
  "snack:existing": "new draft",
  "other-app": "untouched",
});
migrateStorage(storage);
assert.equal(values["snack-channel:2"], "3");
console.log(
  "Storage migration passed: drafts, retry IDs, preferences, conflicts, unrelated keys, repeated runs.",
);
