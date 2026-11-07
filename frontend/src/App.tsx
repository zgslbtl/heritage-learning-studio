import React from "react";
import StudentApp from "./pages/StudentApp";
import AdminApp from "./pages/AdminApp";

export default function App() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  if (path === "/admin" || path.startsWith("/admin/")) {
    return <AdminApp />;
  }
  return <StudentApp />;
}
