from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import get_settings

settings = get_settings()

PROJECT_ID = settings.gcp_project_id
DATASET_ID = settings.gcp_dataset_id
LOCATION = settings.gcp_location

TABLE_FATURA_ITENS = f"{PROJECT_ID}.{DATASET_ID}.fatura_itens"
TABLE_MEDIDORES = f"{PROJECT_ID}.{DATASET_ID}.medidores_leituras"
TABLE_CLIENTES = f"{PROJECT_ID}.{DATASET_ID}.info_clientes"
TABLE_BOLETOS = f"{PROJECT_ID}.{DATASET_ID}.boletos_calculados"
TABLE_EDIT_LOG = f"{PROJECT_ID}.{DATASET_ID}.edit_log"
TABLE_FATURAS_WORKFLOW = f"{PROJECT_ID}.{DATASET_ID}.faturas_workflow"
TABLE_BOLETOS_EMISSAO_SICOOB = f"{PROJECT_ID}.{DATASET_ID}.boletos_emissao_sicoob"

_bigquery_client: bigquery.Client | None = None


def get_bigquery_client() -> bigquery.Client:
    global _bigquery_client

    if _bigquery_client is not None:
        return _bigquery_client

    credentials_path = Path(settings.google_application_credentials)

    if credentials_path.exists():
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path)
        )
        _bigquery_client = bigquery.Client(
            credentials=credentials,
            project=PROJECT_ID,
            location=LOCATION,
        )
    else:
        _bigquery_client = bigquery.Client(
            project=PROJECT_ID,
            location=LOCATION,
        )

    return _bigquery_client


def _infer_bq_param(
    name: str,
    value: Any,
) -> Union[bigquery.ScalarQueryParameter, bigquery.ArrayQueryParameter]:
    if isinstance(value, (list, tuple, set)):
        arr = [None if v is None else str(v) for v in value]
        return bigquery.ArrayQueryParameter(name, "STRING", arr)

    if isinstance(value, bool):
        return bigquery.ScalarQueryParameter(name, "BOOL", value)

    if isinstance(value, int):
        return bigquery.ScalarQueryParameter(name, "INT64", value)

    if isinstance(value, float):
        return bigquery.ScalarQueryParameter(name, "FLOAT64", value)

    return bigquery.ScalarQueryParameter(
        name,
        "STRING",
        None if value is None else str(value),
    )


def execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    client = get_bigquery_client()

    if params:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[_infer_bq_param(k, v) for k, v in params.items()]
        )
        return client.query(query, job_config=job_config).to_dataframe()

    return client.query(query).to_dataframe()


def _ensure_string_dtype(series: pd.Series) -> pd.Series:
    s = series.copy()
    s = s.where(pd.notna(s), pd.NA)
    s = s.astype("string")
    s = s.str.strip()
    s = s.replace({"": pd.NA, "None": pd.NA, "nan": pd.NA, "NaN": pd.NA})
    return s.astype(object).where(s.notna(), None)


def normalize_for_bigquery(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for c in df.columns:
        if df[c].dtype == object:
            try:
                if df[c].map(lambda x: isinstance(x, str) or x is None).all():
                    df[c] = _ensure_string_dtype(df[c])
            except Exception:
                pass

    return df.replace({np.nan: None})


def _make_key_unique_deterministically(df: pd.DataFrame, key_column: str) -> pd.DataFrame:
    if key_column not in df.columns or df.empty:
        return df

    df = df.copy()
    df[key_column] = _ensure_string_dtype(df[key_column])
    df = df[df[key_column].notna()].copy()
    df = df[df[key_column].astype(str).str.strip() != ""].copy()

    if df.empty:
        return df

    dup_mask = df[key_column].duplicated(keep=False)
    if not dup_mask.any():
        return df

    sort_candidates = [c for c in df.columns if c != key_column]
    df = df.sort_values(by=[key_column] + sort_candidates, kind="mergesort").reset_index(drop=True)
    df["__dup_idx"] = df.groupby(key_column).cumcount()

    needs_suffix = df["__dup_idx"] > 0
    df.loc[needs_suffix, key_column] = (
        df.loc[needs_suffix, key_column].astype(str)
        + "-"
        + df.loc[needs_suffix, "__dup_idx"].astype(str)
    )

    df = df.drop(columns=["__dup_idx"])
    df[key_column] = _ensure_string_dtype(df[key_column])
    return df


def _infer_bq_type_from_series(s: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(s):
        return "INT64"
    if pd.api.types.is_float_dtype(s):
        return "FLOAT64"
    if pd.api.types.is_bool_dtype(s):
        return "BOOL"
    return "STRING"


def ensure_table_columns_from_df(table_id: str, df: pd.DataFrame) -> None:
    client = get_bigquery_client()
    dest_table = client.get_table(table_id)
    dest_cols = {f.name for f in dest_table.schema}

    missing = [c for c in df.columns if c not in dest_cols]
    if not missing:
        return

    for c in missing:
        bq_type = _infer_bq_type_from_series(df[c]) if c in df.columns else "STRING"
        ddl = f"ALTER TABLE `{table_id}` ADD COLUMN `{c}` {bq_type}"
        client.query(ddl, location=LOCATION).result()


def _cast_df_to_dest_schema(
    df: pd.DataFrame,
    dest_schema_map: Dict[str, bigquery.SchemaField],
) -> pd.DataFrame:
    out = df.copy()

    for col in out.columns:
        if col not in dest_schema_map:
            continue

        field = dest_schema_map[col]
        field_type = (field.field_type or "").upper()
        series = out[col]

        try:
            if field_type in ("STRING", "GEOGRAPHY"):
                out[col] = _ensure_string_dtype(series)

            elif field_type in ("INT64", "INTEGER"):
                x = pd.to_numeric(series, errors="coerce")
                x = x.round(0)
                out[col] = x.astype("Int64")
                out[col] = out[col].where(out[col].notna(), None)

            elif field_type in ("FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC"):
                x = pd.to_numeric(series, errors="coerce")
                out[col] = x.where(x.notna(), None)

            elif field_type == "BOOL":
                if pd.api.types.is_bool_dtype(series):
                    out[col] = series.where(pd.notna(series), None)
                else:
                    x = series.astype(str).str.strip().str.lower()
                    out[col] = x.map(
                        lambda v: True if v in ("true", "1", "t", "yes", "y")
                        else (False if v in ("false", "0", "f", "no", "n") else None)
                    )

            elif field_type == "TIMESTAMP":
                x = pd.to_datetime(series, errors="coerce", utc=True)
                out[col] = x.where(x.notna(), None)

            elif field_type == "DATE":
                x = pd.to_datetime(series, errors="coerce").dt.date
                out[col] = x.where(pd.notna(x), None)

        except Exception:
            out[col] = series

    return out.replace({np.nan: None})


def upsert_dataframe(df: pd.DataFrame, table_id: str, key_column: str = "id") -> int:
    if df is None or df.empty:
        return 0

    if key_column not in df.columns:
        raise ValueError(f"DataFrame precisa da coluna '{key_column}'.")

    client = get_bigquery_client()

    df_clean = normalize_for_bigquery(df)
    df_clean = _make_key_unique_deterministically(df_clean, key_column)

    if df_clean.empty:
        return 0

    ensure_table_columns_from_df(table_id, df_clean)

    staging_suffix = uuid.uuid4().hex[:12]
    staging_table_id = f"{table_id}__staging_{staging_suffix}"

    dest_table = client.get_table(table_id)
    dest_schema_map = {f.name: f for f in dest_table.schema}

    missing_in_dest = [c for c in df_clean.columns if c not in dest_schema_map]
    if missing_in_dest:
        df_clean = df_clean[[c for c in df_clean.columns if c in dest_schema_map]].copy()

        if df_clean.empty:
            raise ValueError(
                f"Schema de destino não contém nenhuma coluna do DF. Faltantes: {missing_in_dest}"
            )

        dest_table = client.get_table(table_id)
        dest_schema_map = {f.name: f for f in dest_table.schema}

    df_clean = _cast_df_to_dest_schema(df_clean, dest_schema_map)
    staging_schema = [dest_schema_map[c] for c in df_clean.columns]

    try:
        job_config = bigquery.LoadJobConfig(
            schema=staging_schema,
            write_disposition="WRITE_TRUNCATE",
        )

        client.load_table_from_dataframe(
            df_clean,
            staging_table_id,
            location=LOCATION,
            job_config=job_config,
        ).result()

        cols = list(df_clean.columns)
        non_key_cols = [c for c in cols if c != key_column]

        def q(col_name: str) -> str:
            return f"`{col_name}`"

        update_set = ",\n      ".join([f"T.{q(c)} = S.{q(c)}" for c in non_key_cols])
        insert_cols = ", ".join([q(c) for c in cols])
        insert_vals = ", ".join([f"S.{q(c)}" for c in cols])

        merge_sql = f"""
        MERGE `{table_id}` T
        USING `{staging_table_id}` S
        ON T.{q(key_column)} = S.{q(key_column)}
        WHEN MATCHED THEN
          UPDATE SET
          {update_set}
        WHEN NOT MATCHED THEN
          INSERT ({insert_cols}) VALUES ({insert_vals})
        """

        merge_job = client.query(merge_sql, location=LOCATION)
        merge_job.result()

        affected = getattr(merge_job, "num_dml_affected_rows", None)
        return int(affected or len(df_clean))

    finally:
        client.delete_table(staging_table_id, not_found_ok=True)