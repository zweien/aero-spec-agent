import assert from "node:assert/strict";
import test from "node:test";

import {
  buildVersionFileUrl,
  selectCadPreviewSource,
} from "./cadPreviewSource.ts";

test("buildVersionFileUrl creates an API URL for generated files", () => {
  const url = buildVersionFileUrl("http://localhost:8900", "demo", 3, "aircraft.obj");

  assert.equal(
    url,
    "http://localhost:8900/api/designs/demo/versions/3/files/aircraft.obj",
  );
});

test("selectCadPreviewSource prefers glb over obj", () => {
  const source = selectCadPreviewSource({
    apiBaseUrl: "http://localhost:8900",
    designId: "demo",
    versionNo: 4,
    files: ["aircraft.obj", "aircraft.glb"],
  });

  assert.deepEqual(source, {
    filename: "aircraft.glb",
    format: "glb",
    url: "http://localhost:8900/api/designs/demo/versions/4/files/aircraft.glb",
  });
});

test("selectCadPreviewSource falls back to obj when glb is unavailable", () => {
  const source = selectCadPreviewSource({
    apiBaseUrl: "http://localhost:8900",
    designId: "demo",
    versionNo: 5,
    files: ["aircraft.step", "aircraft.obj"],
  });

  assert.equal(source?.format, "obj");
  assert.equal(source?.filename, "aircraft.obj");
});

test("selectCadPreviewSource returns null without a previewable artifact", () => {
  const source = selectCadPreviewSource({
    apiBaseUrl: "http://localhost:8900",
    designId: "demo",
    versionNo: 6,
    files: ["aircraft.step", "aircraft.vsp3"],
  });

  assert.equal(source, null);
});
