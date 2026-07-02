import React, { useRef, useState, useCallback } from "react";

const PALETTE = ["#2b2b2b", "#ff2d78", "#ffd400", "#2bd672", "#2196f3", "#ff7a1a", "#9b5de5"];

interface Props {
  onSave: (dataUrl: string) => void;
  saving: boolean;
}

export default function DrawingCanvas({ onSave, saving }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const [color, setColor] = useState(PALETTE[0]);
  const [lineWidth, setLineWidth] = useState(4);

  const getCtx = () => canvasRef.current?.getContext("2d") ?? null;

  const pointerPos = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const scaleX = canvasRef.current!.width / rect.width;
    const scaleY = canvasRef.current!.height / rect.height;
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  };

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLCanvasElement>) => {
      const ctx = getCtx();
      if (!ctx) return;
      drawing.current = true;
      const { x, y } = pointerPos(e);
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      canvasRef.current?.setPointerCapture(e.pointerId);
    },
    [color, lineWidth]
  );

  const handlePointerMove = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const ctx = getCtx();
    if (!ctx) return;
    const { x, y } = pointerPos(e);
    ctx.lineTo(x, y);
    ctx.stroke();
  }, []);

  const handlePointerUp = useCallback(() => {
    drawing.current = false;
  }, []);

  const clear = () => {
    const canvas = canvasRef.current;
    const ctx = getCtx();
    if (!canvas || !ctx) return;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  };

  React.useEffect(() => {
    clear();
  }, []);

  const save = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    onSave(canvas.toDataURL("image/png"));
  };

  return (
    <div>
      <canvas
        ref={canvasRef}
        className="drawing-canvas"
        width={800}
        height={600}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      />
      <div style={{ display: "flex", gap: 8, margin: "12px 0", flexWrap: "wrap" }}>
        {PALETTE.map((c) => (
          <div
            key={c}
            className={`color-swatch${c === color ? " selected" : ""}`}
            style={{ background: c }}
            onClick={() => setColor(c)}
          />
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
        <span className="handwritten" style={{ fontSize: "1.2rem" }}>
          Толщина:
        </span>
        <input
          type="range"
          min={1}
          max={20}
          value={lineWidth}
          onChange={(e) => setLineWidth(Number(e.target.value))}
        />
      </div>
      <div style={{ display: "flex", gap: 12 }}>
        <button className="marker-btn" style={{ background: "#888" }} onClick={clear}>
          Очистить
        </button>
        <button className="marker-btn" onClick={save} disabled={saving}>
          {saving ? "Отправка..." : "Готово!"}
        </button>
      </div>
    </div>
  );
}
