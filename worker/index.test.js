import test from "node:test";
import assert from "node:assert/strict";

import worker from "./index.js";

test("health endpoint returns ok", async () => {
  const response = await worker.fetch(
    new Request("https://worker.example/health"),
    {},
  );

  assert.equal(response.status, 200);
  assert.equal(await response.text(), "ok");
});

test("close endpoint is disabled", async () => {
  const response = await worker.fetch(
    new Request("https://worker.example/close/42", { method: "POST" }),
    {},
  );

  assert.equal(response.status, 410);
  assert.match(await response.text(), /disabled/i);
});
