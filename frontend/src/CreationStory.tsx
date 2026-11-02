import { useEffect, useRef, useState } from 'react';
import { DuoRenderer } from './DuoRenderer';
import { StoryScreens, smooth } from './StoryScreens';

const PERIOD=13000;
/** One physical model, an outer video screen, and a continuous handoff into the inner display. */
export function CreationStory(){
 const root=useRef<HTMLDivElement>(null),canvas=useRef<HTMLCanvasElement>(null),intro=useRef<HTMLDivElement>(null);
 const elapsed=useRef(0);const [unavailable,setUnavailable]=useState(false);
 useEffect(()=>{
  const node=canvas.current!,host=root.current!,title=intro.current!;const controller=new AbortController();let renderer:DuoRenderer;
  try{renderer=new DuoRenderer(node);}catch{setUnavailable(true);return;}
  const screens=new StoryScreens(),preference=matchMedia('(prefers-reduced-motion: reduce)');
  let disposed=false,ready=false,frame=0,previous=0,inView=true,width=800,height=410,lastTexture=-100,lastDark=false;
  const draw=()=>{
   const t=preference.matches?0:elapsed.current%PERIOD,dark=document.documentElement.dataset.theme==='dark';
   // Finish returning before the loop boundary, so both sides share the same held pose.
   const introExit=smooth(850,1500,t)*(1-smooth(12000,12800,t));
   const alpha=smooth(1000,1700,t)*(1-smooth(11900,12800,t));
   title.style.opacity=String(1-introExit);
   title.style.transform=`translateY(${-12*introExit}px)`;
   if(ready&&(Math.abs(t-lastTexture)>33||t<lastTexture||dark!==lastDark)){screens.draw(t,dark);renderer.updateTexture(0,screens.inner);renderer.updateTexture(1,screens.outer);lastTexture=t;lastDark=dark;}
   const open=smooth(5200,7700,t)*(1-smooth(10900,12100,t));
   renderer.render(open,ready?alpha:0,t,width,height);
   host.dataset.storyPhase=t<1000?'intro':t<5200?'video':t<8200?'unfold':t<10900?'copy':'close';
  };
  const active=()=>!preference.matches&&inView&&!document.hidden&&ready;
  const tick=(now:number)=>{frame=0;if(disposed)return;if(active()){if(previous)elapsed.current+=Math.min(now-previous,50);previous=now;draw();frame=requestAnimationFrame(tick);}else{previous=0;draw();}};
  const wake=()=>{if(!disposed&&!frame){previous=0;frame=requestAnimationFrame(tick);}};
  renderer.load(controller.signal).then(()=>{if(!disposed&&!controller.signal.aborted){ready=true;host.dataset.model="official-duo";wake();}}).catch(error=>{if(!disposed&&error.name!=='AbortError'){setUnavailable(true);}});
  const resize=()=>{const rect=node.getBoundingClientRect();width=rect.width;height=rect.height;const dpr=Math.min(devicePixelRatio||1,2);node.width=Math.round(width*dpr);node.height=Math.round(height*dpr);draw();};
  const size=new ResizeObserver(resize);size.observe(node);const view=new IntersectionObserver(([entry])=>{inView=entry.isIntersecting;wake();},{threshold:.15});view.observe(host);
  const theme=new MutationObserver(draw);theme.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
  preference.addEventListener('change',wake);document.addEventListener('visibilitychange',wake);resize();wake();
  return()=>{disposed=true;controller.abort();cancelAnimationFrame(frame);size.disconnect();view.disconnect();theme.disconnect();preference.removeEventListener('change',wake);document.removeEventListener('visibilitychange',wake);renderer.dispose();};
 },[]);
 return <div ref={root} className={`continuous-story physical-fold-story${unavailable?' fold-unavailable':''}`}>
  <div ref={intro} className="fold-intro"><span>ViralLab · 为创作而生</span><h2>好内容，<br/><em>从这里开始。</em></h2><p>把灵感留下，把表达想透。<br/>让下一条视频，更像你。</p></div>
  <canvas ref={canvas} className="story-canvas" role="img" aria-label="真实设备模型：外屏播放原创带货画面和逐句字幕，屏幕展开时渐进虚化，字幕整理为内屏文案" />
  {unavailable&&<span className="fold-fallback-note">三维展示暂未加载，请刷新页面重试</span>}
 </div>;
}
