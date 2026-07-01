import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import Targets from "./pages/Targets";
import Scenarios from "./pages/Scenarios";
import Runs from "./pages/Runs";
import RunDetail from "./pages/RunDetail";
import "./styles.css";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Scenarios /> },
      { path: "targets", element: <Targets /> },
      { path: "scenarios", element: <Scenarios /> },
      { path: "runs", element: <Runs /> },
      { path: "runs/:id", element: <RunDetail /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
