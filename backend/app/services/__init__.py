from app.services.pdf_parser import (
    ResultadoParsing,
    parse_fatura,
    processar_lote_faturas,
)

from app.services.calc_engine import (
    CalcResult,
    infer_n_fases,
    compute_custo_disp,
    calculate_boletos,
)

from app.services.workflow_adapter import (
    build_workflow_from_parse_results,
    flatten_sicoob_payload_to_row,
)

from app.services.reporting_dataset import (
    load_reporting_fact,
    load_report_header,
    load_report_history,
    load_dashboard_drilldown,
    build_report_payload,
)