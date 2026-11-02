import { useLayoutEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

export type CardOrigin = { element: HTMLElement; rect: DOMRect; focus: HTMLElement | null };

/** Keeps the collection mounted while its card expands into a focused research sheet. */
export function ResearchDialog({ origin, onClose, children, label = "案例研究详情", closeLabel = "关闭案例详情" }: {
  label?: string;
  closeLabel?: string;
  origin: CardOrigin | null;
  onClose: () => void;
  children: (close: () => void) => ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const sheet = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const preview = useRef<HTMLDivElement>(null);
  const closing = useRef(false);
  const flight = useRef<HTMLImageElement | null>(null);
  const destination = useRef<HTMLImageElement | null>(null);
  const originalVisibility = useRef("");
  const observer = useRef<MutationObserver | null>(null);
  const flightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  function clearFlight() {
    flight.current?.remove(); flight.current = null;
    if (destination.current) destination.current.style.visibility = originalVisibility.current;
    destination.current = null;
  }
  function imageFrame(rect: DOMRect) {
    return { left: rect.left + "px", top: rect.top + "px", width: rect.width + "px", height: rect.height + "px" };
  }
  const animations = useRef<Animation[]>([]);
  const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function cardTransform(rect: DOMRect) {
    const target = sheet.current!.getBoundingClientRect();
    return `translate(${rect.left - target.left}px, ${rect.top - target.top}px) scale(${rect.width / target.width}, ${rect.height / target.height})`;
  }
  useLayoutEffect(() => {
    let alive = true;
    let connectFrame: number | undefined;
    const node = dialog.current!;
    const previousOverflow = document.body.style.overflow;
    const previousFocus = origin?.focus || document.activeElement as HTMLElement | null;
    node.showModal();
    document.body.style.overflow = "hidden";
    if (!reduced()) {
      const sourceImage = origin?.element.querySelector<HTMLImageElement>("img");
      const from = sourceImage ? "none" : origin ? cardTransform(origin.rect) : "translateY(20px) scale(.97)";
      if (!sourceImage && origin && origin.rect.width > 0 && origin.rect.height > 0) {
        const clone = origin.element.cloneNode(true) as HTMLElement;
        clone.removeAttribute("data-case-id");
        clone.querySelectorAll("[id]").forEach(el => el.removeAttribute("id"));
        const target = sheet.current!.getBoundingClientRect();
        Object.assign(clone.style, {
          width: origin.rect.width + "px", height: origin.rect.height + "px", margin: "0",
          transformOrigin: "top left", transform: `scale(${target.width / origin.rect.width}, ${target.height / origin.rect.height})`,
        });
        preview.current!.append(clone);
      }
      if (sourceImage) {
        const ghost = new Image();
        ghost.src = sourceImage.currentSrc || sourceImage.src;
        ghost.alt = ""; ghost.className = "shared-cover-flight";
        Object.assign(ghost.style, imageFrame(sourceImage.getBoundingClientRect()));
        node.append(ghost); flight.current = ghost;
        const connect = () => {
          const target = content.current?.querySelector<HTMLImageElement>(".detail-cover > img, .product-detail-gallery img");
          if (!alive || !target || closing.current || !flight.current || destination.current) return;
          observer.current?.disconnect();
          if (flightTimer.current) clearTimeout(flightTimer.current);
          destination.current = target; originalVisibility.current = target.style.visibility;
          const to = target.getBoundingClientRect();
          target.style.visibility = "hidden";
          const motion = ghost.animate([imageFrame(sourceImage.getBoundingClientRect()), imageFrame(to)], {
            duration: 560, easing: "cubic-bezier(.22,1,.36,1)", fill: "forwards",
          });
          animations.current.push(motion);
          void motion.finished.then(clearFlight).catch(() => {});
        };
        observer.current = new MutationObserver(connect);
        observer.current.observe(content.current!, {childList: true, subtree: true});
        flightTimer.current = setTimeout(() => { observer.current?.disconnect(); clearFlight(); }, 1600);
        connectFrame = requestAnimationFrame(connect);
      }
      animations.current = [
        preview.current!.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 200, fill: "forwards" }),
        sheet.current!.animate([{ transform: from, opacity: .5 }, { transform: "none", opacity: 1 }], {
          duration: 520, easing: "cubic-bezier(.22,1,.36,1)",
        }),
        content.current!.animate([{ opacity: 0 }, { opacity: 1 }], {
          delay: 100, duration: 320, fill: "backwards", easing: "ease-out",
        }),
      ];
    }
    return () => {
      alive = false;
      if (connectFrame !== undefined) cancelAnimationFrame(connectFrame);
      animations.current.forEach(a => a.cancel());
      observer.current?.disconnect();
      if (flightTimer.current) clearTimeout(flightTimer.current);
      clearFlight();
      preview.current?.replaceChildren();
      node.close();
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
    };
  }, []);
  async function close() {
    if (closing.current) return;
    closing.current = true;
    animations.current.forEach(a => a.cancel());
    observer.current?.disconnect();
    if (flightTimer.current) clearTimeout(flightTimer.current);
    clearFlight();
    if (!reduced()) {
      const rect = origin?.element.isConnected ? origin.element.getBoundingClientRect() : null;
      const visible = rect && rect.bottom > 0 && rect.top < window.innerHeight;
      const sourceImage = origin?.element.querySelector<HTMLImageElement>("img");
      const targetImage = content.current?.querySelector<HTMLImageElement>(".detail-cover > img, .product-detail-gallery img");
      const targetRect = targetImage?.getBoundingClientRect();
      const canFly = visible && sourceImage && targetImage && targetRect && targetRect.bottom > 0 && targetRect.top < innerHeight;
      if (canFly) {
        const ghost = new Image(); ghost.src = targetImage.currentSrc || targetImage.src;
        ghost.alt = ""; ghost.className = "shared-cover-flight";
        Object.assign(ghost.style, imageFrame(targetRect));
        dialog.current!.append(ghost); flight.current = ghost;
        destination.current = targetImage; originalVisibility.current = targetImage.style.visibility;
        targetImage.style.visibility = "hidden";
        animations.current.push(ghost.animate([imageFrame(targetRect), imageFrame(sourceImage.getBoundingClientRect())], {duration: 360, easing: "cubic-bezier(.4,0,.2,1)", fill: "forwards"}));
      }
      const animation = sheet.current!.animate([
        { transform: "none", opacity: 1 },
        { transform: canFly ? "translateY(12px) scale(.985)" : visible ? cardTransform(rect) : "translateY(18px) scale(.97)", opacity: 0 },
      ], { duration: 360, easing: "cubic-bezier(.4,0,.2,1)", fill: "forwards" });
      animations.current.push(animation, content.current!.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 140, fill: "forwards" }));
      if (!canFly && visible && sheet.current!.scrollTop === 0) {
        animations.current.push(preview.current!.animate([{ opacity: 0 }, { opacity: 1 }], { delay: 100, duration: 180, fill: "forwards" }));
      }
      await animation.finished.catch(() => {});
    }
    onClose();
  }
  return createPortal(
    <dialog ref={dialog} className="research-dialog" aria-label={label}
      onCancel={e => { e.preventDefault(); void close(); }}
      onClick={e => { if (e.target === e.currentTarget) void close(); }}>
      <div ref={sheet} className="research-sheet">
        <div ref={preview} className="research-sheet-preview" aria-hidden="true" inert />
        <div ref={content} className="research-sheet-content">
          <button className="research-sheet-close icon" aria-label={closeLabel} onClick={() => void close()} autoFocus><X size={20} /></button>
          {children(() => void close())}
        </div>
      </div>
    </dialog>, document.body,
  );
}
