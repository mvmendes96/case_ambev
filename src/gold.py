import os
import logging
from google.cloud import bigquery

# ==============================
# CONFIGURAÇÕES E LOGS
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

PROJECT_ID = os.getenv("PROJECT_ID", "ambev-2025")
DATASET_ID_SILVER = "abi_silver"
DATASET_ID_GOLD = "abi_gold"
REGION = "us-central1"



client = bigquery.Client(project=PROJECT_ID)

# ==============================
# FUNÇÃO AUXILIAR
# ==============================
def create_table_from_query(query: str, description: str):
    """Executa query e cria tabela Gold."""
    logging.info(f"Criando {description} ...")
    job = client.query(query)
    job.result()
    logging.info(f"{description} criada com sucesso!\n")

# ==============================
# GARANTIR EXISTÊNCIA DO DATASET GOLD
# ==============================
def ensure_dataset():
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID_GOLD}")
    dataset_ref.location = REGION
    try:
        client.get_dataset(dataset_ref)
        logging.info(f"Dataset '{DATASET_ID_GOLD}' já existe.")
    except Exception:
        client.create_dataset(dataset_ref)
        logging.info(f"Dataset '{DATASET_ID_GOLD}' criado com sucesso!")

# ==============================
# QUERIES GOLD
# ==============================

# 1️⃣ Top 3 Trade Groups por Região
QUERY_1 = f"""
CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET_ID_GOLD}.sales_top3_tradegroups_by_region` AS
WITH ranked_sales AS (
  SELECT
    d.btlr_org_lvl_c_desc AS region,
    c.trade_chnl_desc AS trade_group,
    SUM(f.usd_volume) AS total_sales_usd,
    ROW_NUMBER() OVER (
      PARTITION BY d.btlr_org_lvl_c_desc
      ORDER BY SUM(f.usd_volume) DESC
    ) AS rank
  FROM `{PROJECT_ID}.{DATASET_ID_SILVER}.fact_sales` f
  JOIN `{PROJECT_ID}.{DATASET_ID_SILVER}.dim_distributor` d ON f.distributor_id = d.distributor_id
  JOIN `{PROJECT_ID}.{DATASET_ID_SILVER}.dim_channel` c ON f.channel_id = c.channel_id
  GROUP BY region, trade_group
)
SELECT region, trade_group, total_sales_usd
FROM ranked_sales
WHERE rank <= 3
ORDER BY region, total_sales_usd DESC;
"""

# 2️⃣ Vendas por Marca e Mês
QUERY_2 = f"""
CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET_ID_GOLD}.sales_by_brand_month` AS
SELECT
  b.brand AS brand_name,
  EXTRACT(YEAR FROM f.date) AS year,
  EXTRACT(MONTH FROM f.date) AS month,
  ROUND(SUM(f.usd_volume), 2) AS total_sales_usd
FROM `{PROJECT_ID}.{DATASET_ID_SILVER}.fact_sales` f
JOIN `{PROJECT_ID}.{DATASET_ID_SILVER}.dim_brand` b ON f.brand_id = b.brand_id
GROUP BY brand_name, year, month
ORDER BY brand_name, year, month;
"""

# 3️⃣ Marca com Menor Volume por Região
QUERY_3 = f"""
CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET_ID_GOLD}.lowest_brand_by_region` AS
WITH brand_sales AS (
  SELECT
    d.btlr_org_lvl_c_desc AS region,
    b.brand AS brand_name,
    SUM(f.usd_volume) AS total_sales_usd
  FROM `{PROJECT_ID}.{DATASET_ID_SILVER}.fact_sales` f
  JOIN `{PROJECT_ID}.{DATASET_ID_SILVER}.dim_brand` b ON f.brand_id = b.brand_id
  JOIN `{PROJECT_ID}.{DATASET_ID_SILVER}.dim_distributor` d ON f.distributor_id = d.distributor_id
  GROUP BY region, brand_name
),
ranked AS (
  SELECT
    region,
    brand_name,
    total_sales_usd,
    ROW_NUMBER() OVER (
      PARTITION BY region
      ORDER BY total_sales_usd ASC
    ) AS rank
  FROM brand_sales
)
SELECT region, brand_name, total_sales_usd
FROM ranked
WHERE rank = 1
ORDER BY region;
"""

# ==============================
# EXECUÇÃO PRINCIPAL
# ==============================
if __name__ == "__main__":
    logging.info("🚀 Iniciando camada GOLD da Ambev...")
    ensure_dataset()

    create_table_from_query(QUERY_1, "Top 3 Trade Groups por Região")
    create_table_from_query(QUERY_2, "Vendas por Marca e Mês")
    create_table_from_query(QUERY_3, "Menor Marca por Região")

    logging.info("🎉 Tabelas GOLD criadas com sucesso!")
