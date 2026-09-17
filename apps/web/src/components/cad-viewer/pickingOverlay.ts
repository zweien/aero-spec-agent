import type { AircraftPartId } from "./partSelection.ts";
import { partRefFromPartId } from "./partSelection.ts";
import type { AircraftThreeModel } from "./threePreviewModel.ts";

/**
 * Whether the spec-built aircraft should be added as an invisible picking
 * overlay (instead of a visible wireframe model).
 *
 * True when a real imported model is already loaded, or when one is expected
 * (CAD backend produces real model files): showing the wireframe as a visible
 * "model" first and swapping it for the real geometry later is misleading —
 * the wireframe should stay pick-only until the real model arrives (and be
 * restored to visible if loading ultimately fails).
 */
export function shouldUsePickingOverlay(
  importedLoaded: boolean,
  expectImported = false,
): boolean {
  return importedLoaded || expectImported;
}

export function buildPartRefsFromModel(model: AircraftThreeModel): string[] {
  const partIds: AircraftPartId[] = [
    model.fuselage.partId,
    model.wing.partId,
    model.tail.horizontal.partId,
    model.tail.vertical.partId,
    ...model.engines.map((engine) => engine.partId),
  ];

  return [...new Set(partIds)].map(partRefFromPartId);
}
