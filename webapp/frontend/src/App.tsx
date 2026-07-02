import React, { useEffect, useState } from "react";
import DrawingCanvas from "./DrawingCanvas";
import { getInitData, getQueryParam, getTelegramWebApp } from "./telegram";

type Status = "idle" | "saving" | "done" | "error";

export default function App() {
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    const tg = getTelegramWebApp();
    tg?.ready();
    tg?.expand();
  }, []);

  const sessionId = getQueryParam("sid") ?? "";
  const round = getQueryParam("round") ?? "";

  const handleSave = async (dataUrl: string) => {
    setStatus("saving");
    try {
      const body = new URLSearchParams();
      body.set("initData", getInitData());
      body.set("sessionId", sessionId);
      body.set("imageBase64", dataUrl);

      const resp = await fetch("/api/drawings", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(detail || `HTTP ${resp.status}`);
      }
      setStatus("done");
      setTimeout(() => getTelegramWebApp()?.close(), 1200);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  };

  return (
    <div className="app-shell">
      <div className="torn-card" style={{ ["--tilt" as any]: "-1.5deg" }}>
        <h1 className="handwritten">Кривой телефон</h1>
        <p>
          Раунд {round || "?"} — нарисуй, что тебе досталось. Никто не увидит твой шедевр,
          пока книга не дойдёт до финала!
        </p>
      </div>

      {status === "done" ? (
        <div className="torn-card" style={{ ["--tilt" as any]: "1deg" }}>
          <p className="handwritten" style={{ fontSize: "1.6rem" }}>
            Отправлено! Жди остальных игроков.
          </p>
        </div>
      ) : (
        <div className="torn-card" style={{ ["--tilt" as any]: "0.5deg" }}>
          <DrawingCanvas onSave={handleSave} saving={status === "saving"} />
          {status === "error" && <p style={{ color: "var(--marker-pink)" }}>Ошибка: {errorMsg}</p>}
        </div>
      )}
    </div>
  );
}
