"""
Gera as figuras atualizadas da Prova de Conceito (PoC) para o TCC e GitHub:
1. docs/imagens/figura1_bpmn_as_is.png   (Diagrama BPMN página 16 atualizado)
2. docs/imagens/figura1_bpmn_to_be.png   (Diagrama BPMN página 17 atualizado)
3. docs/imagens/figura3_tabela_supabase.png (Tabela chamados_triagem coerente com schema.sql)
4. docs/imagens/diagrama_er_chamados_triagem.png (Diagrama relacional da tabela SQL)
"""

from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT_DIR / "docs" / "imagens"
DATA_JSON = ROOT_DIR / "evidencias" / "resultados_execucao_100.json"

FONT_REG = r"C:\Windows\Fonts\segoeui.ttf"
FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
FONT_MONO = r"C:\Windows\Fonts\consola.ttf"
FONT_MONO_BOLD = r"C:\Windows\Fonts\consolab.ttf"


def fnt(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def wrap_lines(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int
) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        test = w if not cur else f"{cur} {w}"
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int
) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    t = text
    while len(t) > 1 and draw.textlength(t + "...", font=font) > max_w:
        t = t[:-1]
    return t + "..."


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    fill: str = "#111827",
    line_gap: int = 8,
    y_offset: int = 0,
) -> None:
    x1, y1, x2, y2 = box
    heights = []
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        heights.append(bbox[3] - bbox[1])
    total_h = sum(heights) + line_gap * max(0, len(lines) - 1)
    y = y1 + (y2 - y1 - total_h) // 2 + y_offset
    for ln, h in zip(lines, heights):
        w = draw.textlength(ln, font=font)
        x = x1 + (x2 - x1 - w) / 2
        draw.text((x, y), ln, font=font, fill=fill)
        y += h + line_gap


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    color: str = "#1e293b",
    width: int = 4,
    head_len: int = 18,
    head_w: int = 12,
) -> None:
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=color, width=width, joint="curve")
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist
    px, py = -uy, ux
    tip = (x2, y2)
    left = (x2 - ux * head_len + px * head_w, y2 - uy * head_len + py * head_w)
    right = (x2 - ux * head_len - px * head_w, y2 - uy * head_len - py * head_w)
    draw.polygon([tip, left, right], fill=color)


def draw_user_icon(draw: ImageDraw.ImageDraw, x: int, y: int, s: int, color: str = "#334155") -> None:
    draw.rounded_rectangle([x, y, x + s, y + s], radius=max(4, s // 6), outline=color, width=3)
    cx = x + s // 2
    r = max(4, s // 5)
    draw.ellipse([cx - r, y + s // 5, cx + r, y + s // 5 + 2 * r], outline=color, width=3)
    draw.arc(
        [x + s // 5, y + s // 2 + 2, x + s - s // 5, y + s + s // 4],
        start=190,
        end=350,
        fill=color,
        width=3,
    )


def draw_gear_icon(draw: ImageDraw.ImageDraw, x: int, y: int, s: int, color: str = "#334155") -> None:
    draw.rounded_rectangle([x, y, x + s, y + s], radius=max(4, s // 6), outline=color, width=3)
    cx, cy = x + s // 2, y + s // 2
    r_out = s * 0.31
    r_in = s * 0.14
    for k in range(8):
        ang = k * math.pi / 4
        tx1 = cx + math.cos(ang) * (r_out - 2)
        ty1 = cy + math.sin(ang) * (r_out - 2)
        tx2 = cx + math.cos(ang) * (r_out + 5)
        ty2 = cy + math.sin(ang) * (r_out + 5)
        draw.line([(tx1, ty1), (tx2, ty2)], fill=color, width=4)
    draw.ellipse([cx - r_out, cy - r_out, cx + r_out, cy + r_out], outline=color, width=3)
    draw.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], outline=color, width=3)


def draw_clock_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str = "#334155") -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#ffffff", outline=color, width=4)
    ri = int(r * 0.80)
    draw.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], outline=color, width=3)
    draw.line([(cx, cy), (cx, cy - int(r * 0.48))], fill=color, width=4)
    draw.line([(cx, cy), (cx + int(r * 0.34), cy + int(r * 0.22))], fill=color, width=4)


def draw_xor_gateway(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str = "#334155") -> None:
    pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    draw.polygon(pts, fill="#ffffff", outline=color, width=5)
    d = int(r * 0.34)
    draw.line([(cx - d, cy - d), (cx + d, cy + d)], fill=color, width=7)
    draw.line([(cx + d, cy - d), (cx - d, cy + d)], fill=color, width=7)


def draw_pain_badge(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, num: str, font: ImageFont.FreeTypeFont) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#991b1b")
    draw_centered_text(draw, (cx - r, cy - r, cx + r, cy + r), [num], font, fill="#ffffff", y_offset=-2)


def draw_task_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    kind: str = "service",
    fill: str = "#eef4fb",
    outline: str = "#334155",
    badge: str | None = None,
    badge_font: ImageFont.FreeTypeFont | None = None,
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=24, fill=fill, outline=outline, width=4)
    if kind == "human":
        draw_user_icon(draw, x1 + 18, y1 + 18, 42, outline)
    else:
        draw_gear_icon(draw, x1 + 18, y1 + 18, 42, outline)

    if badge and badge_font:
        bx1, by1, bx2, by2 = x2 - 118, y1 + 16, x2 - 18, y1 + 54
        draw.rounded_rectangle([bx1, by1, bx2, by2], radius=12, fill="#0f766e")
        draw_centered_text(draw, (bx1, by1, bx2, by2), [badge], badge_font, fill="#ffffff", y_offset=-2)

    lines = wrap_lines(draw, text, font, (x2 - x1) - 48)
    draw_centered_text(draw, (x1 + 16, y1 + 48, x2 - 16, y2 - 12), lines, font, fill="#111827", line_gap=8)


def draw_bullets_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    bullets: list[str],
    title_font: ImageFont.FreeTypeFont,
    body_font: ImageFont.FreeTypeFont,
    fill: str,
    outline: str,
    title_color: str,
    bullet_color: str,
    line_step: int = 34,
    item_gap: int = 12,
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=20, fill=fill, outline=outline, width=4)
    pad = 26
    y = y1 + pad
    tlines = wrap_lines(draw, title, title_font, (x2 - x1) - 2 * pad)
    for tl in tlines:
        draw.text((x1 + pad, y), tl, font=title_font, fill=title_color)
        y += 40
    y += 10

    for item in bullets:
        draw.ellipse([x1 + pad + 4, y + 12, x1 + pad + 14, y + 22], fill=bullet_color)
        wrapped = wrap_lines(draw, item, body_font, (x2 - x1) - 2 * pad - 30)
        for wl in wrapped:
            draw.text((x1 + pad + 28, y), wl, font=body_font, fill="#1f2937")
            y += line_step
        y += item_gap


def generate_as_is() -> None:
    W, H = 3334, 4096
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)

    f_hdr = fnt(FONT_BOLD, 46)
    f_lane = fnt(FONT_BOLD, 42)
    f_lbl = fnt(FONT_REG, 36)
    f_lbl_b = fnt(FONT_BOLD, 38)
    f_task = fnt(FONT_REG, 36)
    f_card_t = fnt(FONT_BOLD, 38)
    f_card_b = fnt(FONT_REG, 31)
    f_badge = fnt(FONT_BOLD, 28)

    m_x1, m_y1, m_x2, m_y2 = 110, 110, W - 110, H - 140
    hdr_h = 120
    lane_h = 135
    col1_x = 960
    col2_x = 1780

    d.rectangle([m_x1, m_y1, m_x2, m_y1 + hdr_h], fill="#fae6e6", outline="#334155", width=4)
    draw_centered_text(
        d,
        (m_x1, m_y1, m_x2, m_y1 + hdr_h),
        ["CENÁRIO DE REFERÊNCIA HIPOTÉTICO (AS-IS) — Triagem manual de chamados N1"],
        f_hdr,
        fill="#991b1b",
    )

    ly1, ly2 = m_y1 + hdr_h, m_y1 + hdr_h + lane_h
    d.rectangle([m_x1, ly1, col1_x, ly2], fill="#f8fafc", outline="#334155", width=4)
    d.rectangle([col1_x, ly1, col2_x, ly2], fill="#f8fafc", outline="#334155", width=4)
    d.rectangle([col2_x, ly1, m_x2, ly2], fill="#f8fafc", outline="#334155", width=4)
    draw_centered_text(d, (m_x1, ly1, col1_x, ly2), ["Solicitante"], f_lane)
    draw_centered_text(d, (col1_x, ly1, col2_x, ly2), ["Sistema GLPI (Referência)"], f_lane)
    draw_centered_text(d, (col2_x, ly1, m_x2, ly2), ["Analista N1 (Service Desk)"], f_lane)

    d.rectangle([m_x1, ly2, col1_x, m_y2], outline="#334155", width=4)
    d.rectangle([col1_x, ly2, col2_x, m_y2], outline="#334155", width=4)
    d.rectangle([col2_x, ly2, m_x2, m_y2], outline="#334155", width=4)

    draw_centered_text(d, (m_x1, ly2 + 12, col1_x, ly2 + 78), ["Necessidade de suporte"], f_lbl)
    s_cx, s_cy, s_r = (m_x1 + col1_x) // 2, ly2 + 185, 76
    d.ellipse([s_cx - s_r, s_cy - s_r, s_cx + s_r, s_cy + s_r], fill="#ffffff", outline="#334155", width=6)

    t1_box = (m_x1 + 85, ly2 + 370, col1_x - 85, ly2 + 710)
    draw_task_box(d, t1_box, "Abrir chamado em texto livre no portal", f_task, kind="human", fill="#ffffff")
    draw_pain_badge(d, t1_box[2] - 4, t1_box[1] + 10, 32, "1", f_badge)
    draw_arrow(d, [(s_cx, s_cy + s_r), (s_cx, t1_box[1])])

    # Card lateral 1 ajustado sem excesso de espaço vazio
    draw_bullets_card(
        d,
        (m_x1 + 36, ly2 + 830, col1_x - 36, ly2 + 1595),
        "Caracterização do cenário hipotético (As-Is)",
        [
            "Processo manual hipotético adotado apenas como referência conceitual",
            "Atendimento sujeito ao horário de operação da equipe e à formação de filas",
            "Triagem inicial 100% dependente de leitura e interpretação humana",
            "Rastreabilidade restrita aos registros manuais inseridos no chamado",
        ],
        f_card_t,
        f_card_b,
        fill="#fef2f2",
        outline="#dc2626",
        title_color="#991b1b",
        bullet_color="#dc2626",
        line_step=36,
        item_gap=18,
    )

    # Card lateral 2: Legenda BPMN 2.0
    leg_box = (m_x1 + 36, ly2 + 1740, col1_x - 36, ly2 + 2980)
    d.rounded_rectangle(leg_box, radius=20, fill="#ffffff", outline="#94a3b8", width=4)
    d.text((leg_box[0] + 28, leg_box[1] + 28), "Legenda (BPMN 2.0)", font=f_card_t, fill="#111827")

    ly = leg_box[1] + 115
    lx = leg_box[0] + 75
    d.ellipse([lx - 32, ly - 32, lx + 32, ly + 32], outline="#334155", width=5)
    d.text((lx + 65, ly - 22), "Evento de início", font=f_card_b, fill="#1f2937")

    ly += 115
    d.ellipse([lx - 32, ly - 32, lx + 32, ly + 32], outline="#334155", width=10)
    d.text((lx + 65, ly - 22), "Evento de fim", font=f_card_b, fill="#1f2937")

    ly += 130
    draw_clock_icon(d, lx, ly, 36, "#334155")
    d.text((lx + 65, ly - 44), "Evento", font=f_card_b, fill="#1f2937")
    d.text((lx + 65, ly - 6), "temporizador", font=f_card_b, fill="#1f2937")
    d.text((lx + 65, ly + 32), "(espera)", font=f_card_b, fill="#1f2937")

    ly += 165
    draw_xor_gateway(d, lx, ly, 40, "#334155")
    d.text((lx + 65, ly - 32), "Gateway", font=f_card_b, fill="#1f2937")
    d.text((lx + 65, ly + 6), "exclusivo (XOR)", font=f_card_b, fill="#1f2937")

    ly += 130
    draw_user_icon(d, lx - 28, ly - 28, 56, "#334155")
    d.text((lx + 65, ly - 20), "Tarefa humana", font=f_card_b, fill="#1f2937")

    ly += 125
    draw_gear_icon(d, lx - 28, ly - 28, 56, "#334155")
    d.text((lx + 65, ly - 44), "Tarefa", font=f_card_b, fill="#1f2937")
    d.text((lx + 65, ly - 6), "automatizada", font=f_card_b, fill="#1f2937")
    d.text((lx + 65, ly + 32), "(serviço)", font=f_card_b, fill="#1f2937")

    ly += 155
    draw_pain_badge(d, lx, ly, 28, "n", f_badge)
    d.text((lx + 65, ly - 32), "Ponto de dor (ver", font=f_card_b, fill="#1f2937")
    d.text((lx + 65, ly + 6), "lista)", font=f_card_b, fill="#1f2937")

    glpi_cx = (col1_x + col2_x) // 2
    t2_box = (col1_x + 95, ly2 + 720, col2_x - 95, ly2 + 1060)
    draw_task_box(d, t2_box, 'Registrar chamado com status "Novo"', f_task, kind="service", fill="#eef4fb")
    draw_arrow(d, [(t1_box[2], (t1_box[1] + t1_box[3]) // 2), (glpi_cx, (t1_box[1] + t1_box[3]) // 2), (glpi_cx, t2_box[1])])

    clk_cx, clk_cy, clk_r = glpi_cx, ly2 + 1250, 74
    draw_clock_icon(d, clk_cx, clk_cy, clk_r, "#334155")
    draw_pain_badge(d, clk_cx + 58, clk_cy - 54, 32, "2", f_badge)
    draw_arrow(d, [(glpi_cx, t2_box[3]), (clk_cx, clk_cy - clk_r)])
    draw_centered_text(
        d,
        (col1_x + 40, clk_cy + clk_r + 18, col2_x - 40, clk_cy + clk_r + 125),
        ["Aguarda seleção manual", "(fila passiva)"],
        f_lbl,
    )

    pd_box = (col1_x + 36, ly2 + 1620, col2_x - 36, ly2 + 2660)
    d.rounded_rectangle(pd_box, radius=20, fill="#fef2f2", outline="#dc2626", width=4)
    d.text((pd_box[0] + 28, pd_box[1] + 28), "Pontos de dor", font=f_card_t, fill="#991b1b")
    pains = [
        ("1", "Abertura não estruturada: relato em texto livre, com classificação técnica omitida ou errada."),
        ("2", 'Fila de espera passiva: o chamado permanece "Novo" até a seleção manual.'),
        ("3", "Leitura e classificação manuais: Categoria (Hardware, Software, Redes, Acessos) e urgência variam entre analistas."),
    ]
    py = pd_box[1] + 105
    for num, txt in pains:
        draw_pain_badge(d, pd_box[0] + 54, py + 18, 26, num, f_badge)
        wlines = wrap_lines(d, txt, f_card_b, (pd_box[2] - pd_box[0]) - 130)
        for wl in wlines:
            d.text((pd_box[0] + 98, py - 2), wl, font=f_card_b, fill="#1f2937")
            py += 38
        py += 26

    an_cx = (col2_x + m_x2) // 2
    t3_box = (an_cx - 320, ly2 + 1460, an_cx + 320, ly2 + 1780)
    draw_task_box(d, t3_box, "Selecionar chamado na fila e ler o relato", f_task, kind="human", fill="#ffffff")
    draw_arrow(d, [(clk_cx + clk_r, clk_cy), (an_cx, clk_cy), (an_cx, t3_box[1])])

    t4_box = (an_cx - 320, ly2 + 1890, an_cx + 320, ly2 + 2210)
    draw_task_box(d, t4_box, "Classificar: Categoria ITIL e Urgência/SLA", f_task, kind="human", fill="#ffffff")
    draw_pain_badge(d, t4_box[2] - 4, t4_box[1] + 10, 32, "3", f_badge)
    draw_arrow(d, [(an_cx, t3_box[3]), (an_cx, t4_box[1])])

    gw_cx, gw_cy, gw_r = an_cx, ly2 + 2440, 108
    draw_xor_gateway(d, gw_cx, gw_cy, gw_r, "#334155")
    draw_arrow(d, [(an_cx, t4_box[3]), (gw_cx, gw_cy - gw_r)])
    d.text((gw_cx + 125, gw_cy - 105), "Resolve no N1?", font=f_lbl_b, fill="#111827")

    left_cx = (col2_x + gw_cx) // 2 - 40
    right_cx = (gw_cx + m_x2) // 2 + 40

    t5_box = (left_cx - 265, ly2 + 2710, left_cx + 265, ly2 + 3030)
    t6_box = (right_cx - 265, ly2 + 2710, right_cx + 265, ly2 + 3030)
    draw_task_box(d, t5_box, "Redigir resposta inicial ao solicitante", f_task, kind="human", fill="#ffffff")
    draw_task_box(d, t6_box, "Despachar para N2/N3", f_task, kind="human", fill="#ffffff")

    draw_arrow(d, [(gw_cx - gw_r, gw_cy), (left_cx, gw_cy), (left_cx, t5_box[1])])
    draw_arrow(d, [(gw_cx + gw_r, gw_cy), (right_cx, gw_cy), (right_cx, t6_box[1])])
    d.text((left_cx + 45, gw_cy + 20), "Sim", font=f_lbl_b, fill="#111827")
    d.text((right_cx - 120, gw_cy + 20), "Não", font=f_lbl_b, fill="#111827")

    e1_cy = ly2 + 3240
    e_r = 76
    d.ellipse([left_cx - e_r, e1_cy - e_r, left_cx + e_r, e1_cy + e_r], fill="#ffffff", outline="#334155", width=13)
    d.ellipse([right_cx - e_r, e1_cy - e_r, right_cx + e_r, e1_cy + e_r], fill="#ffffff", outline="#334155", width=13)
    draw_arrow(d, [(left_cx, t5_box[3]), (left_cx, e1_cy - e_r)])
    draw_arrow(d, [(right_cx, t6_box[3]), (right_cx, e1_cy - e_r)])

    draw_centered_text(d, (left_cx - 280, e1_cy + e_r + 16, left_cx + 280, e1_cy + e_r + 130), ["Chamado respondido no", "N1"], f_lbl)
    draw_centered_text(d, (right_cx - 280, e1_cy + e_r + 16, right_cx + 280, e1_cy + e_r + 130), ["Chamado escalado", "(N2/N3)"], f_lbl)

    final_img = img.resize((1667, 2048), Image.Resampling.LANCZOS)
    final_img.save(OUT_DIR / "figura1_bpmn_as_is.png", quality=95)


def generate_to_be() -> None:
    W, H = 3120, 4096
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)

    f_hdr = fnt(FONT_BOLD, 44)
    f_lane = fnt(FONT_BOLD, 38)
    f_lbl = fnt(FONT_REG, 34)
    f_lbl_b = fnt(FONT_BOLD, 36)
    f_task = fnt(FONT_REG, 32)
    f_card_t = fnt(FONT_BOLD, 34)
    f_card_b = fnt(FONT_REG, 28)
    f_badge = fnt(FONT_BOLD, 25)

    m_x1, m_y1, m_x2, m_y2 = 90, 90, W - 90, H - 110
    hdr_h = 115
    lane_h = 145
    col1_x = 680
    col2_x = 1235
    col3_x = 2405

    d.rectangle([m_x1, m_y1, m_x2, m_y1 + hdr_h], fill="#e6f4f1", outline="#334155", width=4)
    draw_centered_text(
        d,
        (m_x1, m_y1, m_x2, m_y1 + hdr_h),
        ["CENÁRIO PROPOSTO (TO-BE) — Esteira de triagem na Prova de Conceito (PoC)"],
        f_hdr,
        fill="#0f766e",
    )

    ly1, ly2 = m_y1 + hdr_h, m_y1 + hdr_h + lane_h
    d.rectangle([m_x1, ly1, col1_x, ly2], fill="#f8fafc", outline="#334155", width=4)
    d.rectangle([col1_x, ly1, col2_x, ly2], fill="#f8fafc", outline="#334155", width=4)
    d.rectangle([col2_x, ly1, col3_x, ly2], fill="#f8fafc", outline="#334155", width=4)
    d.rectangle([col3_x, ly1, m_x2, ly2], fill="#f8fafc", outline="#334155", width=4)

    draw_centered_text(d, (m_x1, ly1, col1_x, ly2), ["Solicitante"], f_lane)
    draw_centered_text(d, (col1_x, ly1, col2_x, ly2), ["Sistema GLPI", "(Emulado via HTTP)"], f_lane, line_gap=4)
    draw_centered_text(d, (col2_x, ly1, col3_x, ly2), ["Esteira de Hiperautomação (n8n + LLM +", "Supabase)"], f_lane, line_gap=4)
    draw_centered_text(d, (col3_x, ly1, m_x2, ly2), ["Analista N1/N2", "(human-in-the-loop)"], f_lane, line_gap=4)

    d.rectangle([m_x1, ly2, col1_x, m_y2], outline="#334155", width=4)
    d.rectangle([col1_x, ly2, col2_x, m_y2], outline="#334155", width=4)
    d.rectangle([col2_x, ly2, col3_x, m_y2], outline="#334155", width=4)
    d.rectangle([col3_x, ly2, m_x2, m_y2], outline="#334155", width=4)

    # Raia 1: Solicitante
    draw_centered_text(d, (m_x1, ly2 + 12, col1_x, ly2 + 78), ["Necessidade de suporte"], f_lbl)
    s_cx, s_cy, s_r = (m_x1 + col1_x) // 2, ly2 + 180, 70
    d.ellipse([s_cx - s_r, s_cy - s_r, s_cx + s_r, s_cy + s_r], fill="#ffffff", outline="#334155", width=6)

    t1_box = (m_x1 + 42, ly2 + 345, col1_x - 42, ly2 + 655)
    draw_task_box(d, t1_box, "Abrir chamado sintético em texto livre no portal", f_task, kind="human", fill="#ffffff")
    draw_arrow(d, [(s_cx, s_cy + s_r), (s_cx, t1_box[1])])

    # Raia 2: Sistema GLPI (Emulado via HTTP)
    glpi_cx = (col1_x + col2_x) // 2
    t2_box = (col1_x + 36, ly2 + 650, col2_x - 36, ly2 + 975)
    draw_task_box(d, t2_box, "Gerar Ticket ID e disparar Webhook HTTP POST", f_task, kind="service", fill="#eef4fb")
    draw_arrow(d, [(t1_box[2], (t1_box[1] + t1_box[3]) // 2), (glpi_cx, (t1_box[1] + t1_box[3]) // 2), (glpi_cx, t2_box[1])])

    # Quadros informativos à esquerda ajustados com folga confortável até o fundo
    draw_bullets_card(
        d,
        (m_x1 + 36, ly2 + 1070, col2_x - 28, ly2 + 2060),
        "Indicadores demonstrativos da PoC (N = 100 chamados sintéticos)",
        [
            "Conjunto experimental de 100 chamados sintéticos (80 padronizados e 20 ambíguos/críticos)",
            "82 encaminhamentos automáticos (82%) e 18 enviados à revisão humana (18%)",
            "74 acertos entre os 80 casos padronizados (92,5% de acurácia classificatória)",
            "Persistência dos registros no PostgreSQL/Supabase (chamados_triagem)",
            "Saída para o GLPI representada por requisições HTTP emuladas (httpbin.org/post)",
        ],
        f_card_t,
        f_card_b,
        fill="#ecfdf5",
        outline="#10b981",
        title_color="#0f766e",
        bullet_color="#10b981",
        line_step=33,
        item_gap=14,
    )

    draw_bullets_card(
        d,
        (m_x1 + 36, ly2 + 2120, col2_x - 28, ly2 + 2860),
        "Como a esteira opera na PoC",
        [
            "Recebimento via Webhook HTTP POST no n8n com dados do chamado sintético",
            "Gemini (gemini-3.5-flash-lite, temp. 0,0) e Structured Output Parser (JSON)",
            "Condicional (confiança ≥ 0,85 e sem revisão obrigatória) define o encaminhamento",
            "O analista atua apenas nas exceções (confiança < 0,85 ou alta criticidade)",
        ],
        f_card_t,
        f_card_b,
        fill="#ecfdf5",
        outline="#10b981",
        title_color="#0f766e",
        bullet_color="#10b981",
        line_step=33,
        item_gap=14,
    )

    # Legenda BPMN 2.0 com folga completa abaixo do último item
    leg_box = (m_x1 + 36, ly2 + 2925, col2_x - 28, m_y2 - 50)
    d.rounded_rectangle(leg_box, radius=20, fill="#ffffff", outline="#94a3b8", width=4)
    d.text((leg_box[0] + 28, leg_box[1] + 24), "Legenda (BPMN 2.0)", font=f_card_t, fill="#111827")

    ly = leg_box[1] + 108
    lx = leg_box[0] + 78
    d.ellipse([lx - 30, ly - 30, lx + 30, ly + 30], outline="#334155", width=5)
    d.text((lx + 65, ly - 20), "Evento de início", font=f_card_b, fill="#1f2937")

    ly += 105
    d.ellipse([lx - 30, ly - 30, lx + 30, ly + 30], outline="#334155", width=10)
    d.text((lx + 65, ly - 20), "Evento de fim", font=f_card_b, fill="#1f2937")

    ly += 110
    draw_xor_gateway(d, lx, ly, 36, "#334155")
    d.text((lx + 65, ly - 20), "Gateway exclusivo (XOR)", font=f_card_b, fill="#1f2937")

    ly += 110
    draw_user_icon(d, lx - 25, ly - 25, 50, "#334155")
    d.text((lx + 65, ly - 20), "Tarefa humana", font=f_card_b, fill="#1f2937")

    ly += 105
    draw_gear_icon(d, lx - 25, ly - 25, 50, "#334155")
    d.text((lx + 65, ly - 20), "Tarefa automatizada (serviço)", font=f_card_b, fill="#1f2937")

    # Raia 3: Esteira de Hiperautomação (n8n + LLM + Supabase) - posições bem distribuídas
    est_cx = (col2_x + col3_x) // 2
    t3_box = (est_cx - 265, ly2 + 885, est_cx + 265, ly2 + 1185)
    draw_task_box(d, t3_box, "Receber payload (Webhook n8n)", f_task, kind="service", fill="#eef4fb")
    draw_arrow(d, [(t2_box[2], (t2_box[1] + t2_box[3]) // 2), (est_cx, (t2_box[1] + t2_box[3]) // 2), (est_cx, t3_box[1])])

    t4_box = (est_cx - 265, ly2 + 1295, est_cx + 265, ly2 + 1615)
    draw_task_box(
        d,
        t4_box,
        "Parsing semântico via LLM e retorno de JSON estrito",
        f_task,
        kind="service",
        fill="#eef4fb",
        badge="LLM",
        badge_font=f_badge,
    )
    draw_arrow(d, [(est_cx, t3_box[3]), (est_cx, t4_box[1])])

    gw_cx, gw_cy, gw_r = est_cx, ly2 + 1865, 102
    draw_xor_gateway(d, gw_cx, gw_cy, gw_r, "#334155")
    draw_arrow(d, [(est_cx, t4_box[3]), (gw_cx, gw_cy - gw_r)])
    draw_centered_text(
        d,
        (col2_x + 30, gw_cy - 170, gw_cx - 80, gw_cy - 40),
        ["Confiança ≥ 0,85", "e sem revisão?"],
        f_lbl_b,
    )

    sim_cx = (col2_x + gw_cx) // 2 - 20
    nao_cx = (gw_cx + col3_x) // 2 + 20

    t5_box = (sim_cx - 245, ly2 + 2115, sim_cx + 245, ly2 + 2455)
    t6_box = (nao_cx - 245, ly2 + 2115, nao_cx + 245, ly2 + 2455)
    draw_task_box(d, t5_box, "Emular atualização no GLPI via HTTP POST (httpbin.org)", f_task, kind="service", fill="#eef4fb")
    draw_task_box(d, t6_box, "Emular envio para revisão humana via HTTP POST (httpbin.org)", f_task, kind="service", fill="#eef4fb")

    draw_arrow(d, [(gw_cx - gw_r, gw_cy), (sim_cx, gw_cy), (sim_cx, t5_box[1])])
    draw_arrow(d, [(gw_cx + gw_r, gw_cy), (nao_cx, gw_cy), (nao_cx, t6_box[1])])
    d.text((sim_cx + 40, gw_cy - 52), "Sim", font=f_lbl_b, fill="#111827")
    d.text((nao_cx - 125, gw_cy - 52), "Não", font=f_lbl_b, fill="#111827")

    t7_box = (sim_cx - 245, ly2 + 2575, sim_cx + 245, ly2 + 2895)
    t8_box = (nao_cx - 245, ly2 + 2575, nao_cx + 245, ly2 + 2895)
    draw_task_box(d, t7_box, "Persistir log no Supabase (status = Automático)", f_task, kind="service", fill="#eef4fb")
    draw_task_box(d, t8_box, "Persistir log no Supabase (status = Revisão Humana)", f_task, kind="service", fill="#eef4fb")

    draw_arrow(d, [(sim_cx, t5_box[3]), (sim_cx, t7_box[1])])
    draw_arrow(d, [(nao_cx, t6_box[3]), (nao_cx, t8_box[1])])

    e1_cy, e_r = ly2 + 3140, 74
    d.ellipse([sim_cx - e_r, e1_cy - e_r, sim_cx + e_r, e1_cy + e_r], fill="#ffffff", outline="#334155", width=13)
    draw_arrow(d, [(sim_cx, t7_box[3]), (sim_cx, e1_cy - e_r)])
    draw_centered_text(
        d,
        (sim_cx - 250, e1_cy + e_r + 18, sim_cx + 250, e1_cy + e_r + 125),
        ["Encaminhamento automático", "emulado"],
        f_lbl,
    )

    # Raia 4: Analista N1/N2 - com folga confortável até m_y2
    an_cx = (col3_x + m_x2) // 2
    t9_box = (col3_x + 52, ly2 + 2880, m_x2 - 52, ly2 + 3190)
    draw_task_box(d, t9_box, "Tratar chamado já pré-classificado", f_task, kind="human", fill="#ffffff")
    draw_arrow(d, [(t8_box[2], (t8_box[1] + t8_box[3]) // 2), (an_cx, (t8_box[1] + t8_box[3]) // 2), (an_cx, t9_box[1])])

    e2_cy = ly2 + 3380
    d.ellipse([an_cx - e_r, e2_cy - e_r, an_cx + e_r, e2_cy + e_r], fill="#ffffff", outline="#334155", width=13)
    draw_arrow(d, [(an_cx, t9_box[3]), (an_cx, e2_cy - e_r)])
    draw_centered_text(
        d,
        (col3_x + 20, e2_cy + e_r + 18, m_x2 - 20, e2_cy + e_r + 125),
        ["Exceção avaliada pelo", "analista"],
        f_lbl,
    )

    final_img = img.resize((1560, 2048), Image.Resampling.LANCZOS)
    final_img.save(OUT_DIR / "figura1_bpmn_to_be.png", quality=95)


def generate_supabase_table_screenshot() -> None:
    records = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    by_id = {r["glpi_ticket_id"]: r for r in records}
    selected_ids = [
        2001, 2002, 2003, 2004, 2005, 2006,
        2015, 2028, 2042,
        2080, 2081, 2083, 2084, 2085, 2086, 2090,
    ]
    rows = [by_id[tid] for tid in selected_ids]

    cols = [
        ("id", "uuid", 145),
        ("created_at", "timestamptz", 225),
        ("glpi_ticket_id", "int4", 130),
        ("remetente_email", "text", 230),
        ("conteudo_original", "text", 325),
        ("intencao_classificada", "text", 185),
        ("nivel_urgencia", "text", 132),
        ("categoria_sugerida", "text", 168),
        ("confianca_ia", "numeric", 118),
        ("requer_revisao", "bool", 138),
        ("status_processamento", "text", 190),
    ]

    W = sum(c[2] for c in cols)
    H = 820
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)

    f_hdr = fnt(FONT_BOLD, 16)
    f_type = fnt(FONT_REG, 13)
    f_cell = fnt(FONT_REG, 15)
    f_mono = fnt(FONT_MONO, 14)
    f_bold = fnt(FONT_BOLD, 15)

    hdr_h = 56
    row_h = (H - hdr_h) // len(rows)
    x = 0
    d.rectangle([0, 0, W, hdr_h], fill="#f8fafc")
    for name, ctype, cw in cols:
        d.rectangle([x, 0, x + cw, hdr_h], outline="#e2e8f0", width=1)
        d.text((x + 12, 10), fit_text(d, name, f_hdr, cw - 20), font=f_hdr, fill="#0f172a")
        d.text((x + 12, 32), ctype, font=f_type, fill="#64748b")
        x += cw

    for idx, r in enumerate(rows):
        y1 = hdr_h + idx * row_h
        y2 = y1 + row_h
        bg = "#ffffff" if r["status_processamento"] == "Automatico" else "#fffbeb"
        if r["glpi_ticket_id"] == 2085:
            bg = "#fef2f2"
        d.rectangle([0, y1, W, y2], fill=bg)

        uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tcc-chamado-{r['glpi_ticket_id']}"))[:12] + "..."
        ts = r["created_at"].replace("T", " ").replace("+00:00", "+00")

        vals = [
            uid,
            ts,
            str(r["glpi_ticket_id"]),
            r["remetente_email"],
            r["conteudo_original"],
            r["intencao_classificada"],
            r["nivel_urgencia"],
            r["categoria_sugerida"],
            f"{r['confianca_ia']:.2f}",
            "true" if r["requer_revisao_humana"] else "false",
            r["status_processamento"],
        ]

        x = 0
        for col_idx, ((_, _, cw), val) in enumerate(zip(cols, vals)):
            d.rectangle([x, y1, x + cw, y2], outline="#e2e8f0", width=1)
            font_use = f_mono if col_idx in (0, 1, 2, 8, 9) else f_cell
            color = "#1e293b"
            if col_idx == 10:
                color = "#047857" if val == "Automatico" else "#b91c1c"
                font_use = f_bold
            elif col_idx == 6 and val == "Critica":
                color = "#b91c1c"
                font_use = f_bold
            txt_fitted = fit_text(d, val, font_use, cw - 22)
            d.text((x + 11, y1 + (row_h - 18) // 2), txt_fitted, font=font_use, fill=color)
            x += cw

    img.save(OUT_DIR / "figura3_tabela_supabase.png", quality=95)


def generate_sql_diagram() -> None:
    W, H = 1600, 960
    img = Image.new("RGB", (W, H), "#f8fafc")
    d = ImageDraw.Draw(img)

    f_title = fnt(FONT_BOLD, 28)
    f_sub = fnt(FONT_REG, 20)
    f_tbl_hdr = fnt(FONT_BOLD, 24)
    f_col = fnt(FONT_MONO_BOLD, 19)
    f_type = fnt(FONT_MONO, 18)
    f_desc = fnt(FONT_REG, 18)

    d.text((55, 34), "Estrutura Relacional de Persistência e Auditoria (database/schema.sql)", font=f_title, fill="#0f172a")
    d.text((55, 72), "Banco: PostgreSQL / Supabase  |  Tabela principal: public.chamados_triagem  |  Script DDL idempotente", font=f_sub, fill="#475569")

    tx1, ty1, tx2, ty2 = 55, 128, 1110, 905
    d.rounded_rectangle([tx1, ty1, tx2, ty2], radius=14, fill="#ffffff", outline="#1e293b", width=3)
    d.rounded_rectangle([tx1, ty1, tx2, ty1 + 58], radius=14, fill="#0f766e")
    d.rectangle([tx1, ty1 + 40, tx2, ty1 + 58], fill="#0f766e")
    d.text((tx1 + 22, ty1 + 14), "TABLE: public.chamados_triagem", font=f_tbl_hdr, fill="#ffffff")

    columns = [
        ("PK", "id", "UUID", "DEFAULT gen_random_uuid() NOT NULL"),
        ("", "created_at", "TIMESTAMPTZ", "DEFAULT timezone('utc', now()) NOT NULL"),
        ("", "glpi_ticket_id", "INTEGER", "Identificador do chamado de origem"),
        ("", "remetente_email", "TEXT NOT NULL", "E-mail corporativo (sintético na PoC)"),
        ("", "conteudo_original", "TEXT NOT NULL", "Título + descrição recebidos via webhook"),
        ("IDX", "intencao_classificada", "TEXT NOT NULL", "Duvida | Incidente | Solicitacao | Outros"),
        ("", "nivel_urgencia", "TEXT NOT NULL", "Baixa | Media | Alta | Critica"),
        ("", "categoria_sugerida", "TEXT", "Hardware | Software | Redes | Acessos"),
        ("", "confianca_ia", "NUMERIC(3,2) NOT NULL", "Escore probabilístico (0.00 a 1.00)"),
        ("IDX", "status_processamento", "TEXT NOT NULL", "'Automatico' ou 'Revisao Humana'"),
        ("", "resposta_sugerida", "TEXT", "Minuta preliminar gerada pela camada cognitiva"),
        ("", "requer_revisao_humana", "BOOLEAN DEFAULT FALSE", "Flag obrigatória para desvio Human-in-the-Loop"),
        ("", "tempo_processamento_ms", "INTEGER", "Referência de latência em milissegundos"),
    ]

    cy = ty1 + 76
    for idx, (badge, cname, ctype, cdesc) in enumerate(columns):
        if idx < len(columns) - 1:
            d.line([(tx1 + 14, cy + 45), (tx2 - 14, cy + 45)], fill="#e2e8f0", width=1)
        if badge:
            bcol = "#d97706" if badge == "PK" else "#2563eb"
            d.rounded_rectangle([tx1 + 16, cy + 7, tx1 + 66, cy + 35], radius=6, fill=bcol)
            draw_centered_text(d, (tx1 + 16, cy + 7, tx1 + 66, cy + 35), [badge], fnt(FONT_BOLD, 14), fill="#ffffff", y_offset=-1)
        d.text((tx1 + 82, cy + 10), cname, font=f_col, fill="#0f172a")
        d.text((tx1 + 360, cy + 10), ctype, font=f_type, fill="#0f766e")
        d.text((tx1 + 615, cy + 11), cdesc, font=f_desc, fill="#475569")
        cy += 53

    ix1, iy1, ix2, iy2 = 1145, 128, 1545, 535
    d.rounded_rectangle([ix1, iy1, ix2, iy2], radius=14, fill="#ffffff", outline="#2563eb", width=3)
    d.rounded_rectangle([ix1, iy1, ix2, iy1 + 54], radius=14, fill="#1d4ed8")
    d.rectangle([ix1, iy1 + 36, ix2, iy1 + 54], fill="#1d4ed8")
    d.text((ix1 + 18, iy1 + 12), "Índices B-Tree & Extensão", font=fnt(FONT_BOLD, 21), fill="#ffffff")

    idx_items = [
        ("Extensão:", 'CREATE EXTENSION "pgcrypto"'),
        ("Índice 1:", "idx_chamados_triagem_status\n(status_processamento)"),
        ("Índice 2:", "idx_chamados_triagem_intencao\n(intencao_classificada)"),
        ("Índice 3:", "idx_chamados_triagem_created_at\n(created_at DESC)"),
    ]
    iy = iy1 + 74
    for lbl, val in idx_items:
        d.text((ix1 + 20, iy), lbl, font=fnt(FONT_BOLD, 17), fill="#1e3a8a")
        iy += 24
        for subl in val.split("\n"):
            d.text((ix1 + 20, iy), subl, font=fnt(FONT_MONO, 16), fill="#334155")
            iy += 23
        iy += 16

    rx1, ry1, rx2, ry2 = 1145, 565, 1545, 905
    d.rounded_rectangle([rx1, ry1, rx2, ry2], radius=14, fill="#ecfdf5", outline="#10b981", width=3)
    d.text((rx1 + 20, ry1 + 20), "Lógica de Roteamento Registrada", font=fnt(FONT_BOLD, 20), fill="#065f46")
    rules = [
        "• Automatico (82/100):",
        "  confianca_ia >= 0.85 E",
        "  requer_revisao_humana = FALSE",
        "",
        "• Revisao Humana (18/100):",
        "  confianca_ia < 0.85 OU",
        "  requer_revisao_humana = TRUE",
        "",
        "• Idempotência DDL:",
        "  IF NOT EXISTS + TRUNCATE",
        "  antes da carga sintética.",
    ]
    ry = ry1 + 64
    for rl in rules:
        d.text((rx1 + 20, ry), rl, font=fnt(FONT_MONO if rl.startswith("  ") else FONT_REG, 16), fill="#1f2937")
        ry += 24

    img.save(OUT_DIR / "diagrama_er_chamados_triagem.png", quality=95)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_as_is()
    generate_to_be()
    generate_supabase_table_screenshot()
    generate_sql_diagram()
    print("Diagramas e evidências visuais gerados em docs/imagens/!")


if __name__ == "__main__":
    main()
