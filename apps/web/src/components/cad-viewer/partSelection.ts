export type AircraftPartId =
  | "fuselage"
  | "main_wing"
  | "tail"
  | "left_engine"
  | "right_engine";

export function partRefFromPartId(partId: AircraftPartId): string {
  return `part:${partId}`;
}
