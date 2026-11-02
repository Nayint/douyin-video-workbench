/** Typed boundary around the locally vendored MIT fold preview and separately sourced model. */
interface DuoScene {
  load(signal: AbortSignal): Promise<void>;
  updateTexture(slot: number, canvas: HTMLCanvasElement): void;
  render(open: number, opacity: number, time: number, width: number, height: number): void;
  dispose(): void;
}
export class DuoRenderer {
  private scene?: DuoScene;
  private disposed = false;
  constructor(private canvas: HTMLCanvasElement) {}
  async load(signal: AbortSignal) {
    const moduleURL = '/duo/scene.js?v=20261019-details';
    const module = await import(/* @vite-ignore */ moduleURL) as {
      DuoScene: new (canvas: HTMLCanvasElement) => DuoScene;
    };
    if (this.disposed || signal.aborted) return;
    this.scene = new module.DuoScene(this.canvas);
    await this.scene.load(signal);
  }
  updateTexture(slot: number, canvas: HTMLCanvasElement) {
    this.scene?.updateTexture(slot, canvas);
  }
  render(open: number, opacity: number, time: number, width: number, height: number) {
    this.scene?.render(open, opacity, time, width, height);
  }
  dispose() {
    this.disposed = true;
    this.scene?.dispose();
  }
}
