import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./style.css";
import "./FrameWorkspace.css";
import "./RaycastCards.css";
import "./RefinedWorkspace.css";
import "./GlassMotion.css";
if (/^#\/?world(?:\/|$)/.test(location.hash)) {
  location.replace("/wangxuge.html");
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
