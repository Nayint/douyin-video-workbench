/** Vector reconstruction measured against Apple's Duo HIG reference screenshots.
 * This is the animation's fixed 9:41/full-charge status, not the Mac's live device status.
 * The actual camera aperture is part of the official 3D mesh and is not redrawn here.
 */
export function drawDuoSystemUI(
  context: CanvasRenderingContext2D,
  display: 'outer' | 'inner',
  color: string,
) {
  const outer = display === 'outer';
  // HIG display crops: outer [28,16,510,742], inner [22,22,1072,754].
  const x = outer ? (485 - 28) / 510 * 800 : (1040 - 22) / 1072 * 1600;
  const timeY = outer ? 159 : 86;
  const y = outer ? 213 : 137;
  const radius = 30.5;
  const radians = (degrees: number) => degrees * Math.PI / 180;
  context.save();
  context.fillStyle = color;
  context.strokeStyle = color;
  context.textAlign = 'center';
  context.textBaseline = 'alphabetic';
  context.font = '600 26px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif';
  context.fillText('9:41', x, timeY);
  context.lineCap = 'round';
  context.lineJoin = 'round';
  // The battery is the surrounding arc; the bottom cellular dots share its circular contour.
  context.lineWidth = 4.5;
  context.beginPath(); context.arc(x, y, radius, radians(143), radians(397)); context.stroke();
  for (const angle of [56, 79, 101, 124]) {
    context.beginPath();
    context.arc(x + Math.cos(radians(angle)) * 32.2, y + Math.sin(radians(angle)) * 32.2, 3.05, 0, Math.PI * 2);
    context.fill();
  }
  // Wi-Fi is centered inside the battery ring, with matching rounded stroke terminals.
  context.lineWidth = 3.8;
  for (const arc of [15, 9]) {
    context.beginPath(); context.arc(x, y + 8, arc, radians(222), radians(318)); context.stroke();
  }
  context.beginPath(); context.arc(x, y + 6.8, 2.45, 0, Math.PI * 2); context.fill();
  context.restore();
}
