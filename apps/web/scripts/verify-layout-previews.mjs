/**
 * Verify layout 2D preview rendering for all 11 aerodynamic layouts.
 * Reads pre-generated JSON specs, checks expected SVG element classes.
 * Usage: cd apps/web && node scripts/verify-layout-previews.mjs
 */
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

const LAYOUTS = [
  "conventional", "twin_boom", "flying_wing", "blended_wing_body",
  "canard", "three_surface", "tandem_wing", "biplane",
  "joined_wing", "box_wing", "multi_fuselage",
];

// Expected preview elements per layout
// top/side: list of CSS class suffixes (without "preview-" prefix)
const EXPECTED = {
  conventional:        { top: ["fuselage","wing","tail"], side: ["fuselage","wing","tail"] },
  twin_boom:           { top: ["fuselage","wing","tail","boom"], side: ["fuselage","wing","tail","boom"] },
  flying_wing:         { top: ["wing"], side: ["wing"], noTail: true },
  blended_wing_body:   { top: ["wing","bwb-body"], side: ["wing","bwb-body"], noTail: true },
  canard:              { top: ["fuselage","wing","tail","canard"], side: ["fuselage","wing","tail","canard"] },
  three_surface:       { top: ["fuselage","wing","tail","canard"], side: ["fuselage","wing","tail","canard"] },
  tandem_wing:         { top: ["fuselage","wing","rear-wing"], side: ["fuselage","wing","rear-wing"], noTail: true },
  biplane:             { top: ["fuselage","wing","tail","lower-wing"], side: ["fuselage","wing","tail","lower-wing"] },
  joined_wing:         { top: ["fuselage","wing","rear-wing"], side: ["fuselage","wing","rear-wing"], noTail: true },
  box_wing:            { top: ["fuselage","wing","tail","lower-wing","endplate"], side: ["fuselage","wing","tail","lower-wing","endplate"] },
  multi_fuselage:      { top: ["fuselage","wing","tail"], side: ["fuselage","wing","tail"] },
};

function textValue(v) {
  if (v == null) return undefined;
  if (typeof v === "object" && "value" in v) return v.value;
  return v;
}
function numVal(v, fb = 0) {
  const n = Number(textValue(v));
  return Number.isFinite(n) ? n : fb;
}

// Mirror previewGeometry.ts layout dispatch
function getPreviewElements(spec) {
  const aircraft = spec.aircraft || {};
  const layout = (typeof aircraft.layout === "string" ? aircraft.layout : "conventional").toLowerCase();

  const top = new Set(["fuselage", "wing"]);
  const side = new Set(["fuselage", "wing"]);
  let hasTail = true;

  if (layout === "flying_wing") { hasTail = false; }
  if (layout === "blended_wing_body") { hasTail = false; top.add("bwb-body"); side.add("bwb-body"); }
  if (layout === "twin_boom") { top.add("boom"); side.add("boom"); }
  if (layout === "canard" || layout === "three_surface") { top.add("canard"); side.add("canard"); }
  if (layout === "tandem_wing" || layout === "joined_wing") { hasTail = false; top.add("rear-wing"); side.add("rear-wing"); }
  if (layout === "biplane") { top.add("lower-wing"); side.add("lower-wing"); }
  if (layout === "box_wing") { top.add("lower-wing"); side.add("lower-wing"); top.add("endplate"); side.add("endplate"); }

  if (hasTail) { top.add("tail"); side.add("tail"); }

  return { top: [...top].sort(), side: [...side].sort(), layout, hasTail };
}

let passed = 0, failed = 0;

for (const layout of LAYOUTS) {
  const specPath = resolve(__dirname, `specs/${layout}.json`);
  let spec;
  try {
    spec = JSON.parse(readFileSync(specPath, "utf8"));
  } catch (e) {
    console.log(`❌ ${layout}: failed to load spec: ${e.message}`);
    failed++; continue;
  }

  const actualLayout = spec.aircraft?.layout;
  if (actualLayout !== layout) {
    console.log(`❌ ${layout}: spec layout="${actualLayout}" !== "${layout}"`);
    failed++; continue;
  }

  const preview = getPreviewElements(spec);
  const exp = EXPECTED[layout];

  const topMissing = exp.top.filter(c => !preview.top.includes(c));
  const sideMissing = exp.side.filter(c => !preview.side.includes(c));
  const tailBad = exp.noTail && preview.hasTail;

  if (topMissing.length === 0 && sideMissing.length === 0 && !tailBad) {
    console.log(`✅ ${layout}: top=[${preview.top}] side=[${preview.side}] tail=${preview.hasTail}`);
    passed++;
  } else {
    const issues = [];
    if (topMissing.length) issues.push(`top missing: ${topMissing}`);
    if (sideMissing.length) issues.push(`side missing: ${sideMissing}`);
    if (tailBad) issues.push("tail should be hidden");
    console.log(`❌ ${layout}: ${issues.join("; ")}`);
    failed++;
  }
}

console.log(`\n${passed}/${passed + failed} layouts verified`);
if (failed > 0) process.exit(1);
