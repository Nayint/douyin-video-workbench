/** Small native WebGL renderer for our articulated glTF asset. No runtime CDN or dependencies. */
type Mat = Float32Array;
const identity=():Mat=>new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);
const multiply=(a:Mat,b:Mat):Mat=>{const out=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[c*4+r]+=a[k*4+r]*b[c*4+k];return out;};
const translate=(x:number,y:number,z:number):Mat=>{const a=identity();a[12]=x;a[13]=y;a[14]=z;return a;};
const rotateY=(t:number):Mat=>{const c=Math.cos(t),s=Math.sin(t);return new Float32Array([c,0,-s,0,0,1,0,0,s,0,c,0,0,0,0,1]);};
const rotateX=(t:number):Mat=>{const c=Math.cos(t),s=Math.sin(t);return new Float32Array([1,0,0,0,0,c,s,0,0,-s,c,0,0,0,0,1]);};
const vertex=`attribute vec3 position;attribute vec3 normal;attribute vec2 uv;uniform mat4 model;uniform mat4 projection;varying vec3 N;varying vec3 P;varying vec2 U;void main(){vec4 p=model*vec4(position,1.);P=p.xyz;N=mat3(model)*normal;U=uv;gl_Position=projection*p;}`;
const fragment=`precision highp float;varying vec3 N;varying vec3 P;varying vec2 U;uniform sampler2D innerScreen;uniform sampler2D outerScreen;uniform float kind;uniform float opacity;uniform float clock;void main(){vec3 n=normalize(N),v=normalize(-P);vec3 col;
if(kind>1.5){col=kind>2.5?texture2D(outerScreen,U).rgb:texture2D(innerScreen,U).rgb;float sheen=pow(max(dot(reflect(-v,n),normalize(vec3(-.8,1.7,2.))),0.),65.);col+=vec3(.06,.075,.09)*sheen;}
else{vec3 r=reflect(-v,n);float strip=exp(-pow((r.x+.38)/.19,2.))* .9+exp(-pow((r.x-.7)/.06,2.))*.8;float top=pow(max(dot(n,normalize(vec3(-2.,3.,4.))),0.),.7);float edge=pow(1.-abs(dot(n,v)),3.);vec3 base=kind<.5?vec3(.24,.27,.31):vec3(.012,.016,.023);col=base*(.5+.6*top)+vec3(.65,.71,.8)*(strip*.7+edge*.25);if(kind>.5)col*=.32;}
gl_FragColor=vec4(col,opacity);}`;
type Primitive={vao:WebGLBuffer[];index:WebGLBuffer;count:number;panel:string;kind:number};
type Accessor={bufferView:number;count:number;type:string;componentType:number;byteOffset?:number};
type Model={accessors:Accessor[];bufferViews:{byteOffset?:number;byteLength:number}[];nodes:{mesh:number;extras:{panel:string;surface:number}}[];meshes:{primitives:{attributes:Record<string,number>;indices:number}[]}[]};
export class FoldRenderer {
 private gl:WebGLRenderingContext;private program:WebGLProgram;private meshes:Primitive[]=[];private textures:WebGLTexture[]=[];private disposed=false;
 constructor(private canvas:HTMLCanvasElement){
  const gl=canvas.getContext('webgl',{alpha:true,antialias:true,premultipliedAlpha:false,powerPreference:'low-power'});if(!gl)throw new Error('WebGL unavailable');this.gl=gl;
  const shader=(type:number,source:string)=>{const s=gl.createShader(type)!;gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){const error=gl.getShaderInfoLog(s);gl.deleteShader(s);throw new Error(error||'Shader error');}return s;};
  const vs=shader(gl.VERTEX_SHADER,vertex),fs=shader(gl.FRAGMENT_SHADER,fragment),program=gl.createProgram()!;gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);gl.deleteShader(vs);gl.deleteShader(fs);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error('WebGL link failed');this.program=program;gl.useProgram(program);
  gl.enable(gl.DEPTH_TEST);gl.enable(gl.CULL_FACE);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
  for(let i=0;i<2;i++){const tex=gl.createTexture()!;this.textures.push(tex);gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,tex);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([8,12,20,255]));}
  gl.uniform1i(gl.getUniformLocation(program,'innerScreen'),0);gl.uniform1i(gl.getUniformLocation(program,'outerScreen'),1);
 }
 async load(signal:AbortSignal){
  const response=await fetch('/models/virallab-fold.glb',{signal});if(!response.ok)throw new Error('手机模型加载失败');const file=await response.arrayBuffer();if(this.disposed)return;
  const dv=new DataView(file);if(dv.getUint32(0,true)!==0x46546c67)throw new Error('Invalid glTF');const jsonLength=dv.getUint32(12,true);const data:Model=JSON.parse(new TextDecoder().decode(new Uint8Array(file,20,jsonLength)));const offset=20+jsonLength+8;const gl=this.gl;
  const read=(index:number)=>{const a=data.accessors[index],view=data.bufferViews[a.bufferView];return new Uint8Array(file,offset+(view.byteOffset||0)+(a.byteOffset||0),view.byteLength);};
  for(const node of data.nodes){for(const p of data.meshes[node.mesh].primitives){const buffers=[];for(const name of ['POSITION','NORMAL','TEXCOORD_0']){const buffer=gl.createBuffer()!;gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,read(p.attributes[name]),gl.STATIC_DRAW);buffers.push(buffer);}const index=gl.createBuffer()!;gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,index);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,read(p.indices),gl.STATIC_DRAW);this.meshes.push({vao:buffers,index,count:data.accessors[p.indices].count,panel:node.extras.panel,kind:node.extras.surface});}}
 }
 updateTexture(slot:number,source:HTMLCanvasElement){const gl=this.gl;gl.activeTexture(gl.TEXTURE0+slot);gl.bindTexture(gl.TEXTURE_2D,this.textures[slot]);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,source);}
 render(open:number,opacity:number,time:number,width:number,height:number){
  const gl=this.gl;gl.viewport(0,0,this.canvas.width,this.canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);if(!this.meshes.length||opacity<.001)return;
  gl.useProgram(this.program);const aspect=width/height,f=1/Math.tan(.54/2),near=.1,far=100;const projection=new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+near)/(near-far),-1,0,0,2*far*near/(near-far),0]);gl.uniformMatrix4fv(gl.getUniformLocation(this.program,'projection'),false,projection);
  const yaw=(-.13+.2*open)+Math.sin(time/3000)*.022;
  const root=multiply(translate((1-open)*1.0125,0,-6.7*Math.max(1,1.35/aspect)),multiply(rotateX(.045-.02*open),rotateY(yaw)));
  const folded=multiply(translate(0,0,.09*(1-open)),rotateY(-Math.PI*(1-open)));
  gl.uniform1f(gl.getUniformLocation(this.program,'opacity'),opacity);gl.uniform1f(gl.getUniformLocation(this.program,'clock'),time);
  for(const mesh of this.meshes){const model=mesh.panel==='right'?multiply(root,folded):root;gl.uniformMatrix4fv(gl.getUniformLocation(this.program,'model'),false,model);gl.uniform1f(gl.getUniformLocation(this.program,'kind'),mesh.kind);
   ['position','normal','uv'].forEach((name,i)=>{const loc=gl.getAttribLocation(this.program,name);gl.bindBuffer(gl.ARRAY_BUFFER,mesh.vao[i]);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,i===2?2:3,gl.FLOAT,false,0,0);});gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,mesh.index);gl.drawElements(gl.TRIANGLES,mesh.count,gl.UNSIGNED_SHORT,0);
  }
 }
 dispose(){this.disposed=true;const gl=this.gl;for(const mesh of this.meshes){for(const b of mesh.vao)gl.deleteBuffer(b);gl.deleteBuffer(mesh.index);}for(const t of this.textures)gl.deleteTexture(t);gl.deleteProgram(this.program);}
}
