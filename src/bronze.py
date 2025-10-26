import os, logging
from google.cloud import storage, bigquery
import pandas as pd
import hashlib
from datetime import datetime, timezone
import io
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

PROJECT_ID = os.getenv("PROJECT_ID", "ambev-2025")
BUCKET_NAME = os.getenv("BUCKET_NAME")
REGION = os.getenv("REGION", "us-central1")
DATASET_BRONZE = os.getenv("DATASET_BRONZE", "abi_bronze")
client = bigquery.Client(project=PROJECT_ID)
storage_client = storage.Client(project=PROJECT_ID)

def clean_column_name(name: str) -> str:
    """Limpa nomes de colunas para serem compatíveis com BigQuery."""
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip())
    cleaned = re.sub(r'_+', '_', cleaned)
    cleaned = cleaned.strip('_')
    if cleaned and cleaned[0].isdigit():
        cleaned = 'col_' + cleaned
    return cleaned.upper()

def read_sales_csv_safe(blob, chunk_size=10000):
    """Lê arquivo CSV grande em chunks para evitar memory overflow."""
    try:
        # Método mais seguro para arquivos grandes
        if blob.size > 10 * 1024 * 1024:  # > 10MB
            logging.info(f"Lendo arquivo grande em chunks: {blob.name} ({blob.size} bytes)")
            chunks = []
            content_bytes = blob.download_as_bytes()
            content_str = content_bytes.decode('utf-16')
            string_io = io.StringIO(content_str)
            
            for chunk in pd.read_csv(string_io, sep='\t', chunksize=chunk_size):
                chunks.append(chunk)
            df = pd.concat(chunks, ignore_index=True)
        else:
            content_bytes = blob.download_as_bytes()
            content_str = content_bytes.decode('utf-16')
            df = pd.read_csv(io.StringIO(content_str), sep='\t')
        
        logging.info(f"Sales CSV lido com sucesso: {blob.name} ({len(df)} linhas, {len(df.columns)} colunas)")
        return df
    except Exception as e:
        logging.error(f"Erro ao ler arquivo de vendas {blob.name}: {e}")
        raise

def read_channel_csv(blob):
    """Lê arquivo de canal (formato normal)."""
    try:
        content = blob.download_as_text()
        df = pd.read_csv(io.StringIO(content))
        logging.info(f"Channel CSV lido com sucesso: {blob.name} ({len(df)} linhas)")
        return df
    except Exception as e:
        logging.error(f"Erro ao ler arquivo de canal {blob.name}: {e}")
        raise

def load_raw_files(bucket) -> tuple:
    """Carrega arquivos RAW do bucket."""
    sales_df, channel_df = None, None
    
    try:
        blobs = list(bucket.list_blobs(prefix="raw/"))
        logging.info(f"Encontrados {len(blobs)} blobs no prefixo 'raw/'")
        
        if not blobs:
            raise Exception("Nenhum arquivo encontrado no diretório 'raw/'")
        
        for blob in blobs:
            blob_name_lower = blob.name.lower()
            logging.info(f"Processando: {blob.name}")
            
            if "sales" in blob_name_lower and blob.name.endswith(".csv"):
                sales_df = read_sales_csv_safe(blob)
                logging.info(f"Sales CSV carregado: {blob.name} ({len(sales_df)} linhas)")
                
            elif "channel" in blob_name_lower and blob.name.endswith(".csv"):
                channel_df = read_channel_csv(blob)
                logging.info(f"Channel CSV carregado: {blob.name} ({len(channel_df)} linhas)")
        
        return sales_df, channel_df
        
    except Exception as e:
        logging.error(f"Erro ao carregar arquivos RAW: {e}")
        raise

def log_data_quality_metrics(df: pd.DataFrame, table_name: str):
    """Loga métricas de qualidade dos dados."""
    logging.info(f"Quality metrics for {table_name}:")
    logging.info(f"  - Total rows: {len(df)}")
    logging.info(f"  - Columns: {len(df.columns)}")
    
    if len(df) > 0:
        logging.info(f"  - Null percentages:")
        for col in df.columns:
            null_pct = (df[col].isna().sum() / len(df)) * 100
            if null_pct > 0:
                logging.warning(f"    {col}: {null_pct:.2f}% nulls")

def clean_sales_data(df: pd.DataFrame) -> pd.DataFrame:
    """Limpeza básica dos dados de vendas para camada Bronze - SEM REMOÇÃO DE DADOS."""
    logging.info("Iniciando limpeza dos dados de vendas...")
    
    df_clean = df.copy()
    initial_rows = len(df_clean)
    logging.info(f"Total de linhas inicial: {initial_rows}")
    
    # Log métricas antes da limpeza
    log_data_quality_metrics(df_clean, "sales_raw")
    
    column_mapping = {}
    for col in df_clean.columns:
        cleaned_name = clean_column_name(col)
        column_mapping[col] = cleaned_name
    
    df_clean = df_clean.rename(columns=column_mapping)
    logging.info(f"Colunas renomeadas para BigQuery: {column_mapping}")
    
    # Remover linhas completamente vazias
    df_clean = df_clean.dropna(how='all')
    empty_rows_removed = initial_rows - len(df_clean)
    if empty_rows_removed > 0:
        logging.info(f"Linhas completamente vazias removidas: {empty_rows_removed}")
    
    # Tratar valores nulos em colunas críticas
    critical_columns = ['DATE', 'CE_BRAND_FLVR', 'BTLR_ORG_LVL_C_DESC', 'TRADE_CHNL_DESC']
    for col in critical_columns:
        if col in df_clean.columns:
            null_count = df_clean[col].isna().sum()
            if null_count > 0:
                df_clean[col] = df_clean[col].fillna('UNKNOWN')
                logging.info(f"Preenchidos {null_count} valores nulos em {col} com 'UNKNOWN'")
    
    # Processar volume em USD
    volume_columns = [col for col in df_clean.columns if 'VOLUME' in col.upper()]
    if volume_columns:
        source_volume_col = volume_columns[0]
        logging.info(f"Processando coluna de volume: {source_volume_col}")
        
        df_clean['USD_VOLUME'] = (
            df_clean[source_volume_col]
            .astype(str)
            .str.replace('$', '', regex=False)
            .str.replace(',', '')
            .replace(['', 'nan', 'None', 'NaN', 'NULL'], '0')
        )
        
        df_clean['USD_VOLUME'] = pd.to_numeric(df_clean['USD_VOLUME'], errors='coerce')
        
        nan_after_conversion = df_clean['USD_VOLUME'].isna().sum()
        if nan_after_conversion > 0:
            df_clean['USD_VOLUME'] = df_clean['USD_VOLUME'].fillna(0)
            logging.info(f"Preenchidos {nan_after_conversion} valores inválidos em USD_VOLUME com 0")
        
        logging.info(f"Estatísticas do USD_VOLUME: Min={df_clean['USD_VOLUME'].min():.2f}, Max={df_clean['USD_VOLUME'].max():.2f}, Mean={df_clean['USD_VOLUME'].mean():.2f}")
    
    # Processar datas
    if 'DATE' in df_clean.columns:
        df_clean['DATE'] = pd.to_datetime(df_clean['DATE'], errors='coerce')
        invalid_dates = df_clean['DATE'].isna().sum()
        if invalid_dates > 0:
            df_clean['DATE'] = df_clean['DATE'].fillna(pd.Timestamp('2000-01-01'))
            logging.info(f"Preenchidas {invalid_dates} datas inválidas com data padrão")
    
    # Metadados
    df_clean['LOADED_AT'] = datetime.now(timezone.utc)
    df_clean['SOURCE_FILE'] = 'sales_raw'
    
    final_rows = len(df_clean)
    logging.info(f"Limpeza concluída. Shape final: {df_clean.shape}")
    logging.info(f"Linhas preservadas: {final_rows}/{initial_rows} ({final_rows/initial_rows*100:.1f}%)")
    
    # Log métricas após limpeza
    log_data_quality_metrics(df_clean, "sales_bronze")
    
    return df_clean

def clean_channel_data(df: pd.DataFrame) -> pd.DataFrame:
    """Limpeza básica dos dados de canal para camada Bronze."""
    logging.info("Iniciando limpeza dos dados de canal...")
    
    df_clean = df.copy()
    initial_rows = len(df_clean)
    
    # Log métricas antes da limpeza
    log_data_quality_metrics(df_clean, "channel_raw")
    
    column_mapping = {}
    for col in df_clean.columns:
        cleaned_name = clean_column_name(col)
        column_mapping[col] = cleaned_name
    
    df_clean = df_clean.rename(columns=column_mapping)
    logging.info(f"Colunas renomeadas: {column_mapping}")
    
    # Remover duplicatas
    initial_count = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    duplicates_removed = initial_count - len(df_clean)
    if duplicates_removed > 0:
        logging.info(f"Duplicatas completas removidas: {duplicates_removed}")
    
    # Tratar valores nulos
    for col in df_clean.columns:
        null_count = df_clean[col].isna().sum()
        if null_count > 0:
            df_clean[col] = df_clean[col].fillna('UNKNOWN')
            logging.info(f"Preenchidos {null_count} valores nulos em {col} com 'UNKNOWN'")
    
    # Metadados
    df_clean['LOADED_AT'] = datetime.now(timezone.utc)
    df_clean['SOURCE_FILE'] = 'channel_raw'
    
    final_rows = len(df_clean)
    logging.info(f"Limpeza concluída. Shape final: {df_clean.shape}")
    logging.info(f"Linhas preservadas: {final_rows}/{initial_rows} ({final_rows/initial_rows*100:.1f}%)")
    
    # Log métricas após limpeza
    log_data_quality_metrics(df_clean, "channel_bronze")
    
    return df_clean

def ensure_bronze_dataset_exists():
    """Garante que o dataset Bronze existe."""
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_BRONZE}")
    try:
        client.get_dataset(dataset_ref)
        logging.info("Dataset BRONZE já existe.")
    except Exception:
        dataset_ref.location = REGION
        client.create_dataset(dataset_ref)
        logging.info("Dataset BRONZE criado.")

def load_to_bronze(df: pd.DataFrame, table_name: str):
    """Carrega DataFrame para BigQuery na camada Bronze."""
    table_id = f"{PROJECT_ID}.{DATASET_BRONZE}.{table_name}"
    
    # Configuração do job com schema automático + particionamento
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        create_disposition="CREATE_IF_NEEDED",
        autodetect=True
    )
    
    try:
        job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
        job.result()  # Aguarda conclusão
        
        table = client.get_table(table_id)
        logging.info(f"{table_name} carregada na BRONZE ({len(df)} linhas, {table.num_rows} no total)")
        
        # Log do schema criado
        logging.info(f"Schema da tabela {table_name}:")
        for field in table.schema:
            logging.info(f"  - {field.name}: {field.field_type}")
            
    except Exception as e:
        logging.error(f"Erro ao carregar {table_name} na BRONZE: {e}")
        raise

def run_etl():
    """Função principal do ETL Bronze."""
    logging.info("Iniciando ETL Bronze...")
    
    try:
        # Validar variáveis de ambiente
        if not BUCKET_NAME:
            raise ValueError("BUCKET_NAME não configurado")
        
        bucket = storage_client.bucket(BUCKET_NAME)
        if not bucket.exists():
            raise Exception(f"Bucket {BUCKET_NAME} não existe")
        
        # Carregar dados
        sales_df, channel_df = load_raw_files(bucket)
        
        if sales_df is None:
            raise Exception("Arquivo de vendas (sales) não encontrado")
        if channel_df is None:
            raise Exception("Arquivo de canal (channel) não encontrado")
        
        logging.info("Aplicando limpeza de dados (preservando todos os registros)...")
        sales_bronze = clean_sales_data(sales_df)
        channel_bronze = clean_channel_data(channel_df)
        
        # Garantir que dataset existe
        ensure_bronze_dataset_exists()
        
        # Carregar para BigQuery
        logging.info("Carregando dados na camada BRONZE...")
        load_to_bronze(sales_bronze, "sales_bronze")
        load_to_bronze(channel_bronze, "channel_bronze")
        
        logging.info("ETL camada BRONZE concluído com sucesso!")
        return True
        
    except Exception as e:
        logging.error(f"Erro no ETL Bronze: {e}")
        raise

if __name__ == "__main__":
    run_etl()