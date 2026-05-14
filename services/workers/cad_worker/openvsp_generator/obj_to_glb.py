from pathlib import Path

import trimesh

from services.workers.cad_worker.openvsp_generator.errors import CadGenerationError


def convert_obj_to_glb(obj_path: Path, glb_path: Path) -> None:
    if not obj_path.is_file():
        raise CadGenerationError(f"OBJ file does not exist: {obj_path}")

    loaded = trimesh.load(obj_path, force="scene")
    if loaded is None:
        raise CadGenerationError(f"Failed to load OBJ file: {obj_path}")

    glb_path.parent.mkdir(parents=True, exist_ok=True)
    exported = loaded.export(file_type="glb")
    if not isinstance(exported, bytes):
        raise CadGenerationError("OBJ to GLB conversion did not return binary data")
    glb_path.write_bytes(exported)

    if not glb_path.exists() or glb_path.stat().st_size == 0:
        raise CadGenerationError(f"GLB file was not written: {glb_path}")
