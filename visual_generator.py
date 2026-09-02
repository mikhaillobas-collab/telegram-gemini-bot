import io
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # Безголовый режим без GUI
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import seaborn as sns

logger = logging.getLogger(__name__)

# --- Настройка шрифтов для поддержки кириллицы ---
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Calibri", "Liberation Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


# ==============================================================================
# 1. Генератор аналитических графиков (Bar, Line, Pie, Area)
# ==============================================================================

def create_chart(data: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Генерирует высококачественный аналитический график (300 DPI).
    Формат data:
    {
        "filename": "Динамика_выручки.png",
        "chart_type": "bar" | "line" | "pie" | "horizontal_bar" | "area",
        "title": "Динамика выручки по кварталам",
        "xlabel": "Квартал",
        "ylabel": "Млн руб.",
        "labels": ["Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025"],
        "values": [12.5, 15.2, 18.0, 22.4],
        "series": [  (опционально, для нескольких линий/столбцов)
            {"name": "2024", "values": [10, 12, 14, 16]},
            {"name": "2025", "values": [12.5, 15.2, 18.0, 22.4]}
        ]
    }
    """
    filename = data.get("filename", "График.png")
    if not any(filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
        filename += ".png"

    chart_type = str(data.get("chart_type", "bar")).lower()
    title = data.get("title", "")
    xlabel = data.get("xlabel", "")
    ylabel = data.get("ylabel", "")
    labels = [str(x) for x in data.get("labels", [])]
    values = data.get("values", [])
    series = data.get("series", [])

    # Настройка стиля
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    palette = sns.color_palette("deep")

    # --- Круговая диаграмма (Pie / Donut) ---
    if chart_type in ["pie", "donut"]:
        if not values or not labels:
            values = [1]
            labels = ["Нет данных"]

        colors = sns.color_palette("pastel", len(values))
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            pctdistance=0.75 if chart_type == "donut" else 0.6,
            textprops={"fontsize": 11, "color": "#1E293B"},
            wedgeprops={"edgecolor": "white", "linewidth": 2}
        )
        for autotext in autotexts:
            autotext.set_color("black")
            autotext.set_fontweight("bold")

        if chart_type == "donut":
            centre_circle = plt.Circle((0, 0), 0.50, fc="white")
            fig.gca().add_artist(centre_circle)

        ax.axis("equal")

    # --- Линейный график (Line) ---
    elif chart_type == "line":
        if series:
            for idx, s in enumerate(series):
                s_name = s.get("name", f"Серия {idx + 1}")
                s_vals = s.get("values", [])
                x_axis = range(len(s_vals))
                ax.plot(x_axis, s_vals, marker="o", linewidth=2.5, label=s_name, color=palette[idx % len(palette)])
                for x, y in zip(x_axis, s_vals):
                    ax.annotate(f"{y}", (x, y), textcoords="offset points", xytext=(0, 8),
                                ha="center", fontsize=9, fontweight="bold")
            if labels:
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(labels, rotation=25 if len(labels) > 6 else 0)
            ax.legend(frameon=True, facecolor="white", edgecolor="#CBD5E1")
        else:
            x_axis = range(len(values))
            ax.plot(x_axis, values, marker="o", linewidth=3, color="#2563EB", markersize=7)
            for x, y in zip(x_axis, values):
                ax.annotate(f"{y}", (x, y), textcoords="offset points", xytext=(0, 8),
                            ha="center", fontsize=10, fontweight="bold", color="#1E3A8A")
            if labels:
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(labels, rotation=25 if len(labels) > 6 else 0)

    # --- Горизонтальная столбчатая диаграмма (Horizontal Bar) ---
    elif chart_type == "horizontal_bar":
        y_pos = range(len(labels))
        bars = ax.barh(y_pos, values, color="#3B82F6", edgecolor="#1D4ED8", height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=10)
        ax.invert_yaxis()
        for bar in bars:
            width = bar.get_width()
            ax.annotate(f"{width}",
                        xy=(width, bar.get_y() + bar.get_height() / 2),
                        xytext=(6, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=10, fontweight="bold", color="#1E293B")

    # --- Обычная столбчатая диаграмма (Bar, по умолчанию) ---
    else:
        if series:
            import numpy as np
            n_series = len(series)
            x = np.arange(len(labels))
            bar_width = 0.8 / n_series
            for idx, s in enumerate(series):
                s_name = s.get("name", f"Серия {idx + 1}")
                s_vals = s.get("values", [])
                offset = (idx - n_series / 2 + 0.5) * bar_width
                bars = ax.bar(x + offset, s_vals, width=bar_width, label=s_name, color=palette[idx % len(palette)])
                for bar in bars:
                    h = bar.get_height()
                    ax.annotate(f"{h}",
                                xy=(bar.get_x() + bar.get_width() / 2, h),
                                xytext=(0, 4), textcoords="offset points",
                                ha="center", va="bottom", fontsize=8, fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=25 if len(labels) > 6 else 0)
            ax.legend(frameon=True, facecolor="white", edgecolor="#CBD5E1")
        else:
            x_pos = range(len(labels))
            bars = ax.bar(x_pos, values, color="#3B82F6", edgecolor="#1D4ED8", width=0.55)
            ax.set_xticks(x_pos)
            ax.set_xticklabels(labels, rotation=25 if len(labels) > 6 else 0)
            for bar in bars:
                h = bar.get_height()
                ax.annotate(f"{h}",
                            xy=(bar.get_x() + bar.get_width() / 2, h),
                            xytext=(0, 4), textcoords="offset points",
                            ha="center", va="bottom", fontsize=10, fontweight="bold", color="#1E293B")

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=16, color="#0F172A")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=11, fontweight="semibold", labelpad=8, color="#334155")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=11, fontweight="semibold", labelpad=8, color="#334155")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue(), filename


# ==============================================================================
# 2. Генератор схем родства и генеалогических деревьев
# ==============================================================================

def create_kinship_tree(data: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Генерирует аккуратную графическую схему родственных связей / генеалогическое древо.
    Формат data:
    {
        "filename": "Схема_родства.png",
        "title": "ГЕНЕАЛОГИЧЕСКАЯ СХЕМА РОДСТВЕННЫХ СВЯЗЕЙ",
        "subtitle": "К заявлению об установлении факта родственных отношений",
        "nodes": [
            {"id": "anc", "title": "ОБЩИЕ ПРЕДКИ", "name": "Смирнов Иван / Смирнова Мария", "desc": "дер. Никишево", "level": 0, "color": "#1E3A8A"},
            {"id": "b1", "title": "Бабушка заявителя", "name": "Смирнова Пелагея Ивановна", "desc": "01.05.1901 – 02.07.1947", "level": 1, "color": "#2563EB"},
            {"id": "b2", "title": "Бабушка наследодателя", "name": "Тараничева Анна Ивановна", "desc": "29.11.1891 – 15.03.1965", "level": 1, "color": "#2563EB"},
            {"id": "s1", "title": "Двоюродная сестра (Заявитель)", "name": "Смирнова Тамара Николаевна", "desc": "Заявитель по делу", "level": 2, "color": "#059669"},
            {"id": "s2", "title": "Двоюродная сестра (Наследодатель)", "name": "Тараничева Нина Ивановна", "desc": "Наследодатель", "level": 2, "color": "#D97706"}
        ],
        "edges": [
            {"from": "anc", "to": "b1", "label": "дочь"},
            {"from": "anc", "to": "b2", "label": "дочь"},
            {"from": "b1", "to": "s1", "label": "дочь / заявитель"},
            {"from": "b2", "to": "s2", "label": "дочь / наследодатель"}
        ]
    }
    """
    filename = data.get("filename", "Схема_родства.png")
    if not any(filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
        filename += ".png"

    title = data.get("title", "СХЕМА РОДСТВЕННЫХ СВЯЗЕЙ")
    subtitle = data.get("subtitle", "")
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    if not nodes:
        # Заглушка, если ноды не переданы
        nodes = [{"id": "1", "title": "Схема", "name": "Нет данных", "level": 0}]

    # Группируем узлы по уровням (поколениям)
    levels: Dict[int, List[Dict[str, Any]]] = {}
    for node in nodes:
        lvl = int(node.get("level", 0))
        levels.setdefault(lvl, []).append(node)

    sorted_levels = sorted(levels.keys())
    max_nodes_in_level = max(len(nodes_in_lvl) for nodes_in_lvl in levels.values())

    # Рассчитываем размер холста
    fig_width = max(12, max_nodes_in_level * 4.2 + 2)
    fig_height = max(8, len(sorted_levels) * 3.2 + 2.5)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=300)
    ax.set_facecolor("#F8FAFC")
    fig.patch.set_facecolor("#F8FAFC")

    # Пределы осей
    ax.set_xlim(0, fig_width)
    ax.set_ylim(0, fig_height)
    ax.axis("off")

    # Шапка документа
    y_title = fig_height - 0.7
    ax.text(fig_width / 2, y_title, title, ha="center", va="center", fontsize=15, fontweight="bold", color="#0F172A")
    if subtitle:
        ax.text(fig_width / 2, y_title - 0.4, subtitle, ha="center", va="center", fontsize=11, fontstyle="italic", color="#475569")

    # Карточка: ширина и высота
    card_w = 3.6
    card_h = 1.6

    node_positions: Dict[str, Tuple[float, float]] = {}

    # Размещаем узлы по уровням
    y_start = fig_height - 2.2
    y_spacing = (y_start - 1.0) / max(len(sorted_levels) - 1, 1)

    for l_idx, lvl in enumerate(sorted_levels):
        nodes_in_lvl = levels[lvl]
        y_pos = y_start - (l_idx * y_spacing)
        n_count = len(nodes_in_lvl)

        # Вычисляем горизонтальные координаты для центрирования
        x_spacing = fig_width / (n_count + 1)

        for n_idx, node in enumerate(nodes_in_lvl):
            x_pos = (n_idx + 1) * x_spacing
            node_id = str(node.get("id", f"{lvl}_{n_idx}"))
            node_positions[node_id] = (x_pos, y_pos)

            # Цвета карточки
            header_color = node.get("color", "#1E3A8A")
            bg_color = "#FFFFFF"

            # Рисуем тело карточки (скругленный прямоугольник)
            card_box = FancyBboxPatch(
                (x_pos - card_w / 2, y_pos - card_h / 2),
                card_w, card_h,
                boxstyle="round,pad=0.08,rounding_size=0.15",
                facecolor=bg_color,
                edgecolor=header_color,
                linewidth=2.0,
                zorder=3
            )
            ax.add_patch(card_box)

            # Верхняя полоска-шапка внутри карточки
            top_bar_h = 0.4
            bar_box = FancyBboxPatch(
                (x_pos - card_w / 2, y_pos + card_h / 2 - top_bar_h),
                card_w, top_bar_h,
                boxstyle="round,pad=0.08,rounding_size=0.12",
                facecolor=header_color,
                edgecolor=header_color,
                zorder=4
            )
            ax.add_patch(bar_box)

            # Текст в шапке (роль / статус)
            card_title = str(node.get("title", ""))
            ax.text(x_pos, y_pos + card_h / 2 - top_bar_h / 2, card_title,
                    ha="center", va="center", color="white", fontsize=9, fontweight="bold", zorder=5)

            # ФИО
            name = str(node.get("name", ""))
            ax.text(x_pos, y_pos + 0.1, name,
                    ha="center", va="center", color="#0F172A", fontsize=10.5, fontweight="bold", zorder=5)

            # Описание / Даты жизни
            desc = str(node.get("desc", ""))
            if desc:
                ax.text(x_pos, y_pos - 0.35, desc,
                        ha="center", va="center", color="#475569", fontsize=9, zorder=5)

    # Рисуем соединительные линии со стрелками (Edges)
    for edge in edges:
        from_id = str(edge.get("from"))
        to_id = str(edge.get("to"))
        label = edge.get("label", "")

        if from_id in node_positions and to_id in node_positions:
            x1, y1 = node_positions[from_id]
            x2, y2 = node_positions[to_id]

            # Точка выхода: низ карточки from, вход: верх карточки to
            start_pt = (x1, y1 - card_h / 2)
            end_pt = (x2, y2 + card_h / 2)

            # Плавная изогнутая стрелка или ортогональная линия
            arrow = FancyArrowPatch(
                start_pt, end_pt,
                connectionstyle="arc3,rad=0.08",
                arrowstyle="-|>",
                mutation_scale=15,
                color="#64748B",
                linewidth=1.8,
                zorder=2
            )
            ax.add_patch(arrow)

            # Подпись к стрелке (например, "дочь", "сын")
            if label:
                mid_x = (start_pt[0] + end_pt[0]) / 2 + 0.15
                mid_y = (start_pt[1] + end_pt[1]) / 2
                ax.text(mid_x, mid_y, str(label),
                        ha="center", va="center", fontsize=8.5, color="#334155",
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="#F1F5F9", edgecolor="#CBD5E1", lw=0.8),
                        zorder=4)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue(), filename


# ==============================================================================
# 3. Генератор блок-схем процессов (Flowcharts)
# ==============================================================================

def create_flowchart(data: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Генерирует блок-схему процесса / алгоритма.
    """
    filename = data.get("filename", "Блок_схема.png")
    if not any(filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
        filename += ".png"

    title = data.get("title", "БЛОК-СХЕМА ПРОЦЕССА")
    steps = data.get("steps", [])

    fig_height = max(6, len(steps) * 1.8 + 2)
    fig, ax = plt.subplots(figsize=(8, fig_height), dpi=300)
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, fig_height)
    ax.axis("off")

    ax.text(5, fig_height - 0.6, title, ha="center", va="center", fontsize=14, fontweight="bold", color="#1E293B")

    y_pos = fig_height - 1.8
    step_h = 0.9
    step_w = 6.0

    for idx, step in enumerate(steps):
        text = str(step.get("text", step) if isinstance(step, dict) else step)
        shape_type = step.get("type", "process") if isinstance(step, dict) else "process"

        # Стили узла
        if shape_type == "start" or idx == 0:
            box = FancyBboxPatch((5 - step_w / 2, y_pos - step_h / 2), step_w, step_h,
                                 boxstyle="round,pad=0.1,rounding_size=0.4",
                                 facecolor="#10B981", edgecolor="#059669", lw=2, zorder=3)
            font_color = "white"
        elif shape_type == "decision":
            box = FancyBboxPatch((5 - step_w / 2, y_pos - step_h / 2), step_w, step_h,
                                 boxstyle="round,pad=0.1,rounding_size=0.1",
                                 facecolor="#F59E0B", edgecolor="#D97706", lw=2, zorder=3)
            font_color = "white"
        else:
            box = FancyBboxPatch((5 - step_w / 2, y_pos - step_h / 2), step_w, step_h,
                                 boxstyle="round,pad=0.1,rounding_size=0.15",
                                 facecolor="#F8FAFC", edgecolor="#3B82F6", lw=2, zorder=3)
            font_color = "#1E293B"

        ax.add_patch(box)
        ax.text(5, y_pos, text, ha="center", va="center", fontsize=10.5, fontweight="bold",
                color=font_color, zorder=4, wrap=True)

        # Стрелка к следующему шагу
        if idx < len(steps) - 1:
            arrow = FancyArrowPatch((5, y_pos - step_h / 2), (5, y_pos - 1.5 + step_h / 2),
                                    arrowstyle="-|>", mutation_scale=15, color="#64748B", lw=2, zorder=2)
            ax.add_patch(arrow)

        y_pos -= 1.5

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue(), filename
