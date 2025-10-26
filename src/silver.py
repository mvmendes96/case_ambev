import os, logging
from google.cloud import bigquery
import pandas as pd
import hashlib
from datetime import datetime, timezone



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

PROJECT_ID = os.getenv("PROJECT_ID", "ambev-2025")
REGION = os.getenv("REGION", "us-central1")
DATASET_BRONZE = os.getenv("DATASET_BRONZE", "abi_bronze")
DATASET_SILVER = os.getenv("DATASET_SILVER", "abi_silver")
client = bigquery.Client(project=PROJECT_ID)

def gen_id(value: str) -> str:
    """Gera ID único baseado em MD5."""
    return hashlib.md5(value.encode("utf-8")).hexdigest()[:12]

def read_from_bronze(table_name: str) -> pd.DataFrame:
    """Lê dados da camada Bronze."""
    try:
        query = f"""
        SELECT * 
        FROM `{PROJECT_ID}.{DATASET_BRONZE}.{table_name}`
        """
        df = client.query(query).to_dataframe()
        logging.info(f"Dados lidos da BRONZE: {table_name} ({len(df)} linhas)")
        return df
    except Exception as e:
        logging.error(f"Erro ao ler da BRONZE {table_name}: {e}")
        raise

def create_dim_brand(sales_df: pd.DataFrame) -> pd.DataFrame:
    """Cria dimensão de marcas."""
    dim_brand = sales_df[["CE_BRAND_FLVR", "BRAND_NM"]].drop_duplicates().copy()
    dim_brand["brand_id"] = dim_brand["CE_BRAND_FLVR"].apply(lambda x: gen_id(str(x)))
    
    dim_brand["BRAND_NM"] = dim_brand["BRAND_NM"].fillna("").astype(str).str.strip()
    
    def extract_brand_flavor(brand_nm):
        if not brand_nm or brand_nm == "nan":
            return "UNKNOWN", "UNKNOWN"
        
        brand_nm_clean = brand_nm.strip()
        parts = brand_nm_clean.split()
        if len(parts) > 0:
            brand = parts[0]
            flavor = " ".join(parts[1:]) if len(parts) > 1 else "REGULAR"
            return brand, flavor
        else:
            return brand_nm_clean, "REGULAR"
    
    brand_flavor_data = dim_brand["BRAND_NM"].apply(extract_brand_flavor)
    dim_brand["brand"] = brand_flavor_data.str[0]
    dim_brand["flavor"] = brand_flavor_data.str[1]
    
    logging.info(f"Dim Brand criada com {len(dim_brand)} marcas")
    for _, row in dim_brand.head().iterrows():
        logging.info(f"  - {row['CE_BRAND_FLVR']}: '{row['BRAND_NM']}' -> Brand: '{row['brand']}', Flavor: '{row['flavor']}'")
    
    return dim_brand[["brand_id", "CE_BRAND_FLVR", "brand", "flavor"]]

def create_dim_distributor(sales_df: pd.DataFrame) -> pd.DataFrame:
    """Cria dimensão de distribuidores."""
    dim_distributor = sales_df[["BTLR_ORG_LVL_C_DESC"]].drop_duplicates().copy()
    dim_distributor["distributor_id"] = dim_distributor["BTLR_ORG_LVL_C_DESC"].apply(
        lambda x: gen_id(str(x))
    )
    
    logging.info(f"Dim Distributor criada com {len(dim_distributor)} distribuidores")
    return dim_distributor[["distributor_id", "BTLR_ORG_LVL_C_DESC"]]

def create_dim_region(sales_df: pd.DataFrame) -> pd.DataFrame:
    """Cria dimensão de regiões."""
    region_columns = []
    possible_region_cols = ["REGION", "REGIAO", "BTLR_ORG_LVL_A_DESC", "BTLR_ORG_LVL_B_DESC"]
    
    for col in possible_region_cols:
        if col in sales_df.columns:
            region_columns.append(col)
            logging.info(f"Coluna de região encontrada: {col}")
    
    if not region_columns:
        logging.warning("Nenhuma coluna de região encontrada. Criando região padrão.")
        dim_region = pd.DataFrame({
            "region_name": ["DEFAULT_REGION"],
            "region_code": ["DEFAULT"]
        })
    else:
        region_col = region_columns[0]
        dim_region = sales_df[[region_col]].drop_duplicates().copy()
        dim_region = dim_region.rename(columns={region_col: "region_name"})
        
        def create_region_code(region_name):
            if pd.isna(region_name) or not region_name:
                return "UNK"
            return str(region_name).upper()[:3]
        
        dim_region["region_code"] = dim_region["region_name"].apply(create_region_code)
    
    dim_region["region_id"] = dim_region["region_name"].apply(lambda x: gen_id(str(x)))
    
    logging.info(f"Dim Region criada com {len(dim_region)} regiões")
    logging.info(f"Regiões disponíveis: {list(dim_region['region_name'].values)}")
    
    return dim_region[["region_id", "region_name", "region_code"]]

def create_dim_channel(channel_df: pd.DataFrame) -> pd.DataFrame:
    """Cria dimensão de canais."""
    dim_channel = channel_df.drop_duplicates(subset=["TRADE_CHNL_DESC"]).copy()
    dim_channel["channel_id"] = dim_channel["TRADE_CHNL_DESC"].apply(
        lambda x: gen_id(str(x))
    )
    
    logging.info(f"Dim Channel criada com {len(dim_channel)} canais")
    return dim_channel[["channel_id", "TRADE_CHNL_DESC", "TRADE_GROUP_DESC", "TRADE_TYPE_DESC"]]

def create_dim_date(sales_df: pd.DataFrame) -> pd.DataFrame:
    """Cria dimensão de datas."""
    dim_date = pd.DataFrame({"date": pd.to_datetime(sales_df["DATE"].unique())})
    dim_date["year"] = dim_date["date"].dt.year
    dim_date["month"] = dim_date["date"].dt.month
    dim_date["month_name"] = dim_date["date"].dt.strftime("%B")
    dim_date["week"] = dim_date["date"].dt.isocalendar().week
    dim_date["weekday"] = dim_date["date"].dt.strftime("%A")
    
    logging.info(f" Dim Date criada com {len(dim_date)} datas")
    return dim_date

def create_fact_sales(sales_df: pd.DataFrame, dim_brand: pd.DataFrame, 
                     dim_distributor: pd.DataFrame, dim_channel: pd.DataFrame,
                     dim_region: pd.DataFrame) -> pd.DataFrame:
    """Cria fato de vendas."""
    if 'USD_VOLUME' not in sales_df.columns:
        volume_cols = [col for col in sales_df.columns if 'VOLUME' in col]
        if volume_cols:
            sales_df['USD_VOLUME'] = sales_df[volume_cols[0]]
        else:
            sales_df['USD_VOLUME'] = 0
    
    region_col = None
    possible_region_cols = ["REGION", "REGIAO", "BTLR_ORG_LVL_A_DESC", "BTLR_ORG_LVL_B_DESC"]
    
    for col in possible_region_cols:
        if col in sales_df.columns:
            region_col = col
            break
    
    fact_sales = (
        sales_df.merge(dim_brand, on="CE_BRAND_FLVR", how="left")
        .merge(dim_distributor, on="BTLR_ORG_LVL_C_DESC", how="left")
        .merge(dim_channel, on="TRADE_CHNL_DESC", how="left")
    )
    
    if region_col and "region_name" in dim_region.columns:
        fact_sales = fact_sales.merge(
            dim_region, 
            left_on=region_col, 
            right_on="region_name", 
            how="left"
        )
        logging.info(f"Join com região realizado usando coluna: {region_col}")
    else:
        default_region_id = dim_region["region_id"].iloc[0] if len(dim_region) > 0 else "unknown"
        fact_sales["region_id"] = default_region_id
        logging.warning("Usando região padrão - coluna de região não encontrada para join")
    
    fact_sales["created_at"] = datetime.now(timezone.utc)
    
    date_column = None
    if 'date' in fact_sales.columns:
        date_column = 'date'
    elif 'DATE' in fact_sales.columns:
        date_column = 'DATE'
    else:
        date_candidates = [col for col in fact_sales.columns if 'date' in col.lower() or 'data' in col.lower()]
        if date_candidates:
            date_column = date_candidates[0]
        else:
            raise KeyError("Nenhuma coluna de data encontrada na fact_sales")
    
    if date_column != 'date':
        fact_sales = fact_sales.rename(columns={date_column: 'date'})
        logging.info(f"Coluna '{date_column}' renomeada para 'date'")
    
    fact_sales["date"] = pd.to_datetime(fact_sales["date"])
    
    fact_columns = [
        "date", "brand_id", "distributor_id", "channel_id", "region_id",
        "USD_VOLUME", "created_at"
    ]
    
    available_columns = [col for col in fact_columns if col in fact_sales.columns]
    
    logging.info(f"Colunas disponíveis na fact_sales: {list(fact_sales.columns)}")
    logging.info(f"Colunas selecionadas: {available_columns}")
    
    fact_sales = fact_sales[available_columns].copy()
    
    logging.info(f"Fact Sales criada com {len(fact_sales)} linhas")
    logging.info(f"Estatísticas do Volume: Min={fact_sales['USD_VOLUME'].min():.2f}, Max={fact_sales['USD_VOLUME'].max():.2f}, Mean={fact_sales['USD_VOLUME'].mean():.2f}")
    logging.info(f"Regiões na fact_sales: {fact_sales['region_id'].nunique() if 'region_id' in fact_sales.columns else 0}")
    
    return fact_sales

def ensure_silver_dataset_exists():
    """Garante que o dataset Silver existe."""
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_SILVER}")
    try:
        client.get_dataset(dataset_ref)
        logging.info("Dataset SILVER já existe.")
    except Exception:
        client.create_dataset(dataset_ref)
        logging.info("Dataset SILVER criado.")

def load_to_silver(df: pd.DataFrame, table_name: str):
    """Carrega DataFrame para BigQuery na camada Silver."""
    table_id = f"{PROJECT_ID}.{DATASET_SILVER}.{table_name}"
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        create_disposition="CREATE_IF_NEEDED"
    )
    
    try:
        job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
        job.result()
        table = client.get_table(table_id)
        logging.info(f"{table_name} carregada na SILVER ({len(df)} linhas, {table.num_rows} no total)")
    except Exception as e:
        logging.error(f"Erro ao carregar {table_name} na SILVER: {e}")
        raise

def run_etl():
    logging.info("Iniciando ETL ...")
    
    try:
        logging.info("Carregando dados da camada BRONZE...")
        sales_bronze = read_from_bronze("sales_bronze")
        channel_bronze = read_from_bronze("channel_bronze")
        
        logging.info(f"Dados Sales da BRONZE: {sales_bronze.shape}")
        logging.info(f"Dados Channel da BRONZE: {channel_bronze.shape}")
        logging.info(f"Colunas Sales: {list(sales_bronze.columns)}")
        
        logging.info("Criando dimensões...")
        dim_brand = create_dim_brand(sales_bronze)
        dim_distributor = create_dim_distributor(sales_bronze)
        dim_region = create_dim_region(sales_bronze)
        dim_channel = create_dim_channel(channel_bronze)
        dim_date = create_dim_date(sales_bronze)
        
        logging.info("Criando fato de vendas...")
        fact_sales = create_fact_sales(sales_bronze, dim_brand, dim_distributor, dim_channel, dim_region)
        logging.info(f"Linhas finais na tabela fato: {len(fact_sales)}")
        
        ensure_silver_dataset_exists()
        
        logging.info("Carregando dados na camada SILVER...")
        load_to_silver(dim_brand, "dim_brand")
        load_to_silver(dim_channel, "dim_channel")
        load_to_silver(dim_distributor, "dim_distributor")
        load_to_silver(dim_region, "dim_region")
        load_to_silver(dim_date, "dim_date")
        load_to_silver(fact_sales, "fact_sales")
        
        logging.info("ETL camada SILVER concluído com sucesso!")
        
    except Exception as e:
        logging.error(f"Erro no ETL Silver: {e}")
        raise

if __name__ == "__main__":
    run_etl()