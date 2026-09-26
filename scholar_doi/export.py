"""文献元数据导出（CSV / JSON）。"""
import csv
import json
import os

_FIELDS = [
    "doi", "title", "authors", "journal", "year",
    "publisher", "type", "is_oa", "oa_status",
    "pdf_url", "landing_url", "saved_file",
]


def _authors_str(record):
    authors = record.get("authors") or []
    if authors and isinstance(authors[0], dict):
        names = []
        for a in authors:
            fam = (a.get("family") or "").strip()
            given = (a.get("given") or "").strip()
            if fam and given:
                names.append("%s, %s" % (fam, given))
            else:
                names.append(fam or given)
        return "; ".join(names)
    return "; ".join(map(str, authors))


def export_records(records, out_path, fmt="csv"):
    """把记录列表导出到 out_path（支持 csv / json）。"""
    records = records or []
    out_path = os.path.abspath(out_path)
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if fmt == "json":
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return out_path

    # 默认 CSV
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writeheader()
        for r in records:
            row = {k: r.get(k) for k in _FIELDS}
            row["authors"] = _authors_str(r)
            row["is_oa"] = "Yes" if r.get("is_oa") else "No"
            row.setdefault("saved_file", r.get("local_path"))
            writer.writerow(row)
    return out_path