from app.clients.bigquery_client import (
    get_bigquery_client,
    execute_query,
    normalize_for_bigquery,
    upsert_dataframe,
    TABLE_FATURA_ITENS,
    TABLE_MEDIDORES,
    TABLE_CLIENTES,
    TABLE_BOLETOS,
    TABLE_EDIT_LOG,
    TABLE_FATURAS_WORKFLOW,
    TABLE_BOLETOS_EMISSAO_SICOOB,
)

from app.clients.sicoob_client import (
    SicoobConfig,
    SicoobCobrancaV3Client,
    get_sicoob_config,
    build_boleto_payload_from_row,
)