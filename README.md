# 🍺 Ambev Data Platform (Terraform + GCP)

## 🚀 Visão Geral
A **Ambev Data Platform** foi desenvolvida para transformar **dados brutos de vendas e canais** em **informações analíticas rápidas, consistentes e confiáveis**.  
O projeto utiliza **Infraestrutura como Código (IaC)** com **Terraform** para provisionar recursos no **Google Cloud Platform (GCP)**, orquestrando pipelines **ETL containerizados** em **Cloud Run Jobs** e armazenando resultados em **BigQuery**.

---

## 🏗️ Arquitetura Geral

![Arquitetura GCP]

```text
[Terraform]
   ↓ provisiona
[Cloud Storage] → [Cloud Run Jobs] → [BigQuery] → [Looker Studio]
                       ↑
     (Dockerfiles Bronze/Silver/Gold + Python ETLs + Catálogos YAML)
```

### 🔹 Camadas de Dados

| Camada | Descrição | Script Principal |
|--------|------------|------------------|
| **Bronze** | Ingestão e padronização dos dados brutos. | `bronze.py` |
| **Silver** | Limpeza, enriquecimento e junção das tabelas. | `silver.py` |
| **Gold** | Agregações analíticas, KPIs e métricas de negócio. | `gold.py` |

---

## ⚙️ Estrutura de Diretórios

```bash
infra/
├── deploy.ps1
├── Dockerfile
├── Dockerfile.bronze
├── Dockerfile.silver
├── Dockerfile.gold
├── src/
│   ├── bronze.py
│   ├── silver.py
│   ├── gold.py
│   ├── catalog_silver.yml
│   ├── catalog_gold.yml
│   └── requirements.txt
├── datasets/
│   ├── abi_bus_case1_beverage_channel_group_20210726.csv
│   └── abi_bus_case1_beverage_sales_20210726.csv
└── terraform/
    ├── bigquery.tf
    ├── cloudrun.tf
    ├── iam.tf
    ├── providers.tf
    ├── run.tf
    ├── storage.tf
    ├── variables.tf
    ├── terraform.tfstate
    ├── terraform.tfstate.backup
    ├── .terraform.lock.hcl
    └── .terraform/
```

---

## 📚 Catálogo de Dados

Os catálogos YAML descrevem de forma padronizada as **estruturas e definições das tabelas** nas camadas Silver e Gold.

| Arquivo | Descrição |
|----------|------------|
| `catalog_silver.yml` | Define dimensões e fatos da camada Silver, incluindo chaves e relacionamentos. |
| `catalog_gold.yml` | Lista as tabelas analíticas e KPIs da camada Gold, utilizadas no Looker Studio. |

Esses arquivos servem como **documentação técnica e de negócio**, permitindo integração com ferramentas de governança de dados (como Data Catalog, Alation, Collibra, etc).

---

## 🌍 Recursos Provisionados (Terraform)

| Recurso | Descrição |
|----------|------------|
| **IAM** | Criação de service accounts e permissões granulares. |
| **Cloud Storage** | Buckets de ingestão e staging para datasets. |
| **BigQuery** | Datasets `abi_bronze`, `abi_silver`, `abi_gold`. |
| **Cloud Run Jobs** | Execução automatizada dos containers ETL. |

---

## 🧩 ETL Containers

Cada camada do pipeline possui um **Dockerfile** e um script dedicado:

| Container | Dockerfile | Script | Output |
|------------|-------------|---------|---------|
| Bronze | `Dockerfile.bronze` | `bronze.py` | Dados padronizados |
| Silver | `Dockerfile.silver` | `silver.py` | Dados limpos e enriquecidos |
| Gold | `Dockerfile.gold` | `gold.py` | KPIs e métricas de negócio |

Os **catálogos YAML** são armazenados na mesma pasta (`src/`) para versionamento junto aos scripts Python e garantir consistência entre código e documentação.

---

## 🚀 Como Executar

### 1. Configurar variáveis de ambiente
```bash
export GOOGLE_CLOUD_PROJECT="ambev-data"
export GOOGLE_APPLICATION_CREDENTIALS="key.json"
```

### 2. Inicializar e aplicar o Terraform
```bash
cd terraform
terraform init
terraform apply -auto-approve
```

### 3. Enviar datasets para o Cloud Storage
Após o Terraform criar o bucket (`ambev-beverage-mvp`), envie os arquivos para o GCS:

```bash
cd ../datasets
gsutil cp abi_bus_case1_beverage_channel_group_20210726.csv gs://ambev-beverage-mvp/raw/
gsutil cp abi_bus_case1_beverage_sales_20210726.csv gs://ambev-beverage-mvp/raw/
```

### 4. Build e push das imagens Docker
```bash
gcloud builds submit --tag gcr.io/ambev-data/etl-bronze .
gcloud builds submit --tag gcr.io/ambev-data/etl-silver .
gcloud builds submit --tag gcr.io/ambev-data/etl-gold .
```

### 5. Executar os jobs no Cloud Run
```bash
gcloud run jobs execute etl-bronze
gcloud run jobs execute etl-silver
gcloud run jobs execute etl-gold
```

---

## 🧭 Roadmap Futuro
- Integração com **Cloud Composer (Airflow)** para agendamento centralizado.  
- Camada de **Data Quality** (Great Expectations / dbt tests).  
- Deploy automatizado via **GitHub Actions**.  
- Versionamento de dados com **BigQuery Time Travel**.  
- Integração dos catálogos YAML com o **GCP Data Catalog**.

---

## 👨‍💻 Autor
**Marcus Vinicius Mendes**  
_Data Engineer Manager – Ambev (Projeto Educacional)_  

[Linkedin](https://www.linkedin.com/in/marcus-mendes-328542146/)

[Apresentação AMBEV](https://docs.google.com/presentation/d/1p1ISb4vnGBLcbU-lpSdGDN-VSlXVLQKHwU9vCY1_KWg/edit?slide=id.g39d1e8344bc_0_38#slide=id.g39d1e8344bc_0_38)

[Looker AMBEV](https://lookerstudio.google.com/u/0/reporting/4de5eb2f-bc81-42d1-8223-eb70cb1b6f3e/page/3v5cF)

📧 mvmendes96@gmail.com  
📍 Curitiba – PR, Brasil  
