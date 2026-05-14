from pathlib import Path

from services.workers.cad_worker.openvsp_generator.obj_to_glb import convert_obj_to_glb


def test_convert_obj_to_glb_writes_binary_glb(tmp_path: Path):
    obj_path = tmp_path / "triangle.obj"
    glb_path = tmp_path / "triangle.glb"
    obj_path.write_text(
        "\n".join(
            [
                "o triangle",
                "v 0 0 0",
                "v 1 0 0",
                "v 0 1 0",
                "f 1 2 3",
            ]
        ),
        encoding="utf-8",
    )

    convert_obj_to_glb(obj_path, glb_path)

    assert glb_path.exists()
    assert glb_path.read_bytes()[:4] == b"glTF"
    assert glb_path.stat().st_size > 20
