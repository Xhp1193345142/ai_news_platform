<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const canvas = ref(null);
const props = defineProps({ sceneMode: { type: String, default: "auth" } });
let renderer;
let composer;
let resizeObserver;
let frameId;
let mediaQuery;
let render;
let controls;
let glitchPass;
let glitchStartedAt = 0;
let blackHole;
let authPosition;
let consolePosition;
let targetPosition;
let targetScale;
let requestedSceneMode = props.sceneMode;

function setSceneMode(mode) {
  if (!blackHole || !authPosition || !consolePosition || !controls) return;
  const isConsole = mode === "console";
  targetPosition.copy(isConsole ? consolePosition : authPosition);
  targetScale.setScalar(isConsole ? 0.42 : 0.64);
  controls.enableRotate = !isConsole;
  controls.enableZoom = !isConsole;
}

watch(() => props.sceneMode, (mode) => {
  requestedSceneMode = mode;
  setSceneMode(mode);
});

function triggerGlitch() {
  if (!glitchPass) return;
  glitchStartedAt = window.performance.now();
  glitchPass.enabled = true;
}

defineExpose({ triggerGlitch });

onMounted(() => {
  const element = canvas.value;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 4000);
  // Start from the source scene's three-quarter view. It keeps the disk on
  // a left-bottom → right-top diagonal instead of presenting it face-on.
  camera.position.set(-6.5, 5, 6.5);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ canvas: element, alpha: true, antialias: true, powerPreference: "high-performance" });
  renderer.setClearColor(0x020104, 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  const initialBounds = element.getBoundingClientRect();
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(initialBounds.width || window.innerWidth, initialBounds.height || window.innerHeight, false);

  composer = new EffectComposer(renderer);
  composer.renderToScreen = true;
  const renderPass = new RenderPass(scene, camera);
  renderPass.clear = true;
  composer.addPass(renderPass);
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(1, 1), 0.6, 0.7, 0.2));
  const lensingPass = new ShaderPass({
    uniforms: { tDiffuse: { value: null }, blackHoleScreenPos: { value: new THREE.Vector2(.5, .5) }, lensingStrength: { value: .12 }, lensingRadius: { value: .3 }, aspectRatio: { value: 1 }, chromaticAberration: { value: .015 }, scanlineIntensity: { value: .15 }, vignetteDarkness: { value: .8 } },
    vertexShader: "varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}",
    fragmentShader: "uniform sampler2D tDiffuse;uniform vec2 blackHoleScreenPos;uniform float lensingStrength,lensingRadius,aspectRatio,chromaticAberration,scanlineIntensity,vignetteDarkness;varying vec2 vUv;void main(){vec2 p=vUv,c=p-blackHoleScreenPos;c.x*=aspectRatio;float d=length(c);float edge=1.-smoothstep(lensingRadius*.3,lensingRadius,d);float a=clamp(lensingStrength/(d*d+.003),0.,.7)*edge;vec2 o=normalize(c)*a;o.x/=aspectRatio;float r=texture2D(tDiffuse,p-o*(1.+chromaticAberration)).r;float g=texture2D(tDiffuse,p-o).g;float b=texture2D(tDiffuse,p-o*(1.-chromaticAberration)).b;vec3 color=vec3(r,g,b);color-=((sin(vUv.y*800.)*.5+.5)*scanlineIntensity)*color;color*=1.-length(vUv-vec2(.5))*vignetteDarkness;gl_FragColor=vec4(color,1.);}"
  });
  composer.addPass(lensingPass);
  glitchPass = new ShaderPass({
    uniforms: { tDiffuse: { value: null }, uIntensity: { value: 0 }, uTime: { value: 0 } },
    vertexShader: "varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}",
    fragmentShader: "uniform sampler2D tDiffuse;uniform float uIntensity,uTime;varying vec2 vUv;float random(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}void main(){vec2 uv=vUv;float rOffset=(random(uv+uTime*.4)-.5)*.05*uIntensity;float gOffset=(random(uv+uTime*.6)-.5)*.05*uIntensity;vec3 glitched=vec3(texture2D(tDiffuse,uv+vec2(rOffset,0.)).r,texture2D(tDiffuse,uv+vec2(gOffset,0.)).g,texture2D(tDiffuse,uv).b);float lineY=floor(uv.y*50.+uTime*20.);float lineShift=(random(vec2(lineY,uTime))-.5)*.1*uIntensity;if(random(vec2(lineY,uTime*2.))>.97-uIntensity*.3)glitched=texture2D(tDiffuse,vec2(uv.x+lineShift,uv.y)).rgb;vec3 original=texture2D(tDiffuse,vUv).rgb;gl_FragColor=vec4(mix(original,glitched,uIntensity),1.);}"
  });
  glitchPass.enabled = false;
  composer.addPass(glitchPass);
  controls = new OrbitControls(camera, element);
  controls.enableDamping = true;
  controls.dampingFactor = .035;
  controls.rotateSpeed = .4;
  controls.enablePan = false;
  controls.minDistance = 2.5;
  controls.maxDistance = 100;
  controls.target.set(0, 0, 0);
  controls.update();

  const starCount = 26000;
  const positions = new Float32Array(starCount * 3);
  const colors = new Float32Array(starCount * 3);
  for (let i = 0; i < starCount; i += 1) {
    const offset = i * 3;
    const phi = Math.acos(-1 + (2 * i) / starCount);
    const theta = Math.sqrt(starCount * Math.PI) * phi;
    const radius = Math.cbrt(Math.random()) * 2000 + 100;
    positions[offset] = radius * Math.sin(phi) * Math.cos(theta);
    positions[offset + 1] = radius * Math.sin(phi) * Math.sin(theta);
    positions[offset + 2] = radius * Math.cos(phi);
    const palette = [new THREE.Color(0x00ffff), new THREE.Color(0xff00ff), new THREE.Color(0x8a2be2), new THREE.Color(0x00ff7f), new THREE.Color(0xccddff)];
    const color = palette[i % palette.length].multiplyScalar(Math.random() * .7 + .3);
    colors[offset] = color.r; colors[offset + 1] = color.g; colors[offset + 2] = color.b;
  }
  const stars = new THREE.Points(new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(positions, 3)).setAttribute("color", new THREE.BufferAttribute(colors, 3)), new THREE.PointsMaterial({ size: 2, vertexColors: true, transparent: true, opacity: .72, blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(stars);

  blackHole = new THREE.Group();
  const forward = new THREE.Vector3();
  const screenRight = new THREE.Vector3();
  const screenUp = new THREE.Vector3();
  camera.getWorldDirection(forward);
  screenRight.crossVectors(forward, camera.up).normalize();
  screenUp.crossVectors(screenRight, forward).normalize();
  // Composition intentionally reserves the right third for the auth card.
  // This places the black hole inside the upper-left visual field shown in
  // the approved reference while keeping the headline unobstructed.
  blackHole.position.addScaledVector(screenRight, -1.72).addScaledVector(screenUp, .92);
  blackHole.scale.setScalar(.64);
  authPosition = blackHole.position.clone();
  consolePosition = new THREE.Vector3().addScaledVector(screenRight, -0.65).addScaledVector(screenUp, .52);
  targetPosition = authPosition.clone();
  targetScale = new THREE.Vector3().setScalar(.64);
  scene.add(blackHole);
  setSceneMode(requestedSceneMode);

  const horizon = new THREE.Mesh(new THREE.SphereGeometry(1.38, 128, 64), new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uCameraPosition: { value: camera.position.clone() } },
    vertexShader: "varying vec3 vNormal; varying vec3 vPosition; void main(){vNormal=normalize(normalMatrix*normal);vPosition=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}",
    fragmentShader: "uniform float uTime;uniform vec3 uCameraPosition;varying vec3 vNormal;varying vec3 vPosition;void main(){vec3 viewDirection=normalize(uCameraPosition-vPosition);float fresnel=pow(1.-abs(dot(vNormal,viewDirection)),2.);float pulse=sin(uTime*3.5)*.2+.8;vec3 glowColor=vec3(0.,1.,.8);gl_FragColor=vec4(glowColor*fresnel*pulse,fresnel*.5);}",
    transparent: true, blending: THREE.AdditiveBlending, side: THREE.BackSide, depthWrite: false
  }));
  blackHole.add(horizon);
  const core = new THREE.Mesh(new THREE.SphereGeometry(1.3, 128, 64), new THREE.MeshBasicMaterial({ color: 0x010106 }));
  blackHole.add(core);

  const disk = new THREE.Mesh(new THREE.RingGeometry(1.5, 8, 256, 128), new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uColorHot: { value: new THREE.Color(0xffffff) }, uColorMid1: { value: new THREE.Color(0xff00ff) }, uColorMid2: { value: new THREE.Color(0x00ffff) }, uColorOuter: { value: new THREE.Color(0x3939f5) } },
    vertexShader: "varying float vRadius;varying float vAngle;void main(){vRadius=length(position.xy);vAngle=atan(position.y,position.x);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}",
    fragmentShader: "uniform float uTime;uniform vec3 uColorHot,uColorMid1,uColorMid2,uColorOuter;varying float vRadius;varying float vAngle;float noise(vec2 p){return sin(p.x)*sin(p.y)*.5+.5;}void main(){float r=smoothstep(1.5,8.,vRadius);float time=uTime*.25*(2./(vRadius*.3+1.));vec2 flow=vec2(vAngle*7.+time,vRadius*2.2-time*.35);float n1=noise(flow);float n2=noise(flow*2.+.8);float n=pow(n1*.6+n2*.4,1.45);vec3 color=mix(uColorOuter,uColorMid2,smoothstep(0.,.4,r));color=mix(color,uColorMid1,smoothstep(.3,.7,r));color=mix(color,uColorHot,smoothstep(.65,.95,r));float radialGrid=pow(1.-(sin(vRadius*3.-uTime*.5)*.5+.5),4.);float angleGrid=pow(1.-(sin(vAngle*20.)*.5+.5),4.);float grid=1.-clamp(radialGrid+angleGrid,0.,1.);float brightness=(pow(1.-r,1.2)*3.+.5)*(.3+n*2.2)*(.7+grid*.8);float alpha=1.5*(.2+n*.9);alpha*=smoothstep(0.,.15,r)*(1.-smoothstep(.85,1.,r));gl_FragColor=vec4(color*brightness,clamp(alpha,0.,1.));}",
    transparent: true, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false
  }));
  disk.rotation.x = Math.PI / 3;
  disk.renderOrder = 1;
  blackHole.add(disk);

  const grid = new THREE.GridHelper(100, 50, 0x00ffff, 0x00ffff);
  grid.material.opacity = .1;
  grid.material.transparent = true;
  grid.material.blending = THREE.AdditiveBlending;
  grid.position.y = -10;
  scene.add(grid);

  const resize = () => {
    const { width, height } = element.getBoundingClientRect();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(width, height, false);
    composer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    lensingPass.uniforms.aspectRatio.value = camera.aspect;
  };
  resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(element);
  resize();

  const clock = new THREE.Clock();
  mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  render = () => {
    const reduced = mediaQuery.matches;
    const time = reduced ? 1.4 : clock.getElapsedTime();
    horizon.material.uniforms.uTime.value = time;
    horizon.material.uniforms.uCameraPosition.value.copy(camera.position);
    disk.material.uniforms.uTime.value = time;
    const isConsole = requestedSceneMode === "console";
    disk.rotation.z = reduced ? 0.03 : time * (isConsole ? .005 : .012);
    stars.rotation.y = reduced ? 0 : time * (isConsole ? .0014 : .003);
    blackHole.position.lerp(targetPosition, .026);
    blackHole.scale.lerp(targetScale, .026);
    const glitchProgress = glitchStartedAt ? (window.performance.now() - glitchStartedAt) / 1000 : 1;
    if (glitchProgress < 1 && !reduced) {
      glitchPass.enabled = true;
      glitchPass.uniforms.uIntensity.value = Math.sin(glitchProgress * Math.PI);
      glitchPass.uniforms.uTime.value = time;
    } else {
      glitchPass.enabled = false;
      glitchPass.uniforms.uIntensity.value = 0;
      glitchStartedAt = 0;
    }
    const projected = core.getWorldPosition(new THREE.Vector3()).project(camera);
    lensingPass.uniforms.blackHoleScreenPos.value.set((projected.x + 1) / 2, (projected.y + 1) / 2);
    controls.update();
    composer.render();
    if (!reduced) frameId = window.requestAnimationFrame(render);
  };
  mediaQuery.addEventListener("change", render);
  render();
});

onBeforeUnmount(() => {
  window.cancelAnimationFrame(frameId);
  resizeObserver?.disconnect();
  mediaQuery?.removeEventListener("change", render);
  controls?.dispose();
  composer?.dispose();
  renderer?.dispose();
});
</script>

<template><canvas ref="canvas" class="black-hole-canvas" aria-label="蓝紫霓虹吸积盘黑洞动画" /></template>

<style scoped>
.black-hole-canvas { display:block; width:100%; height:100%; cursor:grab; touch-action:none; }
.black-hole-canvas:active { cursor:grabbing; }
</style>
