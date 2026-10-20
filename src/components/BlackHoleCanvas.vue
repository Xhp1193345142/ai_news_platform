<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";

const BLACK_HOLE_RADIUS = 1.3;
const DISK_INNER_RADIUS = BLACK_HOLE_RADIUS + 0.2;
// Keep the approved source pose, with a slightly broader outer edge so the
// accretion disk reads as a long, cinematic band across the left visual field.
const DISK_OUTER_RADIUS = 9.5;
const DISK_TILT_ANGLE = Math.PI / 3;

const canvas = ref(null);
const props = defineProps({ sceneMode: { type: String, default: "auth" } });
let renderer; let composer; let controls; let resizeObserver; let mediaQuery; let frameId;
let render; let blackHole; let authScreenNdcX = 0; let canvasWidth = 0; let canvasHeight = 0;
let currentViewOffset = 0; let targetViewOffset = 0;
let glitchPass; let glitchStartedAt = 0; let requestedSceneMode = props.sceneMode;

function setSceneMode(mode) {
  targetViewOffset = mode === "console" ? authScreenNdcX * canvasWidth * .5 : 0;
  if (mediaQuery?.matches) currentViewOffset = targetViewOffset;
}
watch(() => props.sceneMode, (mode) => { requestedSceneMode = mode; setSceneMode(mode); });
function triggerGlitch() { if (glitchPass) { glitchStartedAt = performance.now(); glitchPass.enabled = true; } }
defineExpose({ triggerGlitch });

const lensingShader = {
  uniforms: {
    tDiffuse: { value: null }, blackHoleScreenPos: { value: new THREE.Vector2(.5, .5) },
    lensingStrength: { value: .12 }, lensingRadius: { value: .3 }, aspectRatio: { value: 1 },
    chromaticAberration: { value: .015 }, scanlineIntensity: { value: .15 }, vignetteDarkness: { value: .8 }
  },
  vertexShader: `varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
  fragmentShader: `
    uniform sampler2D tDiffuse;uniform vec2 blackHoleScreenPos;uniform float lensingStrength,lensingRadius,aspectRatio,chromaticAberration,scanlineIntensity,vignetteDarkness;varying vec2 vUv;
    void main(){vec2 screenPos=vUv;vec2 toCenter=screenPos-blackHoleScreenPos;toCenter.x*=aspectRatio;float dist=length(toCenter);float distortionAmount=clamp(lensingStrength/(dist*dist+.003),0.,.7);float falloff=smoothstep(lensingRadius,lensingRadius*.3,dist);distortionAmount*=falloff;vec2 offset=normalize(toCenter)*distortionAmount;offset.x/=aspectRatio;float r=texture2D(tDiffuse,screenPos-offset*(1.+chromaticAberration)).r;float g=texture2D(tDiffuse,screenPos-offset).g;float b=texture2D(tDiffuse,screenPos-offset*(1.-chromaticAberration)).b;vec3 finalColor=vec3(r,g,b);float scanline=sin(vUv.y*800.)*.5+.5;finalColor-=scanline*scanlineIntensity*finalColor;float vignette=length(vUv-vec2(.5));finalColor*=1.-vignette*vignetteDarkness;gl_FragColor=vec4(finalColor,1.);}`
};
const glitchShader = {
  uniforms: { tDiffuse: { value: null }, uIntensity: { value: 0 }, uTime: { value: 0 } },
  vertexShader: `varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
  fragmentShader: `uniform sampler2D tDiffuse;uniform float uIntensity,uTime;varying vec2 vUv;float random(vec2 p){return fract(sin(dot(p.xy,vec2(12.9898,78.233)))*43758.5453);}void main(){vec2 uv=vUv;float rOffset=(random(uv+uTime*.4)-.5)*.05*uIntensity;float gOffset=(random(uv+uTime*.6)-.5)*.05*uIntensity;vec3 finalColor=vec3(texture2D(tDiffuse,uv+vec2(rOffset,0.)).r,texture2D(tDiffuse,uv+vec2(gOffset,0.)).g,texture2D(tDiffuse,uv).b);float lineY=floor(uv.y*50.+uTime*20.);float lineShift=(random(vec2(lineY,uTime))-.5)*.1*uIntensity;if(random(vec2(lineY,uTime*2.))>.97-uIntensity*.3)finalColor=texture2D(tDiffuse,vec2(uv.x+lineShift,uv.y)).rgb;vec3 originalColor=texture2D(tDiffuse,vUv).rgb;gl_FragColor=vec4(mix(originalColor,finalColor,uIntensity),1.);}`
};

onMounted(() => {
  const element = canvas.value;
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x020104, .035);
  const camera = new THREE.PerspectiveCamera(60, 1, .1, 4000);
  camera.position.set(-6.5, 5, 6.5);

  renderer = new THREE.WebGLRenderer({ canvas: element, antialias: true, powerPreference: "high-performance" });
  renderer.setClearColor(0x020104, 1);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(1, 1), .6, .7, .2));
  const lensingPass = new ShaderPass(lensingShader);
  composer.addPass(lensingPass);
  glitchPass = new ShaderPass(glitchShader);
  glitchPass.enabled = false;
  composer.addPass(glitchPass);

  controls = new OrbitControls(camera, element);
  controls.enableDamping = true; controls.dampingFactor = .035; controls.rotateSpeed = .4;
  controls.autoRotate = false; controls.autoRotateSpeed = .1; controls.target.set(0, 0, 0);
  controls.minDistance = 2.5; controls.maxDistance = 100; controls.enablePan = false; controls.update();

  const starCount = 150000;
  const starGeometry = new THREE.BufferGeometry();
  const starPositions = new Float32Array(starCount * 3);
  const starColors = new Float32Array(starCount * 3);
  const starSizes = new Float32Array(starCount);
  const starTwinkle = new Float32Array(starCount);
  const palette = [new THREE.Color(0x00ffff), new THREE.Color(0xff00ff), new THREE.Color(0x8a2be2), new THREE.Color(0x00ff7f), new THREE.Color(0xccddff)];
  for (let i = 0; i < starCount; i += 1) {
    const i3 = i * 3; const phi = Math.acos(-1 + (2 * i) / starCount); const theta = Math.sqrt(starCount * Math.PI) * phi; const radius = Math.cbrt(Math.random()) * 2000 + 100;
    starPositions[i3] = radius * Math.sin(phi) * Math.cos(theta); starPositions[i3 + 1] = radius * Math.sin(phi) * Math.sin(theta); starPositions[i3 + 2] = radius * Math.cos(phi);
    const color = palette[Math.floor(Math.random() * palette.length)].clone().multiplyScalar(Math.random() * .7 + .3);
    starColors[i3] = color.r; starColors[i3 + 1] = color.g; starColors[i3 + 2] = color.b; starSizes[i] = THREE.MathUtils.randFloat(.8, 2.5); starTwinkle[i] = Math.random() * Math.PI * 2;
  }
  starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
  starGeometry.setAttribute("color", new THREE.BufferAttribute(starColors, 3));
  starGeometry.setAttribute("size", new THREE.BufferAttribute(starSizes, 1));
  starGeometry.setAttribute("twinkle", new THREE.BufferAttribute(starTwinkle, 1));
  const starMaterial = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uPixelRatio: { value: renderer.getPixelRatio() } },
    vertexShader: `uniform float uTime,uPixelRatio;attribute float size,twinkle;varying vec3 vColor;varying float vTwinkle;void main(){vColor=color;vTwinkle=sin(uTime*2.5+twinkle)*.5+.5;vec4 mvPosition=modelViewMatrix*vec4(position,1.);gl_PointSize=size*uPixelRatio*(300./-mvPosition.z);gl_Position=projectionMatrix*mvPosition;}`,
    fragmentShader: `varying vec3 vColor;varying float vTwinkle;void main(){float dist=distance(gl_PointCoord,vec2(.5));float cross=abs(gl_PointCoord.x-.5)+abs(gl_PointCoord.y-.5);if(cross>.5)discard;float alpha=1.-smoothstep(0.,.5,dist);alpha*=.2+vTwinkle*.8;gl_FragColor=vec4(vColor,alpha);}`,
    transparent: true, vertexColors: true, blending: THREE.AdditiveBlending, depthWrite: false
  });
  const stars = new THREE.Points(starGeometry, starMaterial); scene.add(stars);

  // A sparse, cool-toned galactic plane sits behind the source star field.
  // It is intentionally broad and dim so the event horizon remains the focus.
  const galaxyCount = 60000;
  const galaxyGeometry = new THREE.BufferGeometry();
  const galaxyPositions = new Float32Array(galaxyCount * 3);
  const galaxyColors = new Float32Array(galaxyCount * 3);
  const galaxySizes = new Float32Array(galaxyCount);
  const galaxyForward = new THREE.Vector3();
  const galaxyRight = new THREE.Vector3();
  const galaxyUp = new THREE.Vector3();
  camera.getWorldDirection(galaxyForward);
  galaxyRight.crossVectors(galaxyForward, camera.up).normalize();
  galaxyUp.crossVectors(galaxyRight, galaxyForward).normalize();
  const galaxyCenter = camera.position.clone().addScaledVector(galaxyForward, 1350);
  for (let i = 0; i < galaxyCount; i += 1) {
    const i3 = i * 3;
    const horizontal = (Math.random() - .5) * 3600;
    // In screen space: left-top → right-bottom, with a deliberately steep
    // diagonal so the galaxy reads as a vertical background ribbon.
    const vertical = horizontal * -.58 + (Math.random() + Math.random() + Math.random() + Math.random() - 2) * 175;
    const depth = (Math.random() - .5) * 360;
    const point = galaxyCenter.clone().addScaledVector(galaxyRight, horizontal).addScaledVector(galaxyUp, vertical).addScaledVector(galaxyForward, depth);
    galaxyPositions[i3] = point.x; galaxyPositions[i3 + 1] = point.y; galaxyPositions[i3 + 2] = point.z;
    const color = new THREE.Color().setHSL(.56 + Math.random() * .18, .8, .56 + Math.random() * .24);
    galaxyColors[i3] = color.r; galaxyColors[i3 + 1] = color.g; galaxyColors[i3 + 2] = color.b;
    galaxySizes[i] = THREE.MathUtils.randFloat(3.5, 10.5);
  }
  galaxyGeometry.setAttribute("position", new THREE.BufferAttribute(galaxyPositions, 3));
  galaxyGeometry.setAttribute("color", new THREE.BufferAttribute(galaxyColors, 3));
  galaxyGeometry.setAttribute("size", new THREE.BufferAttribute(galaxySizes, 1));
  const galaxyMaterial = new THREE.ShaderMaterial({
    uniforms: { uPixelRatio: { value: renderer.getPixelRatio() } },
    vertexShader: `uniform float uPixelRatio;attribute float size;varying vec3 vColor;void main(){vColor=color;vec4 mvPosition=modelViewMatrix*vec4(position,1.);gl_PointSize=size*uPixelRatio*(360./-mvPosition.z);gl_Position=projectionMatrix*mvPosition;}`,
    fragmentShader: `varying vec3 vColor;void main(){float d=distance(gl_PointCoord,vec2(.5));float alpha=1.-smoothstep(.04,.5,d);gl_FragColor=vec4(vColor,alpha*.52);}`,
    transparent: true, vertexColors: true, blending: THREE.AdditiveBlending, depthWrite: false
  });
  const galacticBand = new THREE.Points(galaxyGeometry, galaxyMaterial); scene.add(galacticBand);

  // Keep the source scene intact, only offsetting its shared group to leave the login card's right third clear.
  blackHole = new THREE.Group();
  const forward = new THREE.Vector3(); const screenRight = new THREE.Vector3(); const screenUp = new THREE.Vector3();
  camera.getWorldDirection(forward); screenRight.crossVectors(forward, camera.up).normalize(); screenUp.crossVectors(screenRight, forward).normalize();
  blackHole.position.addScaledVector(screenRight, -1.72).addScaledVector(screenUp, .92); blackHole.scale.setScalar(.64);
  scene.add(blackHole);

  const eventHorizonMat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uCameraPosition: { value: camera.position.clone() } },
    vertexShader: `varying vec3 vNormal,vPosition;void main(){vNormal=normalize(normalMatrix*normal);vPosition=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader: `uniform float uTime;uniform vec3 uCameraPosition;varying vec3 vNormal,vPosition;void main(){vec3 viewDirection=normalize(uCameraPosition-vPosition);float fresnel=pow(1.-abs(dot(vNormal,viewDirection)),2.);vec3 glowColor=vec3(0.,1.,.8);float pulse=sin(uTime*3.5)*.2+.8;gl_FragColor=vec4(glowColor*fresnel*pulse,fresnel*.5);}`,
    transparent: true, blending: THREE.AdditiveBlending, side: THREE.BackSide
  });
  const eventHorizon = new THREE.Mesh(new THREE.SphereGeometry(BLACK_HOLE_RADIUS * 1.05, 128, 64), eventHorizonMat); blackHole.add(eventHorizon);
  const core = new THREE.Mesh(new THREE.SphereGeometry(BLACK_HOLE_RADIUS, 128, 64), new THREE.MeshBasicMaterial({ color: 0x000000 })); core.renderOrder = 0; blackHole.add(core);
  const diskMaterial = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uColorHot: { value: new THREE.Color(0xffffff) }, uColorMid1: { value: new THREE.Color(0xff00ff) }, uColorMid2: { value: new THREE.Color(0x00ffff) }, uColorOuter: { value: new THREE.Color(0x3939f5) }, uNoiseScale: { value: 3.5 }, uFlowSpeed: { value: .25 }, uDensity: { value: 1.5 } },
    vertexShader: `varying vec2 vUv;varying float vRadius,vAngle;void main(){vUv=uv;vRadius=length(position.xy);vAngle=atan(position.y,position.x);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader: `
      uniform float uTime,uNoiseScale,uFlowSpeed,uDensity;uniform vec3 uColorHot,uColorMid1,uColorMid2,uColorOuter;varying vec2 vUv;varying float vRadius,vAngle;
      vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}
      float snoise(vec3 v){const vec2 C=vec2(1./6.,1./3.);const vec4 D=vec4(0.,.5,1.,2.);vec3 i=floor(v+dot(v,C.yyy));vec3 x0=v-i+dot(i,C.xxx);vec3 g=step(x0.yzx,x0.xyz);vec3 l=1.-g;vec3 i1=min(g.xyz,l.zxy);vec3 i2=max(g.xyz,l.zxy);vec3 x1=x0-i1+C.xxx;vec3 x2=x0-i2+C.yyy;vec3 x3=x0-D.yyy;i=mod289(i);vec4 p=permute(permute(permute(i.z+vec4(0.,i1.z,i2.z,1.))+i.y+vec4(0.,i1.y,i2.y,1.))+i.x+vec4(0.,i1.x,i2.x,1.));float n_=0.142857142857;vec3 ns=n_*D.wyz-D.xzx;vec4 j=p-49.*floor(p*ns.z*ns.z);vec4 x_=floor(j*ns.z);vec4 y_=floor(j-7.*x_);vec4 x=x_*ns.x+ns.yyyy;vec4 y=y_*ns.x+ns.yyyy;vec4 h=1.-abs(x)-abs(y);vec4 b0=vec4(x.xy,y.xy);vec4 b1=vec4(x.zw,y.zw);vec4 s0=floor(b0)*2.+1.;vec4 s1=floor(b1)*2.+1.;vec4 sh=-step(h,vec4(0.));vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;vec3 p0=vec3(a0.xy,h.x);vec3 p1=vec3(a0.zw,h.y);vec3 p2=vec3(a1.xy,h.z);vec3 p3=vec3(a1.zw,h.w);vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);m=m*m;return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));}
      void main(){float normalizedRadius=smoothstep(1.5,9.5,vRadius);float timeOffset=uTime*uFlowSpeed*(2./(vRadius*.3+1.));vec2 noiseUv=vec2(vAngle*2.+timeOffset,vRadius*.5);float noiseVal1=snoise(vec3(noiseUv*uNoiseScale,uTime*.15));float noiseVal2=snoise(vec3(noiseUv*uNoiseScale*2.+.8,uTime*.22));float noiseVal=(noiseVal1*.6+noiseVal2*.4+1.)*.5;vec3 color=mix(uColorOuter,uColorMid2,smoothstep(0.,.4,normalizedRadius));color=mix(color,uColorMid1,smoothstep(.3,.7,normalizedRadius));color=mix(color,uColorHot,smoothstep(.65,.95,normalizedRadius));float brightness=pow(1.-normalizedRadius,1.2)*3.+.5;brightness*=.3+noiseVal*2.2;float radialGrid=1.-(sin(vRadius*3.-uTime*.5)*.5+.5);radialGrid=pow(radialGrid,4.);float angleGrid=1.-(sin(vAngle*20.)*.5+.5);angleGrid=pow(angleGrid,4.);float grid=1.-clamp(radialGrid+angleGrid,0.,1.);brightness*=.7+grid*.8;float alpha=uDensity*(.2+noiseVal*.9);alpha*=smoothstep(0.,.15,normalizedRadius);alpha*=1.-smoothstep(.85,1.,normalizedRadius);gl_FragColor=vec4(color*brightness,clamp(alpha,0.,1.));}`,
    transparent: true, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending
  });
  const disk = new THREE.Mesh(new THREE.RingGeometry(DISK_INNER_RADIUS, DISK_OUTER_RADIUS, 256, 128), diskMaterial); disk.rotation.x = DISK_TILT_ANGLE; disk.renderOrder = 1; blackHole.add(disk);
  const grid = new THREE.GridHelper(100, 50, 0x00ffff, 0x00ffff); grid.material.opacity = .1; grid.material.transparent = true; grid.material.blending = THREE.AdditiveBlending; grid.position.y = -10; scene.add(grid);

  const applyViewOffset = () => { if (!canvasWidth || !canvasHeight) return; if (Math.abs(currentViewOffset) < .25) { camera.clearViewOffset(); } else { camera.setViewOffset(canvasWidth, canvasHeight, currentViewOffset, 0, canvasWidth, canvasHeight); } camera.updateProjectionMatrix(); };
  const resize = () => { const { width, height } = element.getBoundingClientRect(); if (!width || !height) return; canvasWidth = width; canvasHeight = height; camera.clearViewOffset(); camera.aspect = width / height; camera.updateProjectionMatrix(); authScreenNdcX = blackHole.getWorldPosition(new THREE.Vector3()).project(camera).x; targetViewOffset = requestedSceneMode === "console" ? authScreenNdcX * width * .5 : 0; applyViewOffset(); renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5)); renderer.setSize(width, height, false); composer.setSize(width, height); starMaterial.uniforms.uPixelRatio.value = renderer.getPixelRatio(); galaxyMaterial.uniforms.uPixelRatio.value = renderer.getPixelRatio(); lensingPass.uniforms.aspectRatio.value = camera.aspect; };
  resizeObserver = new ResizeObserver(resize); resizeObserver.observe(element); resize();
  const clock = new THREE.Clock(); const screenPosition = new THREE.Vector3(); mediaQuery = matchMedia("(prefers-reduced-motion: reduce)");
  render = () => { const reduced = mediaQuery.matches; const elapsedTime = reduced ? 0 : clock.getElapsedTime(); const deltaTime = clock.getDelta(); diskMaterial.uniforms.uTime.value = elapsedTime; starMaterial.uniforms.uTime.value = elapsedTime; eventHorizonMat.uniforms.uTime.value = elapsedTime; eventHorizonMat.uniforms.uCameraPosition.value.copy(camera.position); if (glitchPass.enabled) { const progress = Math.min((performance.now() - glitchStartedAt) / 1000, 1); glitchPass.uniforms.uIntensity.value = reduced ? 0 : Math.sin(progress * Math.PI); glitchPass.uniforms.uTime.value = elapsedTime; if (progress >= 1) { glitchPass.enabled = false; glitchPass.uniforms.uIntensity.value = 0; } } if (!reduced) { currentViewOffset += (targetViewOffset - currentViewOffset) * .12; stars.rotation.y += deltaTime * .003; disk.rotation.z += deltaTime * .005; } applyViewOffset(); screenPosition.copy(core.getWorldPosition(new THREE.Vector3())).project(camera); lensingPass.uniforms.blackHoleScreenPos.value.set((screenPosition.x + 1) / 2, (screenPosition.y + 1) / 2); controls.update(); composer.render(deltaTime); if (!reduced) frameId = requestAnimationFrame(render); };
  mediaQuery.addEventListener("change", render); render();
});
onBeforeUnmount(() => { cancelAnimationFrame(frameId); resizeObserver?.disconnect(); mediaQuery?.removeEventListener("change", render); controls?.dispose(); composer?.dispose(); renderer?.dispose(); });
</script>

<template><canvas ref="canvas" class="black-hole-canvas" aria-label="赛博朋克黑洞与旋转吸积盘" /></template>

<style scoped>
.black-hole-canvas { display:block; width:100%; height:100%; cursor:grab; touch-action:none; }
.black-hole-canvas:active { cursor:grabbing; }
</style>
