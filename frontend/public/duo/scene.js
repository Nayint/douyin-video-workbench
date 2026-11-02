/** Adapted from jadon7/chuspeeism iphone-duo, MIT (2026).
 * Official Apple model remains separately licensed. See licenses/ and sources.json.
 * ViralLab: local modules, lifecycle cleanup, original screens and automatic timeline.
 */
import * as THREE from './vendor/three/build/three.module.js';
import { USDLoader } from './vendor/three/examples/jsm/loaders/USDLoader.js';
import { RoomEnvironment } from './vendor/three/examples/jsm/environments/RoomEnvironment.js';
const screenShader = `
uniform float foldAngle;
uniform vec2 uiPixel;
uniform vec4 uiFrame;
uniform vec2 uiGradient;
uniform vec3 uiReferenceEye;
uniform float creaseLight;
varying vec3 vUIPosition;
vec3 screenColor() {
  // Intersect the fixed front-view ray with the unfolded inner-screen plane.
  float depth = (0.24948 - uiReferenceEye.z) / (vUIPosition.z - uiReferenceEye.z);
  vec2 projected = uiReferenceEye.xy + (vUIPosition.xy - uiReferenceEye.xy) * depth;
  vec2 sourceUV = (projected - uiFrame.xy) / uiFrame.zw;
  #ifdef INNER_UI
    float progress = clamp(foldAngle / 1.570796327, 0.0, 1.0);
  #else
    // Anchor the image to the projected hinge-side edge of the outer screen.
    float c = cos(foldAngle), s = sin(foldAngle);
    vec2 hingeEdge = vec2(-0.23396, -0.27463 - 0.275454);
    vec2 foldedEdge = vec2(c * hingeEdge.x + s * hingeEdge.y,
      -s * hingeEdge.x + c * hingeEdge.y + 0.275454);
    float edgeDepth = (0.24948 - uiReferenceEye.z) / (foldedEdge.y - uiReferenceEye.z);
    float anchorX = uiReferenceEye.x + (foldedEdge.x - uiReferenceEye.x) * edgeDepth;
    sourceUV.x = uiGradient.x + (projected.x - anchorX) / uiFrame.z;
    float progress = clamp((3.141592654 - foldAngle) / 1.570796327, 0.0, 1.0);
  #endif
  float edge = (sourceUV.x - uiGradient.x) / (uiGradient.y - uiGradient.x);
  float motion = smoothstep(0.0, 1.0, progress);
  float blurGradient = clamp(edge, 0.0, 1.0);
  float darkenGradient = clamp((edge - 0.2) / 0.8, 0.0, 1.0);
  float effect = motion * pow(darkenGradient, 1.35);
  float radius = 72.0 * motion * pow(blurGradient, 1.35);
  vec2 aa = max(fwidth(sourceUV), uiPixel * 0.5);
  vec2 dx = dFdx(sourceUV) / uiPixel;
  vec2 dy = dFdy(sourceUV) / uiPixel;
  float baseLod = log2(max(1.0, max(length(dx), length(dy))));
  vec2 coverage = smoothstep(-aa, aa, sourceUV)
    * (1.0 - smoothstep(vec2(1.0) - aa, vec2(1.0) + aa, sourceUV));
  vec3 color = textureLod(map, clamp(sourceUV, vec2(0.0), vec2(1.0)), baseLod).rgb * coverage.x * coverage.y;
  if (radius > 0.0) {
    // Use the same mip level at zero blur, then increase it continuously.
    float lod = max(baseLod, log2(max(1.0, radius)));
    vec2 footprint = max(aa, uiPixel * radius * 0.75);
    color = vec3(0.0);
    for (int y = -2; y <= 2; y++) {
      for (int x = -2; x <= 2; x++) {
        float wx = x == 0 ? 6.0 : (abs(x) == 1 ? 4.0 : 1.0);
        float wy = y == 0 ? 6.0 : (abs(y) == 1 ? 4.0 : 1.0);
        vec2 sampleUV = sourceUV + vec2(float(x), float(y)) * uiPixel * radius;
        // Blur the image and its coverage together so color spreads into the black margin.
        vec2 coverage = smoothstep(-footprint, footprint, sampleUV)
          * (1.0 - smoothstep(vec2(1.0) - footprint, vec2(1.0) + footprint, sampleUV));
        color += textureLod(map, clamp(sampleUV, vec2(0.0), vec2(1.0)), lod).rgb
          * coverage.x * coverage.y * wx * wy / 256.0;
      }
    }
  }
  vec3 outputColor = color * (1.0 - min(1.0, effect * 2.0));
  #ifdef INNER_UI
    // A faint paired reflection across the continuous display, not a black seam.
    // Full-open reference photographs are nearly flat; the contrast rises only as it bends.
    float leftReflection = exp(-pow((vUIPosition.x + 0.065) / 0.075, 2.0));
    float rightReflection = exp(-pow((vUIPosition.x - 0.065) / 0.075, 2.0));
    float reveal = (1.0 - progress) * creaseLight;
    outputColor += (rightReflection - leftReflection) * 0.018 * reveal;
  #endif
  return outputColor;
}
`;

// The camera half stays in its original transform. Only the cover half rotates.
const foldShader = `
uniform float foldAngle;
vec2 rotateHinge(vec2 p) {
  float c = cos(foldAngle), s = sin(foldAngle);
  p.y -= 0.275454;
  return vec2(c * p.x + s * p.y, -s * p.x + c * p.y + 0.275454);
}
#ifdef FLEXIBLE_SCREEN
vec4 bendStrip(vec3 p) {
  float halfWidth = 0.35;
  if (p.x >= halfWidth) return vec4(p.x, p.z, 1.0, 0.0);
  if (p.x <= -halfWidth) return vec4(rotateHinge(p.xz), cos(foldAngle), -sin(foldAngle));
  float t = (p.x + halfWidth) / (2.0 * halfWidth);
  float t2 = t*t, t3 = t2*t;
  vec2 a = rotateHinge(vec2(-halfWidth, p.z));
  vec2 b = vec2(halfWidth, p.z);
  vec2 ta = 2.0 * halfWidth * vec2(cos(foldAngle), -sin(foldAngle));
  vec2 tb = vec2(2.0 * halfWidth, 0.0);
  vec2 point = (2.0*t3-3.0*t2+1.0)*a + (t3-2.0*t2+t)*ta + (-2.0*t3+3.0*t2)*b + (t3-t2)*tb;
  vec2 tangent = normalize((6.0*t2-6.0*t)*a + (3.0*t2-4.0*t+1.0)*ta + (-6.0*t2+6.0*t)*b + (3.0*t2-2.0*t)*tb);
  return vec4(point, tangent);
}
#endif
`;

export class DuoScene {
  constructor(canvas) {
    this.disposed=false;this.resources=new Set();
    this.scene=new THREE.Scene();
    this.camera=new THREE.PerspectiveCamera(32,1,.1,250);
    this.camera.position.set(0,0,40);
    this.renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true,powerPreference:'low-power'});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));
    this.renderer.setClearColor(0,0);
    this.renderer.toneMapping=THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure=1.18;
    const environment=new RoomEnvironment(),pmrem=new THREE.PMREMGenerator(this.renderer);
    this.environment=pmrem.fromScene(environment,.04);
    this.scene.environment=this.environment.texture;
    environment.dispose();pmrem.dispose();
    this.scene.environmentIntensity=1.35;
    this.scene.add(new THREE.HemisphereLight(0xffffff,0xb5baa8,1.8));
    const key=new THREE.DirectionalLight(0xfffcf5,2.6);key.position.set(-15,25,30);this.scene.add(key);
    const rim=new THREE.DirectionalLight(0xe8edf5,2);rim.position.set(15,5,-15);this.scene.add(rim);
    this.phone=new THREE.Group();this.scene.add(this.phone);
    this.bend={value:Math.PI};this.creaseLight={value:.2};this.screens={};
    this.uiReferenceEye=new THREE.Vector3(0,0,40);
    const inner=new THREE.Vector4(-7.89935,.34562-5.8974,15.7987,11.1035);
    const outer=new THREE.Vector4(.23396,.27173-5.8974,7.73936,11.2513).multiplyScalar((40-.24948)/(40-.825538));
    for(const kind of ['inner','outer']) {
      const texture=new THREE.CanvasTexture(document.createElement('canvas'));
      texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=Math.min(4,this.renderer.capabilities.getMaxAnisotropy());
      this.resources.add(texture);
      this.screens[kind]={material:new THREE.MeshBasicMaterial({map:texture,toneMapped:false}),frame:{value:(kind==='inner'?inner:outer).clone()},gradient:{value:new THREE.Vector2(kind==='inner'?.5:0,kind==='inner'?0:1)},pixel:{value:new THREE.Vector2(1/1600,1/1125)}};
    }
  }
  async load(signal) {
    const response=await fetch('/duo/assets/iPhone_Duo_Render.usdc',{signal});
    if(!response.ok)throw new Error('设备模型加载失败');
    const data=await response.arrayBuffer();
    if(this.disposed||signal.aborted)return;
    const model=await new Promise((resolve,reject)=>{
      new USDLoader().parse(data,'/duo/assets/',resolve,reject);
    });
    if(this.disposed||signal.aborted){disposeObject(model);return;}
    const phone=this.phone,bend=this.bend,screens=this.screens,uiReferenceEye=this.uiReferenceEye,creaseLight=this.creaseLight;
  model.scale.multiplyScalar(100);
  model.updateMatrixWorld(true);
  const count = { moving: 0, fixed: 0, flexible: 0 };
  model.traverse(object => {
    if (!object.isMesh) return;
    const geometry = object.geometry.clone().applyMatrix4(object.matrixWorld);
    geometry.translate(0, -5.8974, 0);
    let ancestor = object;
    while (ancestor && !['upTUAKvMVkPOMKq', 'SiftyleUEEZwLhF'].includes(ancestor.name)) ancestor = ancestor.parent;
    const moving = ancestor?.name === 'upTUAKvMVkPOMKq';
    const flexible = ['JnJdTkxbQgUtLwU', 'xdyyaajWsatVNxN', 'UXtsBZYlaUvHoEh', 'MvKPXGSdYDVvSpk'].includes(object.name);
    const kind = object.name === 'UXtsBZYlaUvHoEh' ? 'inner' : object.name === 'hhgAIoCGsHXeDPY' ? 'outer' : null;
    const material = kind ? screens[kind].material : object.material.clone();
    if (kind) {
      const p = geometry.attributes.position;
      const uv = new Float32Array(p.count * 2);
      for (let i = 0; i < p.count; i++) {
        uv[i * 2] = kind === 'inner' ? (p.getX(i) + 7.89935) / 15.7987 : (-.23396 - p.getX(i)) / 7.73936;
        uv[i * 2 + 1] = kind === 'inner' ? (p.getY(i) + 5.8974 - .34562) / 11.1035 : (p.getY(i) + 5.8974 - .27173) / 11.2513;
      }
      geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    }
    if (moving || flexible) {
      material.onBeforeCompile = shader => {
        shader.uniforms.foldAngle = bend;
        if (kind) {
          shader.uniforms.uiFrame = screens[kind].frame;
          shader.uniforms.uiGradient = screens[kind].gradient;
          shader.uniforms.uiReferenceEye = { value: uiReferenceEye };
          shader.uniforms.creaseLight = creaseLight;
          shader.uniforms.uiPixel = screens[kind].pixel;
          shader.fragmentShader = shader.fragmentShader.replace('#include <map_pars_fragment>', `
            #include <map_pars_fragment>
            ${kind === 'inner' ? '#define INNER_UI' : ''}
            ${screenShader}
          `).replace('#include <map_fragment>', 'diffuseColor.rgb *= screenColor();');
          shader.vertexShader = `varying vec3 vUIPosition;\n${shader.vertexShader}`;
          shader.vertexShader = shader.vertexShader.replace('#include <project_vertex>', `
            vUIPosition = transformed;
            #include <project_vertex>
          `);
        }
        shader.vertexShader = `${flexible ? '#define FLEXIBLE_SCREEN\n' : ''}${foldShader}\n${shader.vertexShader}`;
        shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>', flexible ? `
          vec4 folded = bendStrip(position);
          vec3 transformed = vec3(folded.x, position.y, folded.y);
        ` : `
          vec2 folded = rotateHinge(position.xz);
          vec3 transformed = vec3(folded.x, position.y, folded.y);
        `);
        shader.vertexShader = shader.vertexShader.replace('#include <beginnormal_vertex>', `
          vec3 objectNormal = vec3(normal);
          ${flexible ? 'vec4 strip = bendStrip(position); float a = atan(-strip.w, strip.z);' : 'float a = foldAngle;'}
          objectNormal.x = cos(a) * normal.x + sin(a) * normal.z;
          objectNormal.z = -sin(a) * normal.x + cos(a) * normal.z;
        `);
      };
      material.customProgramCacheKey = () => `${flexible ? 'fold-flexible' : 'fold-cover'}-${kind || 'body'}`;
    }
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = object.name;
    mesh.frustumCulled = false;
    phone.add(mesh);
    count[flexible ? 'flexible' : moving ? 'moving' : 'fixed']++;
  });

    this.sourceModel=model;
    this.stats={...count,total:phone.children.length};
    this.canvasReady=true;
    this.renderer.compile(this.scene,this.camera);
  }
  updateTexture(slot,canvas) {
    if(this.disposed)return;
    const screen=this.screens[slot===0?'inner':'outer'];
    screen.material.map.image=canvas;screen.material.map.needsUpdate=true;
    screen.pixel.value.set(1/canvas.width,1/canvas.height);
  }
  render(open,opacity,time,width,height) {
    if(this.disposed)return;
    if(this.width!==width||this.height!==height){
      this.width=width;this.height=height;this.renderer.setSize(width,height,false);
      this.camera.aspect=width/height;
      const units=Math.min(width/21,height/13.4,43);
      this.camera.fov=THREE.MathUtils.radToDeg(2*Math.atan(height/units/2/40));
      this.camera.updateProjectionMatrix();
    }
    this.bend.value=(1-open)*Math.PI;
    this.phone.position.x=-4.0*(1-open);
    const hingeReveal=Math.sin(Math.PI*open);
    this.phone.rotation.x=.15*hingeReveal;
    this.phone.rotation.y=.025+.10*hingeReveal+Math.sin(time/3200)*.008;
    this.creaseLight.value=.20+.80*hingeReveal;
    this.screens.outer.material.color.setScalar(open>.999?0:1);
    this.renderer.domElement.style.opacity=String(opacity);
    this.renderer.render(this.scene,this.camera);
  }
  dispose() {
    if(this.disposed)return;this.disposed=true;
    disposeObject(this.phone);
    if(this.sourceModel)disposeObject(this.sourceModel);
    for(const screen of Object.values(this.screens))screen.material.dispose();
    for(const resource of this.resources)resource.dispose();
    this.environment.dispose();this.renderer.dispose();
  }
}
function disposeObject(root){
  const materials=new Set(),textures=new Set(),geometries=new Set();
  root.traverse(object=>{if(object.geometry)geometries.add(object.geometry);for(const material of Array.isArray(object.material)?object.material:object.material?[object.material]:[]){materials.add(material);for(const value of Object.values(material))if(value?.isTexture)textures.add(value);}});
  for(const resource of [...textures,...materials,...geometries])resource.dispose();
}
