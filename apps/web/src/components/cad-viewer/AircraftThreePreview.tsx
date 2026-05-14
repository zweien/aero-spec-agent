"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";

import type { AircraftPreviewSpec } from "./previewGeometry";
import {
  buildAircraftThreeModel,
  type AircraftThreeModel,
} from "./threePreviewModel";
import type { CadPreviewFormat } from "./cadPreviewSource";
import type { CadPreviewStatus } from "./cadPreviewStatus";

type AircraftThreePreviewProps = {
  modelFormat?: CadPreviewFormat;
  modelUrl?: string;
  onStatusChange?: (status: CadPreviewStatus) => void;
  spec: AircraftPreviewSpec;
};

function disposeMaterial(material: THREE.Material): void {
  for (const value of Object.values(material)) {
    if (value instanceof THREE.Texture) {
      value.dispose();
    }
  }
  material.dispose();
}

function disposeObject3D(object: THREE.Object3D): void {
  const disposedMaterials = new Set<THREE.Material>();

  object.traverse((child) => {
    if ("geometry" in child && child.geometry instanceof THREE.BufferGeometry) {
      child.geometry.dispose();
    }
    if ("material" in child) {
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      for (const material of materials) {
        if (material instanceof THREE.Material && !disposedMaterials.has(material)) {
          disposeMaterial(material);
          disposedMaterials.add(material);
        }
      }
    }
  });
}

function createTaperedWingMesh(
  rootChord: number,
  tipChord: number,
  span: number,
  thickness: number,
  material: THREE.Material,
): THREE.Mesh {
  const centerBand = Math.min(span * 0.04, 0.24);
  const halfSpan = span / 2;
  const shape = new THREE.Shape();
  shape.moveTo(-rootChord / 2, -centerBand);
  shape.lineTo(rootChord / 2, -centerBand);
  shape.lineTo(tipChord / 2, -halfSpan);
  shape.lineTo(-tipChord / 2, -halfSpan);
  shape.lineTo(-tipChord / 2, halfSpan);
  shape.lineTo(tipChord / 2, halfSpan);
  shape.lineTo(rootChord / 2, centerBand);
  shape.lineTo(-rootChord / 2, centerBand);
  shape.closePath();

  const geometry = new THREE.ExtrudeGeometry(shape, {
    bevelEnabled: false,
    depth: thickness,
  });
  geometry.translate(0, 0, -thickness / 2);
  return new THREE.Mesh(geometry, material);
}

function createRectWingMesh(
  chord: number,
  span: number,
  thickness: number,
  material: THREE.Material,
): THREE.Mesh {
  const geometry = new THREE.BoxGeometry(chord, span, thickness);
  return new THREE.Mesh(geometry, material);
}

function createAircraftGroup(model: AircraftThreeModel): THREE.Group {
  const group = new THREE.Group();
  const fuselageMaterial = new THREE.MeshStandardMaterial({
    color: 0xd8e2f0,
    metalness: 0.18,
    roughness: 0.42,
  });
  const wingMaterial = new THREE.MeshStandardMaterial({
    color: 0x60a5fa,
    metalness: 0.12,
    roughness: 0.5,
  });
  const tailMaterial = new THREE.MeshStandardMaterial({
    color: 0x8bd8bd,
    metalness: 0.1,
    roughness: 0.52,
  });
  const engineMaterial = new THREE.MeshStandardMaterial({
    color: 0xf2b84b,
    metalness: 0.2,
    roughness: 0.38,
  });

  const fuselage = new THREE.Mesh(
    new THREE.CapsuleGeometry(model.fuselage.diameter / 2, model.fuselage.length, 16, 24),
    fuselageMaterial,
  );
  fuselage.rotation.z = Math.PI / 2;
  group.add(fuselage);

  const wing = createTaperedWingMesh(
    model.wing.rootChord,
    model.wing.tipChord,
    model.wing.span,
    0.08,
    wingMaterial,
  );
  wing.position.set(-model.fuselage.length * 0.08, 0, model.wing.z);
  group.add(wing);

  const horizontalTail = createRectWingMesh(
    model.tail.horizontal.chord,
    model.tail.horizontal.span,
    0.06,
    tailMaterial,
  );
  horizontalTail.position.set(
    model.tail.horizontal.position.x,
    model.tail.horizontal.position.y,
    model.tail.horizontal.position.z,
  );
  group.add(horizontalTail);

  const verticalTail = createRectWingMesh(
    model.tail.vertical.chord,
    model.tail.vertical.span,
    0.06,
    tailMaterial,
  );
  verticalTail.position.set(
    model.tail.vertical.position.x,
    model.tail.vertical.position.y,
    model.tail.vertical.position.z,
  );
  verticalTail.rotation.set(
    model.tail.vertical.rotation.x,
    model.tail.vertical.rotation.y,
    model.tail.vertical.rotation.z,
  );
  group.add(verticalTail);

  for (const engine of model.engines) {
    const nacelle = new THREE.Mesh(
      new THREE.CylinderGeometry(engine.diameter / 2, engine.diameter / 2, engine.length, 24),
      engineMaterial,
    );
    nacelle.rotation.z = Math.PI / 2;
    nacelle.position.set(engine.position.x, engine.position.y, engine.position.z);
    group.add(nacelle);
  }

  return group;
}

function prepareImportedModel(object: THREE.Object3D): boolean {
  let hasMesh = false;
  object.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      hasMesh = true;
      if (!child.material) {
        child.material = new THREE.MeshStandardMaterial({
          color: 0xd8e2f0,
          metalness: 0.12,
          roughness: 0.45,
        });
      }
    }
  });
  if (!hasMesh) {
    return false;
  }

  const box = new THREE.Box3().setFromObject(object);
  if (box.isEmpty()) {
    return false;
  }
  const size = box.getSize(new THREE.Vector3());
  const maxDimension = Math.max(size.x, size.y, size.z);
  if (!Number.isFinite(maxDimension) || maxDimension <= 0) {
    return false;
  }

  const center = box.getCenter(new THREE.Vector3());
  object.position.sub(center);
  object.scale.multiplyScalar(Math.min(1, 10 / maxDimension));
  return true;
}

function loadImportedModel(
  url: string,
  format: CadPreviewFormat,
  onLoad: (object: THREE.Object3D) => void,
  onError: () => void,
): void {
  if (format === "glb") {
    new GLTFLoader().load(
      url,
      (gltf) => onLoad(gltf.scene),
      undefined,
      onError,
    );
    return;
  }

  new OBJLoader().load(
    url,
    onLoad,
    undefined,
    onError,
  );
}

export function AircraftThreePreview({
  modelFormat,
  modelUrl,
  onStatusChange,
  spec,
}: AircraftThreePreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const model = useMemo(() => buildAircraftThreeModel(spec), [spec]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const rendererCanvas = canvas;

    let animationFrame = 0;
    let isActive = true;
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      canvas: rendererCanvas,
      preserveDrawingBuffer: true,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
    camera.position.set(-7, -10, 5.2);

    const controls = new OrbitControls(camera, rendererCanvas);
    controls.enableDamping = true;
    controls.target.set(0, 0, 0);
    controls.update();

    scene.add(new THREE.HemisphereLight(0xffffff, 0x162033, 2.4));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.8);
    keyLight.position.set(-4, -6, 8);
    scene.add(keyLight);

    const aircraft = createAircraftGroup(model);
    scene.add(aircraft);
    const grid = new THREE.GridHelper(14, 14, 0x33506e, 0x213246);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.75;
    scene.add(grid);

    if (modelUrl && modelFormat) {
      onStatusChange?.({ format: modelFormat, state: "loading" });
      loadImportedModel(
        modelUrl,
        modelFormat,
        (loadedModel) => {
          if (!isActive) {
            disposeObject3D(loadedModel);
            return;
          }
          if (!prepareImportedModel(loadedModel)) {
            disposeObject3D(loadedModel);
            return;
          }
          scene.remove(aircraft);
          disposeObject3D(aircraft);
          scene.add(loadedModel);
          onStatusChange?.({ format: modelFormat, state: "loaded" });
        },
        () => onStatusChange?.({ format: modelFormat, state: "fallback" }),
      );
    } else {
      onStatusChange?.({ state: "parameter" });
    }

    function resize() {
      const width = rendererCanvas.clientWidth;
      const height = rendererCanvas.clientHeight;
      if (rendererCanvas.width !== width || rendererCanvas.height !== height) {
        renderer.setSize(width, height, false);
        camera.aspect = width / Math.max(height, 1);
        camera.updateProjectionMatrix();
      }
    }

    function render() {
      resize();
      controls.update();
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(render);
    }

    render();

    return () => {
      isActive = false;
      window.cancelAnimationFrame(animationFrame);
      controls.dispose();
      disposeObject3D(scene);
      renderer.dispose();
    };
  }, [model, modelFormat, modelUrl, onStatusChange]);

  return <canvas ref={canvasRef} className="three-preview-canvas" aria-label="可旋转 3D 飞机预览" />;
}
