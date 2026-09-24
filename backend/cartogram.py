"""One deterministic SVG for screen and exports; labels never overlap in the centre."""
import math
from html import escape
from ml.topology import select_topology, attach_routes, TYPE_LABELS


def cartogram_svg(result, width=1000, height=1040):
    topology = result.get("intersection") or select_topology(result.get("calibration", {}), {})
    data = {**result, "intersection": topology, "movements": [dict(m) for m in result.get("movements", [])]}
    attach_routes(data)
    # Preserve historical results, but never render disputed AI routes as established flows.
    if topology.get("source") == "local_vlm" and topology.get("requires_review"):
        topology = {**topology, "usable": False}
        data["intersection"] = topology
    arms = topology.get("approaches", [])
    ids = {a["id"] for a in arms}
    routes = {}
    unmapped = 0
    for m in data["movements"]:
        key = (m.get("source_approach"), m.get("target_approach"))
        if not topology.get("usable") or None in key or key[0] not in ids or key[1] not in ids or key[0] == key[1]:
            unmapped += m.get("total", 0)
            continue
        r = routes.setdefault(key, {"total": 0, "review": False, "names": []})
        r["total"] += m.get("total", 0)
        r["review"] |= m.get("requires_review", False)
        r["names"].append(m.get("name", ""))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 1000 1040" role="img">',
             '<title>Картограмма транспортных потоков</title><desc>Схематический вид сверху. Числа — транспорт за весь ролик. Пунктир — нужна проверка.</desc>',
             '<rect width="1000" height="1040" fill="white"/>',
             '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L10 5 L0 10Z" fill="#222"/></marker></defs>',
             '<g font-family="Arial,sans-serif" fill="#20262b">']

    def point(a, lateral, radius):
        t = math.radians(a["angle"])
        return 500 + math.sin(t) * radius + math.cos(t) * lateral, 500 - math.cos(t) * radius + math.sin(t) * lateral

    def box(x, y, text, w=60, size=22, hint="", angle=0):
        angle = ((angle + 90) % 180) - 90
        parts.append(f'<g transform="rotate({angle:.1f} {x:.1f} {y:.1f})"><title>{escape(hint)}</title><rect x="{x-w/2:.1f}" y="{y-20:.1f}" width="{w}" height="40" fill="white" stroke="#222" stroke-width="2"/><text x="{x:.1f}" y="{y+7:.1f}" text-anchor="middle" font-size="{size}">{escape(str(text))}</text></g>')

    if len(arms) < 2:
        parts.append('<text x="500" y="440" text-anchor="middle" font-size="24">Геометрия перекрёстка не определена</text><text x="500" y="480" text-anchor="middle" font-size="18">Задайте зоны въезда и выезда в калибровке.</text>')
    else:
        # White road corridors mask their shared borders, giving continuous road outlines.
        for a in arms:
            parts.append(f'<path d="M500 500 L{point(a,0,485)[0]:.1f} {point(a,0,485)[1]:.1f}" stroke="#222" stroke-width="324"/>')
        for a in arms:
            parts.append(f'<path d="M500 500 L{point(a,0,488)[0]:.1f} {point(a,0,488)[1]:.1f}" stroke="white" stroke-width="318"/>')
        destinations = {a["id"]: sorted([key for key in routes if key[1] == a["id"]]) for a in arms}
        byid = {a["id"]: a for a in arms}
        label_boxes = []
        for key, route in routes.items():
            if route["total"] == 0:
                continue
            source, target = byid[key[0]], byid[key[1]]
            keys = destinations[key[1]]
            offset = 20 + keys.index(key) * min(52, 112 / max(1, len(keys)-1))
            sx, sy = point(source, -85, 285)
            ex, ey = point(target, offset, 265)
            c1 = point(source, -85, 50)
            c2 = point(target, offset, 50)
            dash = ' stroke-dasharray="9 6"' if route["review"] else ''
            parts.append(f'<path d="M{sx:.1f} {sy:.1f} C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {ex:.1f} {ey:.1f}" fill="none" stroke="#222" stroke-width="3" marker-end="url(#arrow)"{dash}><title>{escape("; ".join(route["names"]))}: {route["total"]}</title></path>')
            label_boxes.append((*point(target, offset, 291), route["total"], '; '.join(route["names"]), target["angle"]))
        for x, y, total, name, angle in label_boxes:
            box(x, y, total, 48 if total < 1000 else 62, 20, name, angle)
        for a in arms:
            incoming = sum(r["total"] for key, r in routes.items() if key[0] == a["id"])
            outgoing = sum(r["total"] for key, r in routes.items() if key[1] == a["id"])
            if incoming:
                x1,y1=point(a,-85,337);x2,y2=point(a,-85,285)
                parts.append(f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" stroke="#222" stroke-width="3"/>')
            keys = destinations[a["id"]]
            offsets = [20+i*min(52,112/max(1,len(keys)-1)) for i,key in enumerate(keys) if routes[key]["total"] > 0]
            if offsets:
                for lateral in offsets:
                    x1,y1=point(a,lateral,311);x2,y2=point(a,lateral,325)
                    parts.append(f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" stroke="#222" stroke-width="2"/>')
                x1,y1=point(a,min(offsets),325);x2,y2=point(a,max(offsets),325);x3,y3=point(a,70,337)
                parts.append(f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f} M{(x1+x2)/2:.1f} {(y1+y2)/2:.1f} L{x3:.1f} {y3:.1f}" fill="none" stroke="#222" stroke-width="2"/>')
            for lateral, total, label in ((-85, incoming, "Въезд"), (70, outgoing, "Выезд")):
                x, y = point(a, lateral, 357)
                box(x, y, total if topology.get("usable") else "—", 74, 24, label + ' · ' + a["label"], a["angle"])
                rotation = ((a["angle"] + 90) % 180) - 90
                parts.append(f'<text transform="rotate({rotation:.1f} {x:.1f} {y:.1f})" x="{x:.1f}" y="{y-28:.1f}" text-anchor="middle" font-size="13">{label}</text>')
            x1,y1=point(a,-85,382);x2,y2=point(a,70,382);x3,y3=point(a,0,404)
            parts.append(f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f} M{(x1+x2)/2:.1f} {(y1+y2)/2:.1f} L{x3:.1f} {y3:.1f}" fill="none" stroke="#222" stroke-width="2"/>')
            box(*point(a,0,414), incoming+outgoing if topology.get("usable") else "—", 86, 24, 'Сумма въезда и выезда', a["angle"])
            x,y=point(a,0,475)
            rotation = ((a["angle"] + 90) % 180) - 90
            parts.append(f'<text transform="rotate({rotation:.1f} {x:.1f} {y:.1f})" x="{x:.1f}" y="{y+5:.1f}" text-anchor="middle" font-size="16">{escape(a["label"][:25])}</text>')
    kind = TYPE_LABELS.get(topology.get("intersection_type"), "Не определён")
    note = f'{kind} · ТС за весь ролик · Без направления на схеме: {unmapped}'
    parts.append(f'<rect x="0" y="990" width="1000" height="50" fill="white"/><text x="500" y="1010" text-anchor="middle" font-size="16">{escape(note)}</text>')
    parts.append('<text x="500" y="1032" text-anchor="middle" font-size="13">Условная схема, без масштаба и географического севера. Пунктир — требуется проверка.</text></g></svg>')
    return ''.join(parts)
