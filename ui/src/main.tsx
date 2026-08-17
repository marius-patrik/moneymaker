import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
// Self-hosted variable fonts — a system stack is the default look of a page
// nobody designed, and figures need a mono with real tabular alignment.
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
