from __future__ import annotations

import base64
import io
import os
import re
from typing import Any

import numpy as np
import sympy as sp
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from scipy.signal import place_poles, tf2ss

S = sp.Symbol("s")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="進階貝祖恆等式計算器", version="1.0.0")


def parse_matrix(s_str: str) -> np.ndarray:
    rows = [r.strip() for r in s_str.replace(";", "\n").split("\n") if r.strip()]
    if not rows:
        raise ValueError("矩陣不可為空。")
    data = []
    width = None
    for row in rows:
        vals = [x.strip() for x in re.split(r"[ ,\\t]+", row) if x.strip()]
        if not vals:
            continue
        values = [float(x) for x in vals]
        width = width or len(values)
        if len(values) != width:
            raise ValueError("矩陣每一列的欄數必須相同。")
        data.append(values)
    if not data:
        raise ValueError("矩陣不可為空。")
    return np.array(data, dtype=float)


def parse_poles(pole_text: str) -> list[float]:
    poles = [float(p.strip()) for p in pole_text.split(",") if p.strip()]
    if not poles:
        raise ValueError("至少要輸入一個期望閉迴路極點。")
    return poles


def ensure_shapes(A: np.ndarray, B: np.ndarray, C: np.ndarray, D: np.ndarray) -> None:
    n = A.shape[0]
    if A.ndim != 2 or A.shape[1] != n:
        raise ValueError("A 必須是方陣。")
    if B.ndim != 2 or B.shape[0] != n:
        raise ValueError("B 的列數必須等於 A 的階數。")
    if C.ndim != 2 or C.shape[1] != n:
        raise ValueError("C 的欄數必須等於 A 的階數。")
    if D.ndim != 2 or D.shape != (C.shape[0], B.shape[1]):
        raise ValueError("D 的維度必須等於 C 的列數 × B 的欄數。")


def tf_to_state_space(g_str: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    expr = sp.sympify(g_str, locals={"s": S})
    num, den = sp.fraction(sp.cancel(expr))
    if num == 0:
        raise ValueError("轉移函數分子不可為 0。")
    num_coeffs = [float(c) for c in sp.Poly(num, S).all_coeffs()]
    den_coeffs = [float(c) for c in sp.Poly(den, S).all_coeffs()]
    if len(den_coeffs) < 2:
        den_coeffs = [den_coeffs[0], 0.0]
    A, B, C, D = tf2ss(num_coeffs, den_coeffs)
    return np.asarray(A, float), np.asarray(B, float), np.asarray(C, float), np.asarray(D, float)


def ss2tf_sym(A_m: np.ndarray, B_m: np.ndarray, C_m: np.ndarray, D_m: np.ndarray) -> sp.Matrix:
    A_sp = sp.Matrix(A_m)
    B_sp = sp.Matrix(B_m)
    C_sp = sp.Matrix(C_m)
    D_sp = sp.Matrix(D_m)
    resolvent = (S * sp.eye(A_m.shape[0]) - A_sp).inv()
    return sp.simplify(C_sp * resolvent * B_sp + D_sp)


def clean_expr(expr: Any) -> sp.Expr | sp.MatrixBase:
    try:
        if isinstance(expr, sp.MatrixBase):
            return expr.applyfunc(lambda x: sp.cancel(sp.nsimplify(x, tolerance=1e-5, rational=True)))
        return sp.cancel(sp.nsimplify(expr, tolerance=1e-5, rational=True))
    except Exception:
        return sp.simplify(expr)


def matrix_to_list(m: np.ndarray) -> list[list[float]]:
    return np.asarray(m, dtype=float).tolist()


def matrix_latex(m: np.ndarray) -> str:
    return sp.latex(sp.Matrix(m))


def expression_to_latex(expr: sp.MatrixBase | sp.Expr) -> str:
    return sp.latex(expr)


def calculate_abcd(A: np.ndarray, B: np.ndarray, C: np.ndarray, D: np.ndarray, desired_poles: list[float]) -> dict[str, Any]:
    ensure_shapes(A, B, C, D)
    n = A.shape[0]
    p, m = C.shape[0], B.shape[1]
    if len(desired_poles) != n:
        raise ValueError(f"系統是 {n} 階，因此期望極點數量必須是 {n} 個。")

    # scipy.signal.place_poles uses the same gain convention as Python Control:
    # u = -Kx gives poles(A - BK). The original app defines F = -K.
    K_f = place_poles(A, B, desired_poles).gain_matrix
    F = -K_f
    K_l = place_poles(A.T, C.T, desired_poles).gain_matrix
    L = -K_l.T

    I_m, I_p = np.eye(m), np.eye(p)
    A_f = A + B @ F
    M_s = ss2tf_sym(A_f, B, F, I_m)
    Y_s = ss2tf_sym(A_f, L, F, np.zeros((m, p)))
    N_s = ss2tf_sym(A_f, B, C + D @ F, D)
    X_s = ss2tf_sym(A_f, L, C + D @ F, -I_p)

    A_l = A + L @ C
    X_tilde_s = ss2tf_sym(A_l, B + L @ D, -F, I_m)
    Y_tilde_s = ss2tf_sym(A_l, -L, -F, np.zeros((m, p)))
    N_tilde_s = ss2tf_sym(A_l, B + L @ D, C, D)
    M_tilde_s = ss2tf_sym(A_l, -L, C, -I_p)

    eq1 = clean_expr(X_tilde_s * M_s + Y_tilde_s * N_s)
    eq2 = clean_expr(X_tilde_s * Y_s + Y_tilde_s * X_s)
    eq3 = clean_expr(N_tilde_s * M_s + M_tilde_s * N_s)
    eq4 = clean_expr(N_tilde_s * Y_s + M_tilde_s * X_s)

    return {
        "dimensions": {"state_order": n, "outputs": p, "inputs": m},
        "A": matrix_to_list(A),
        "B": matrix_to_list(B),
        "C": matrix_to_list(C),
        "D": matrix_to_list(D),
        "F": matrix_to_list(F),
        "L": matrix_to_list(L),
        "F_latex": matrix_latex(F),
        "L_latex": matrix_latex(L),
        "factors": {
            "M": expression_to_latex(clean_expr(M_s)),
            "N": expression_to_latex(clean_expr(N_s)),
            "X": expression_to_latex(clean_expr(X_s)),
            "Y": expression_to_latex(clean_expr(Y_s)),
            "M_tilde": expression_to_latex(clean_expr(M_tilde_s)),
            "N_tilde": expression_to_latex(clean_expr(N_tilde_s)),
            "X_tilde": expression_to_latex(clean_expr(X_tilde_s)),
            "Y_tilde": expression_to_latex(clean_expr(Y_tilde_s)),
        },
        "equations": {
            "eq1": expression_to_latex(eq1),
            "eq2": expression_to_latex(eq2),
            "eq3": expression_to_latex(eq3),
            "eq4": expression_to_latex(eq4),
        },
    }


class CalculateRequest(BaseModel):
    mode: str
    pole_text: str = "-2, -3"
    A: str = "0, 1\n2, -1"
    B: str = "0\n1"
    C: str = "1, 0"
    D: str = "0"
    g_str: str = "1/(s - 1)"
    image_base64: str | None = None
    image_mime: str | None = None
    api_key: str | None = None


def extract_g_from_gemini(image_bytes: bytes, mime_type: str, api_key: str) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("後端尚未安裝 google-genai。請執行 pip install -r requirements.txt。") from exc

    client = genai.Client(api_key=api_key)
    prompt = (
        "這是一張控制系統的轉移函數圖片。請提取其中的數學表達式，"
        "只輸出單行式子（變數為 s，例如 100/s 或 1/(s^2+2*s+1)），"
        "不要包含 G(s)=，不要包含 markdown、解釋或其他文字。"
    )
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
    )
    text = (response.text or "").strip().replace("`", "").replace(" ", "")
    if "=" in text:
        text = text.split("=")[-1]
    if not text:
        raise RuntimeError("AI 沒有回傳可解析的轉移函數。")
    return text


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/calculate")
def calculate(req: CalculateRequest) -> dict[str, Any]:
    try:
        poles = parse_poles(req.pole_text)
        recognized = None
        if req.mode == "state":
            A, B, C, D = parse_matrix(req.A), parse_matrix(req.B), parse_matrix(req.C), parse_matrix(req.D)
        elif req.mode == "transfer":
            A, B, C, D = tf_to_state_space(req.g_str)
        elif req.mode == "image":
            if not req.image_base64:
                raise ValueError("請先上傳圖片。")
            api_key = (req.api_key or os.getenv("GEMINI_API_KEY") or "").strip()
            if not api_key:
                raise ValueError("請先輸入 Gemini API Key，或由網站管理者設定 GEMINI_API_KEY。")
            image_bytes = base64.b64decode(req.image_base64)
            mime = req.image_mime or "image/png"
            recognized = extract_g_from_gemini(image_bytes, mime, api_key)
            A, B, C, D = tf_to_state_space(recognized)
        else:
            raise ValueError("未知的輸入模式。")

        result = calculate_abcd(A, B, C, D, poles)
        result["recognized_g"] = recognized
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
