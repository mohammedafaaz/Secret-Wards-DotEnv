import { Canvas, useFrame } from '@react-three/fiber';
import { Suspense, useRef } from 'react';
import { useReducedMotion } from 'framer-motion';
import type { Group, Mesh } from 'three';

const forest = '#376b56';
const paper = '#f0e8d8';
const rust = '#bd6349';

function IsometricFolio({ position, rotation = 0, color = paper, size = [0.72, 0.9, 0.08] }: {
  position: [number, number, number]; rotation?: number; color?: string; size?: [number, number, number];
}) {
  return <group position={position} rotation={[0.08, 0, rotation]}>
    <mesh castShadow receiveShadow><boxGeometry args={size} /><meshStandardMaterial color={color} roughness={0.8} metalness={0.04} /></mesh>
    <mesh position={[0, 0, size[2] / 2 + 0.008]}><boxGeometry args={[size[0] * 0.72, 0.012, 0.008]} /><meshStandardMaterial color="#80917d" transparent opacity={0.55} /></mesh>
  </group>;
}

function Reactor({ reducedMotion }: { reducedMotion: boolean }) {
  const root = useRef<Group>(null);
  const rotor = useRef<Group>(null);
  const containment = useRef<Group>(null);
  const particleRefs = useRef<(Mesh | null)[]>([]);
  const outRefs = useRef<(Group | null)[]>([]);
  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    if (root.current && !reducedMotion) {
      root.current.rotation.y += (state.pointer.x * 0.075 - root.current.rotation.y) * Math.min(delta * 1.4, 1);
      root.current.rotation.x += (-state.pointer.y * 0.04 - root.current.rotation.x) * Math.min(delta * 1.4, 1);
    }
    if (rotor.current && !reducedMotion) rotor.current.rotation.z += delta * 0.13;
    if (containment.current && !reducedMotion) containment.current.rotation.y -= delta * 0.08;
    particleRefs.current.forEach((mesh, i) => {
      if (!mesh) return;
      const phase = reducedMotion ? 0 : (t * 0.19 + i * 0.34) % 1;
      mesh.position.x = -1.35 + phase * 2.7;
      mesh.position.y = 0.12 + Math.sin(phase * Math.PI * 2 + i) * 0.11;
      mesh.visible = phase < 0.42 || phase > 0.59;
      if (phase >= 0.42 && phase <= 0.59) mesh.position.x = 0;
    });
    outRefs.current.forEach((group, i) => {
      if (!group || reducedMotion) return;
      group.position.y = -0.12 + Math.sin(t * 0.55 + i * 0.8) * 0.025;
    });
  });
  return <group ref={root}>
    {/* Raised isometric rails give each region a distinct footprint. */}
    <mesh position={[-1.45, -0.62, -0.12]} rotation={[0, 0, 0.07]}><boxGeometry args={[1.52, 0.12, 0.66]} /><meshStandardMaterial color="#d8cfbd" roughness={0.82} /></mesh>
    <mesh position={[0, -0.72, -0.15]}><boxGeometry args={[1.72, 0.13, 0.78]} /><meshStandardMaterial color="#d4c9b6" roughness={0.76} /></mesh>
    <mesh position={[1.52, -0.62, -0.12]} rotation={[0, 0, -0.06]}><boxGeometry args={[1.45, 0.12, 0.66]} /><meshStandardMaterial color="#d8cfbd" roughness={0.82} /></mesh>
    {/* Heterogeneous, deliberately blank hospital-data folios. */}
    <IsometricFolio position={[-1.8, 0.24, 0.13]} rotation={-0.14} size={[0.6, 0.78, 0.1]} />
    <IsometricFolio position={[-1.35, 0.34, 0.08]} rotation={0.1} color="#e2d8c7" size={[0.66, 0.96, 0.07]} />
    <IsometricFolio position={[-0.98, 0.15, -0.02]} rotation={0.22} color="#c9c7b7" size={[0.48, 0.7, 0.11]} />
    <mesh position={[-1.43, -0.03, 0.32]} rotation={[0, 0, 0.12]}><octahedronGeometry args={[0.1, 0]} /><meshStandardMaterial color={rust} roughness={0.36} metalness={0.12} /></mesh>
    <mesh position={[-1.05, 0.56, 0.18]} rotation={[0.1, 0.2, 0.15]}><dodecahedronGeometry args={[0.075, 0]} /><meshStandardMaterial color={forest} roughness={0.4} /></mesh>
    {/* Central reactor: five fine rings suggest conceptual privacy stages, not measured progress. */}
    <group position={[0, 0.02, 0]}>
      {[0.55, 0.67, 0.8].map((r, i) => <mesh key={r} rotation={[Math.PI / 2, i * 0.22, i * 0.37]}>
        <torusGeometry args={[r, i === 1 ? 0.023 : 0.014, 8, 72]} />
        <meshStandardMaterial color={i === 1 ? forest : '#899a86'} roughness={0.38} metalness={0.24} />
      </mesh>)}
      <mesh rotation={[Math.PI / 2, 0.06, 0]}><cylinderGeometry args={[0.61, 0.61, 0.07, 64, 1, true]} /><meshStandardMaterial color="#7caa8d" transparent opacity={0.2} side={2} roughness={0.35} /></mesh>
      <group ref={rotor}>
        {[0, 1, 2].map((i) => <mesh key={i} rotation={[0, 0, i * Math.PI / 3]}><boxGeometry args={[0.035, 1.55, 0.035]} /><meshStandardMaterial color="#728a77" metalness={0.3} roughness={0.45} /></mesh>)}
      </group>
      <group ref={containment}>
        <mesh position={[0, 0, 0.2]}><dodecahedronGeometry args={[0.25, 0]} /><meshStandardMaterial color="#d1b190" metalness={0.19} roughness={0.46} /></mesh>
        {[0, 1, 2].map((i) => <mesh key={i} position={[Math.cos(i * 2.1) * 0.39, Math.sin(i * 2.1) * 0.39, 0.18]}><octahedronGeometry args={[0.055, 0]} /><meshStandardMaterial color={rust} emissive={rust} emissiveIntensity={0.08} roughness={0.5} /></mesh>)}
      </group>
      <mesh position={[0, -0.57, 0]}><boxGeometry args={[1.25, 0.045, 0.48]} /><meshStandardMaterial color="#8c7861" roughness={0.55} /></mesh>
    </group>
    {/* Abstract clinical-information flow. No value names or patient details. */}
    {Array.from({ length: 5 }, (_, i) => <mesh key={`flow-${i}`} ref={(el) => { particleRefs.current[i] = el; }} position={[-1.35 + i * 0.14, 0.1, 0.42]}>
      <octahedronGeometry args={[0.035, 0]} /><meshStandardMaterial color={i === 2 ? '#547e60' : '#86a77f'} roughness={0.4} />
    </mesh>)}
    {/* Research-ready output: aligned, blank folios—never a claimed run result. */}
    <group ref={(el) => { outRefs.current[0] = el; }} position={[1.33, -0.12, 0.1]}><IsometricFolio position={[0, 0.18, 0]} rotation={0.05} size={[0.6, 0.66, 0.09]} /><IsometricFolio position={[0.32, 0.04, -0.02]} rotation={-0.04} color="#d7d9c7" size={[0.56, 0.73, 0.08]} /></group>
    <group ref={(el) => { outRefs.current[1] = el; }} position={[1.72, -0.12, 0.02]}><IsometricFolio position={[0, 0.12, 0]} rotation={0.03} size={[0.47, 0.62, 0.09]} /></group>
  </group>;
}

export default function VaultScene() {
  const reducedMotion = useReducedMotion() ?? false;
  return <div className="vault-canvas" aria-label="The Shield Privacy Reactor, a conceptual 3D installation showing abstract fragmented inputs, a layered privacy chamber with contained identifiers, and blank organized outputs. Not live data or a processing result." role="img">
    <Canvas camera={{ position: [3.8, 2.9, 7.4], fov: 34 }} dpr={[1, 1.35]} gl={{ alpha: true, antialias: true }} fallback={<div className="vault-fallback" aria-hidden="true"><span /><span /><span /></div>}>
      <Suspense fallback={null}><ambientLight intensity={1.7} /><directionalLight position={[2, 4, 5]} intensity={2} color="#fff8ea" /><pointLight position={[-1.4, 1.1, 2]} intensity={7} distance={7} color="#bd6349" /><pointLight position={[1.5, 1, 2]} intensity={7} distance={7} color="#64856a" /><Reactor reducedMotion={reducedMotion} /></Suspense>
    </Canvas>
    <div className="reactor-labels" aria-hidden="true"><span>FRAGMENTED INPUT</span><span>PRIVACY REACTOR</span><span>CONTROLLED RELEASE</span></div>
    <div className="scene-index" aria-hidden="true"><span>THE SHIELD PRIVACY REACTOR / CONCEPT</span><span>NOT LIVE DATA</span></div>
  </div>;
}
