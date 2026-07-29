import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Role dans le projet:
// Ce fichier monte l'application React dans le DOM. Il relie index.html au composant App qui porte l'interface utilisateur.
