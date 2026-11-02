import { drawDuoSystemUI } from './DuoSystemUI';

export const smooth = (a: number, b: number, t: number) => {
  const p = Math.max(0, Math.min(1, (t - a) / (b - a)));
  return p * p * p * (p * (p * 6 - 15) + 10);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const lines = ['先看这个小细节。', '拿在手里，再仔细看看。', '把喜欢的理由，讲清楚。'];
const starts = [1500, 2800, 4100];
const FONT = '-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif';

/** Original imagery and identical subtitle strings on the outside and inside displays. */
export class StoryScreens {
  readonly outer = document.createElement('canvas');
  readonly inner = document.createElement('canvas');
  private backdrop = document.createElement('canvas');
  private image = new Image();
  constructor() {
    this.outer.width = 800; this.outer.height = 1163;
    this.inner.width = 1600; this.inner.height = 1125;
    this.backdrop.width = 1600; this.backdrop.height = 1125;
    this.image.src = '/visuals/creator-scenes-v1.png';
  }
  private text(c: CanvasRenderingContext2D, text: string, x: number, y: number, size: number, weight = 500) {
    c.font = `${weight} ${size}px ${FONT}`; c.fillText(text, x, y);
  }
  private picture(c: CanvasRenderingContext2D, w: number, h: number, t: number) {
    c.fillStyle = '#14243b'; c.fillRect(0, 0, w, h);
    if (!this.image.complete || !this.image.naturalWidth) return;
    const shot = t < 2800 ? 0 : t < 4100 ? 1 : 2;
    const paint = (index: number, alpha: number) => {
      const panel = this.image.naturalWidth / 3, ih = this.image.naturalHeight;
      let sh = ih / (1 + smooth(starts[index], starts[index] + 1900, t) * .075), sw = sh * w / h;
      if (sw > panel) { sw = panel; sh = sw * h / w; }
      c.save(); c.globalAlpha = alpha;
      c.drawImage(this.image, index * panel + (panel - sw) / 2, (ih - sh) * (index === 0 ? .08 : .45), sw, sh, 0, 0, w, h);
      c.restore();
    };
    if (shot) paint(shot - 1, 1);
    paint(shot, shot ? smooth(starts[shot], starts[shot] + 160, t) : 1);
  }
  draw(t: number, dark: boolean) {
    const out = this.outer.getContext('2d')!, inside = this.inner.getContext('2d')!, bg = this.backdrop.getContext('2d')!;
    this.picture(out, 800, 1163, t); this.picture(bg, 1600, 1125, t);
    const shot = t < 2800 ? 0 : t < 4100 ? 1 : 2;
    const pop = smooth(starts[shot] + 20, starts[shot] + 180, t);
    const shade = out.createLinearGradient(0, 670, 0, 1163); shade.addColorStop(0, '#03081200'); shade.addColorStop(1, '#030812cc');
    out.fillStyle = shade; out.fillRect(0, 670, 800, 493); drawDuoSystemUI(out, 'outer', '#ffffffed');
    out.save(); out.globalAlpha = pop; out.fillStyle = '#ffffff'; out.textAlign = 'center';
    out.shadowColor = '#0009'; out.shadowBlur = 10; out.shadowOffsetY = 3;
    this.text(out, lines[shot], 400, 1012 + (1 - pop) * 12, 43, 500); out.restore();

    // Apple-style folding blur lives in the upstream screen shader. This layer resolves into clear copy.
    const paper = smooth(5950, 8050, t);
    inside.drawImage(this.backdrop, 0, 0);
    inside.save(); inside.globalAlpha = paper;
    inside.filter = `blur(${paper * 24}px) saturate(.85)`;
    inside.drawImage(this.backdrop, -14, -14, 1628, 1153); inside.filter = 'none';
    // A light frosted reading surface keeps the final text distinct from the source image.
    const tint = inside.createLinearGradient(0, 0, 1600, 1125);
    tint.addColorStop(0, dark ? '#e9f0f6e8' : '#f8fafde8');
    tint.addColorStop(1, dark ? '#cfdeebe3' : '#eaf1f8ed');
    inside.fillStyle = tint; inside.fillRect(0, 0, 1600, 1125);
    inside.restore();
    const chrome = smooth(7100, 8350, t);
    inside.save(); inside.globalAlpha = chrome; inside.textAlign = 'left';
    inside.fillStyle = '#647b94'; this.text(inside, 'ViralLab  /  创作文案', 112, 132, 27, 500);
    inside.fillStyle = '#152637'; this.text(inside, '把喜欢的理由，讲清楚。', 112, 265, 59, 600);
    inside.fillStyle = '#1d426c18'; inside.fillRect(112, 319, 1376, 1.5);
    inside.fillStyle = '#7b8b9d'; this.text(inside, '从画面里的细节，到自己的表达。', 112, 1012, 26, 400);
    inside.restore();
    lines.forEach((line, i) => {
      const p = smooth(5850 + i * 140, 8200 + i * 140, t);
      const visible = mix(i === shot ? pop : 0, 1, smooth(5650, 6500, t));
      const x = mix(800, 112, p) + Math.sin(Math.PI * p) * 65;
      const y = mix(960 + (i - 1) * 65 * smooth(5650, 6500, t), 455 + i * 121, p);
      const size = mix(44, 44, p);
      inside.save(); inside.globalAlpha = visible; inside.font = `500 ${size}px ${FONT}`;
      const left = x - inside.measureText(line).width / 2 * (1 - p);
      inside.fillStyle = p < .65 ? '#ffffff' : '#31445a';
      if (p < .65) { inside.shadowColor = '#03101a88'; inside.shadowBlur = 8; }
      inside.textAlign = 'left'; inside.fillText(line, left, y); inside.restore();
    });
    // Source imagery stays inside the device and shares the material's subtle lens border.
    inside.save(); inside.globalAlpha = smooth(7800, 8750, t);
    inside.shadowColor = '#1c385b1c'; inside.shadowBlur = 30; inside.shadowOffsetY = 14;
    inside.fillStyle = '#eaf0f9'; inside.beginPath(); inside.roundRect(1070, 393, 394, 506, 28); inside.fill(); inside.shadowBlur = 0; inside.shadowOffsetY = 0;
    inside.beginPath(); inside.roundRect(1070, 393, 394, 506, 28); inside.clip();
    if (this.image.complete && this.image.naturalWidth) { const pw = this.image.naturalWidth / 3; inside.drawImage(this.image, pw * 2, 0, pw, this.image.naturalHeight, 1070, 393, 394, 788); }
    const lens = inside.createLinearGradient(1070, 393, 1464, 899); lens.addColorStop(0, '#ffffff35'); lens.addColorStop(.4, '#ffffff00'); lens.addColorStop(1, '#b7d8f322');
    inside.fillStyle = lens; inside.fillRect(1070, 393, 394, 506); inside.restore();
    inside.save(); inside.globalAlpha = chrome; inside.strokeStyle = '#ffffff8a'; inside.lineWidth = 1.5; inside.beginPath(); inside.roundRect(1071, 394, 392, 504, 28); inside.stroke(); inside.restore();
    inside.save(); inside.globalAlpha = smooth(6400, 7850, t);
    drawDuoSystemUI(inside, 'inner', paper > .6 ? '#273b50' : '#ffffffed');
    inside.restore();
  }
}
