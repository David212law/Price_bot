"""M12 Researcher v2 — export (با fallback بدون pandas)."""
from __future__ import annotations

import json
from pathlib import Path

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pd = None
    HAS_PANDAS = False


def export_csv(df, path):
    """ذخیره DataFrame یا list[dict] به CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if HAS_PANDAS and isinstance(df, pd.DataFrame):
        df.to_csv(path, index=False)
        return path

    # fallback: list of dicts
    rows = df if isinstance(df, list) else []
    if not rows:
        path.write_text("")
        return path

    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for r in rows:
        lines.append(",".join(str(r.get(h, "")) for h in headers))
    path.write_text("\n".join(lines))
    return path


def export_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def export_markdown(text, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def export_excel(dfs, path):
    """Excel — فقط اگه pandas+openpyxl باشه."""
    if not HAS_PANDAS:
        raise ImportError("pandas required for Excel")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, df in dfs.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return path


def export_full_report(results_dir, metrics_df, config, markdown_report="", date_str="latest"):
    out = Path(results_dir) / date_str
    out.mkdir(parents=True, exist_ok=True)
    paths = {}

    paths["csv"] = export_csv(metrics_df, out / f"metrics_{date_str}.csv")
    paths["json"] = export_json(config, out / f"config_{date_str}.json")
    if markdown_report:
        paths["md"] = export_markdown(markdown_report, out / f"summary_{date_str}.md")

    # Excel فقط اگه pandas باشه
    if HAS_PANDAS:
        try:
            excel_sheets = {"all": metrics_df}
            if "regime" in metrics_df.columns:
                for regime in metrics_df["regime"].unique():
                    excel_sheets[regime] = metrics_df[metrics_df["regime"] == regime]
            paths["excel"] = export_excel(excel_sheets, out / f"metrics_{date_str}.xlsx")
        except Exception:
            paths["excel"] = None
    else:
        paths["excel"] = None

    return paths


__all__ = ["export_csv", "export_excel", "export_json", "export_markdown", "export_full_report", "HAS_PANDAS"]
