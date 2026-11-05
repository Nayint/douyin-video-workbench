declare const __VIRALLAB_DESKTOP__: boolean;
declare const __VIRALLAB_STANDALONE__: boolean;
export const isStandalone = (typeof __VIRALLAB_STANDALONE__ !== "undefined" && __VIRALLAB_STANDALONE__) || (typeof __VIRALLAB_DESKTOP__ !== "undefined" && __VIRALLAB_DESKTOP__);
export const isDesktop = isStandalone;
