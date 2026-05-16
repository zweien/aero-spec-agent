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
import {
  partRefFromPartId,
  type AircraftPartId,
} from "./partSelection";
import { shouldUsePickingOverlay } from "./pickingOverlay";

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
    fuselageMaterial.clone(),
  );
  fuselage.userData.partId = model.fuselage.partId;
  fuselage.rotation.z = Math.PI / 2;
  group.add(fuselage);

  const wing = createTaperedWingMesh(
    model.wing.rootChord,
    model.wing.tipChord,
    model.wing.span,
    0.08,
    wingMaterial.clone(),
  );
  wing.userData.partId = model.wing.partId;
  wing.position.set(-model.fuselage.length * 0.08, 0, model.wing.z);
  group.add(wing);

  const horizontalTail = createRectWingMesh(
    model.tail.horizontal.chord,
    model.tail.horizontal.span,
    0.06,
    tailMaterial.clone(),
  );
  horizontalTail.userData.partId = model.tail.horizontal.partId;
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
    tailMaterial.clone(),
  );
  verticalTail.userData.partId = model.tail.vertical.partId;
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
      engineMaterial.clone(),
    );
    nacelle.userData.partId = engine.partId;
    nacelle.rotation.z = Math.PI / 2;
    nacelle.position.set(engine.position.x, engine.position.y, engine.position.z);
    group.add(nacelle);
  }

  return group;
}

function findPartId(object: THREE.Object3D): AircraftPartId | null {
  let current: THREE.Object3D | null = object;
  while (current) {
    const partId = current.userData.partId;
    if (typeof partId === "string") {
      return partId as AircraftPartId;
    }
    current = current.parent;
  }
  return null;
}

function makePickingOverlayInvisible(root: THREE.Object3D): void {
  root.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    for (const material of materials) {
      if (material instanceof THREE.MeshStandardMaterial) {
        material.transparent = true;
        material.opacity = 0;
        material.depthWrite = false;
        material.colorWrite = false;
      }
    }
  });
}

function setPartHighlight(root: THREE.Object3D, partId: AircraftPartId, enabled: boolean): void {
  root.traverse((child) => {
    if (!(child instanceof THREE.Mesh) || findPartId(child) !== partId) return;
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    for (const material of materials) {
      if (material instanceof THREE.MeshStandardMaterial) {
        material.emissive.setHex(enabled ? 0x38bdf8 : 0x000000);
        material.emissiveIntensity = enabled ? 0.55 : 0;
      }
    }
  });
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

type AircraftThreePreviewProps = {
  modelFormat?: CadPreviewFormat;
  modelUrl?: string;
  onStatusChange?: (status: CadPreviewStatus) => void;
  onSelectPart?: (partRef: string | null) => void;
  spec: AircraftPreviewSpec;
};

export function AircraftThreePreview({
  modelFormat,
  modelUrl,
  onSelectPart,
  onStatusChange,
  spec,
}: AircraftThreePreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const model = useMemo(() => buildAircraftThreeModel(spec), [spec]);

  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const wireframeRef = useRef<THREE.Group | null>(null);
  const pickingOverlayRef = useRef<THREE.Group | null>(null);
  const importedRef = useRef<THREE.Object3D | null>(null);
  const selectedPartIdRef = useRef<AircraftPartId | null>(null);
  const onSelectPartRef = useRef<typeof onSelectPart>(onSelectPart);
  const animFrameRef = useRef(0);
  const isActiveRef = useRef(true);

  useEffect(() => {
    onSelectPartRef.current = onSelectPart;
  }, [onSelectPart]);

  // Scene setup — runs once
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const activeCanvas = canvas;

    isActiveRef.current = true;

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      canvas,
      preserveDrawingBuffer: true,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    rendererRef.current = renderer;

    const scene = new THREE.Scene();
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
    camera.position.set(-7, -10, 5.2);

    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.target.set(0, 0, 0);
    controls.update();
    controlsRef.current = controls;

    scene.add(new THREE.HemisphereLight(0xffffff, 0x162033, 2.4));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.8);
    keyLight.position.set(-4, -6, 8);
    scene.add(keyLight);

    const grid = new THREE.GridHelper(14, 14, 0x33506e, 0x213246);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.75;
    scene.add(grid);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    function handlePointerDown(event: PointerEvent) {
      const root = pickingOverlayRef.current;
      if (!root) return;

      const rect = activeCanvas.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);

      const hit = raycaster
        .intersectObjects(root.children, true)
        .find((intersection) => findPartId(intersection.object));
      const nextPartId = hit ? findPartId(hit.object) : null;
      const prevPartId = selectedPartIdRef.current;

      if (prevPartId) {
        setPartHighlight(root, prevPartId, false);
      }
      selectedPartIdRef.current = nextPartId;
      if (nextPartId) {
        setPartHighlight(root, nextPartId, true);
        onSelectPartRef.current?.(partRefFromPartId(nextPartId));
      } else {
        onSelectPartRef.current?.(null);
      }
    }

    activeCanvas.addEventListener("pointerdown", handlePointerDown);

    function resize() {
      const el = canvasRef.current;
      if (!el) return;
      const width = el.clientWidth;
      const height = el.clientHeight;
      if (el.width !== width || el.height !== height) {
        renderer.setSize(width, height, false);
        camera.aspect = width / Math.max(height, 1);
        camera.updateProjectionMatrix();
      }
    }

    function render() {
      resize();
      controls.update();
      renderer.render(scene, camera);
      animFrameRef.current = window.requestAnimationFrame(render);
    }

    render();

    return () => {
      isActiveRef.current = false;
      window.cancelAnimationFrame(animFrameRef.current);
      activeCanvas.removeEventListener("pointerdown", handlePointerDown);
      controls.dispose();
      disposeObject3D(scene);
      renderer.dispose();
      sceneRef.current = null;
      rendererRef.current = null;
      controlsRef.current = null;
      wireframeRef.current = null;
      pickingOverlayRef.current = null;
      importedRef.current = null;
    };
  }, []);

  // Update wireframe / picking overlay when spec changes
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !isActiveRef.current) return;

    // Remove old wireframe
    if (wireframeRef.current) {
      scene.remove(wireframeRef.current);
      disposeObject3D(wireframeRef.current);
    }

    // Remove old picking overlay
    if (pickingOverlayRef.current) {
      scene.remove(pickingOverlayRef.current);
      disposeObject3D(pickingOverlayRef.current);
    }

    const aircraft = createAircraftGroup(model);

    if (shouldUsePickingOverlay(Boolean(importedRef.current))) {
      // Real model loaded: create transparent picking overlay
      makePickingOverlayInvisible(aircraft);
      scene.add(aircraft);
      pickingOverlayRef.current = aircraft;
    } else {
      // No real model: wireframe IS the picking overlay
      scene.add(aircraft);
      wireframeRef.current = aircraft;
      pickingOverlayRef.current = aircraft;

      if (!modelUrl || !modelFormat) {
        onStatusChange?.({ state: "parameter" });
      }
    }

    if (selectedPartIdRef.current) {
      setPartHighlight(aircraft, selectedPartIdRef.current, true);
    }
  }, [model, modelUrl, modelFormat, onStatusChange]);

  // Load imported model (GLB/OBJ) — keeps old model visible until new loads
  useEffect(() => {
    if (!modelUrl || !modelFormat || !sceneRef.current || !isActiveRef.current) return;

    const scene = sceneRef.current;

    onStatusChange?.({ format: modelFormat, state: "loading" });

    loadImportedModel(
      modelUrl,
      modelFormat,
      (loadedModel) => {
        if (!isActiveRef.current || sceneRef.current !== scene) {
          disposeObject3D(loadedModel);
          return;
        }
        if (!prepareImportedModel(loadedModel)) {
          disposeObject3D(loadedModel);
          return;
        }

        // Remove old imported model
        if (importedRef.current) {
          scene.remove(importedRef.current);
          disposeObject3D(importedRef.current);
        }

        // Convert wireframe to transparent picking overlay
        if (wireframeRef.current) {
          makePickingOverlayInvisible(wireframeRef.current);
          pickingOverlayRef.current = wireframeRef.current;
          wireframeRef.current = null;
        }

        scene.add(loadedModel);
        importedRef.current = loadedModel;
        onStatusChange?.({ format: modelFormat, state: "loaded" });
      },
      () => {
        if (isActiveRef.current) {
          onStatusChange?.({ format: modelFormat, state: "fallback" });
        }
      },
    );
  }, [modelUrl, modelFormat, onStatusChange]);

  return <canvas ref={canvasRef} className="three-preview-canvas" aria-label="可旋转 3D 飞机预览" />;
}
