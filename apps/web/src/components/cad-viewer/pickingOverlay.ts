import type { AircraftPartId } from "./partSelection.ts";
import { partRefFromPartId } from "./partSelection.ts";
import type { AircraftThreeModel } from "./threePreviewModel.ts";

export function shouldUsePickingOverlay(importedLoaded: boolean): boolean {
  return importedLoaded;
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
