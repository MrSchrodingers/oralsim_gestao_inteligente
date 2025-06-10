# Oralsin Gestão Inteligente

> **Sistema completo de gestão de cobranças e notificações inteligentes, baseado em arquitetura DDD/CQRS, com alta observabilidade e automação por meio de mensageria e contêineres.**

## Diagrama de Arquitetura Geral

```mermaid
flowchart TB
    subgraph Infraestrutura
        direction LR
        A[Docker & Docker Compose] --> B[Containers]
        B --> C[PostgreSQL]
        B --> D[Redis]
        B --> E[RabbitMQ]
        B --> F[Celery Worker & Beat]
        B --> G[Prometheus]
        B --> H[Grafana]
    end

    subgraph Aplicação Core
        direction TB
        I[oralsin_core] --> J["Domain (Entidades, Eventos)"]
        J --> K["Application (Comandos, Queries, Handlers)"]
        K --> L[Adapters: API Clients, Repositórios Django, Observability]
    end

    subgraph Interface Django
        direction TB
        M[API Django Rest Framework + Channels] --> N[Views / Serializers / Routers]
        N --> O[Endpoints de Cobrança e Notificação]
        O -->|Envio/Recepção| E[RabbitMQ]
    end

    subgraph Observabilidade
        G --> P["Scrape de Métricas (HTTP, Celery, DB)"]
        H -->|Dashboards| P
    end

    subgraph Fluxos Principais
        direction TB
        Q['1. Registro de Cobertura'] --> R[CommandBus → RegisterCoverageHandler]
        R --> S[OralsinAPIClient → API Externa Oralsin]
        S --> T[Persistência de Clínica / Dados Relacionados]
        T --> U[Emissão de Evento → SyncInadimplencia]

        Q2['2. Sincronização de Inadimplência'] --> V[CommandBus → SyncInadimplenciaHandler]
        V --> W[OralsinAPIClient → Lista de Pacientes / Contratos / Parcelas]
        W --> X[Bulk Upsert em PostgreSQL via Repositórios]

        Q3['3. Fluxo de Notificação'] --> Y[Scheduler Django / Celery Beat → Geração de Agendamentos]
        Y --> Z[RabbitMQ → Fila de Notificação]
        Z --> AA["Celery Worker / Consumer → Notifiers (E-mail, SMS, WhatsApp)"]
        AA --> AB[Persistência de Histórico de Contato]
    end

    C & D & E & F & G & H --> I
    I --> M
    M --> Observabilidade
```

> **Legenda dos Componentes**
>
> * **PostgreSQL**: Banco relacional para armazenar entidades de domínio, histórico de contratos e parcelas.
> * **Redis**: Cache de consultas frequentes e backend para Celery.
> * **RabbitMQ**: Broker de mensageria para filas de notificação.
> * **Celery (Worker & Beat)**: Tarefas assíncronas e agendamento periódico (sync, notificações).
> * **Prometheus & Grafana**: Telemetria de métricas (latência, contadores, gauges) e dashboards em tempo real.
> * **oralsin\_core**: Núcleo de negócio em Python, seguindo DDD/CQRS, com injeção de dependência via Dependency Injector.
> * **Django API**: Camada de interface web (REST + WebSockets), expondo endpoints de cobrança inteligente e notificações.
> * **Notifiers**: Integrações com SendGrid (e-mail), Assertiva (SMS) e DebtApp (WhatsApp).
## Modelo de Dados e Relacionamentos

O diagrama abaixo representa as principais entidades do sistema e seus relacionamentos.

```mermaid
erDiagram
    USER {
        UUID id PK
        string email UNIQUE
        string name
        string role
    }
    CLINIC {
        UUID id PK
        int oralsin_clinic_id UNIQUE
        string name
        string cnpj
    }
    USER_CLINIC {
        UUID id PK
        UUID user_id FK
        UUID clinic_id FK
        string permission
    }
    CLINIC_COVERAGE {
        UUID id PK
        UUID clinic_id FK
        bool active
        date coverage_start
        date coverage_end
    }
    PATIENT {
        UUID id PK
        int oralsin_patient_id UNIQUE
        UUID clinic_id FK
        string name
        string cpf
    }
    CONTRACT {
        UUID id PK
        int oralsin_contract_id UNIQUE
        UUID patient_id FK
        string status
    }
    INSTALLMENT {
        UUID id PK
        UUID contract_id FK
        int number
        date due_date
        decimal amount
        bool received
    }
    FLOW_STEP_CONFIG {
        UUID id PK
        int step_number UNIQUE
        string channels
    }
    MESSAGE {
        UUID id PK
        UUID flow_step_config_id FK
        string type
        text content
    }
    CONTACT_SCHEDULE {
        UUID id PK
        UUID contract_id FK
        UUID flow_step_config_id FK
        datetime scheduled_date
        string status
    }
    CONTACT_HISTORY {
        UUID id PK
        UUID contact_schedule_id FK
        datetime sent_at
        bool success
        text details
    }

    USER ||--o{ USER_CLINIC : "vincula"
    CLINIC ||--o{ USER_CLINIC : "vincula"
    CLINIC ||--o{ CLINIC_COVERAGE : "cobre"
    CLINIC ||--o{ PATIENT : "pertence a"
    PATIENT ||--o{ CONTRACT : "possui"
    CONTRACT ||--o{ INSTALLMENT : "contém"
    FLOW_STEP_CONFIG ||--o{ MESSAGE : "define"
    FLOW_STEP_CONFIG ||--o{ CONTACT_SCHEDULE : "orquestra"
    CONTRACT ||--o{ CONTACT_SCHEDULE : "gera"
    CONTACT_SCHEDULE ||--o{ CONTACT_HISTORY : "registra"
```

> **Detalhamento das Entidades**
>
> * **User**: Representa os usuários do sistema, que podem ter a função de `admin` ou `clinic`.
> * **Clinic**: Armazena as informações básicas das clínicas, como nome e CNPJ, e é a entidade central que conecta pacientes, contratos e usuários.
> * **CoveredClinic**: Indica se uma clínica está habilitada para o serviço de cobrança inteligente.
> * **Patient**: Contém os dados dos pacientes, incluindo informações de contato e um vínculo com sua clínica.
> * **Contract**: Descreve os contratos dos pacientes, com seu status e valores.
> * **Installment**: Representa as parcelas de um contrato, com datas de vencimento e status de pagamento.
> * **FlowStepConfig**: Define as etapas do fluxo de cobrança, especificando os canais de comunicação a serem utilizados em cada passo.
> * **Message**: Armazena os templates de mensagens que serão enviados aos pacientes em cada etapa do fluxo de cobrança.
> * **ContactSchedule**: Agenda os contatos a serem feitos com os pacientes, com base nas regras definidas em `FlowStepConfig`.
> * **ContactHistory**: Mantém um registro de todos os contatos realizados com os pacientes.

---

## Status do Projeto

O sistema está **parcialmente implementado**, com os seguintes fluxos principais em funcionamento:

* **Sincronização de Clínicas e Inadimplência**: O registro de cobertura de clínicas e a sincronização de dados de pacientes, contratos e parcelas com a API externa da Oralsin estão operacionais.
* **Agendamento de Notificações**: A lógica para agendamento de contatos com base em regras de negócio (steps de cobrança) está implementada, com envio efetivo das notificações.
* **Verificação Pipedrive**: A sincronização e verificação de CPF's inadimplentes entre o Banco de dados da Oralsin e do Pipedrive (Implementação via um sistema própio chamado Pipeboad) está operacional, mas as ações estão pendentes.
* **Infraestrutura e Orquestração**: Toda a infraestrutura baseada em Docker e Docker Compose está configurada, permitindo a execução dos serviços de forma integrada (banco de dados, mensageria, cache, etc.).

---

## Índice

1. [Visão Geral do Projeto](#visão-geral-do-projeto)
2. [Casos de Uso & Proposta Comercial](#casos-de-uso--proposta-comercial)
3. [Fluxos de Negócio e Regras](#fluxos-de-negócio-e-regras)
4. [Requisitos de Sistema](#requisitos-de-sistema)
5. [Instalação e Execução](#instalação-e-execução)

   1. [Pré-requisitos](#pré-requisitos)
   2. [Configuração de Ambiente](#configuração-de-ambiente)
   3. [Execução com Docker Compose](#execução-com-docker-compose)
5. [Arquitetura Técnica Detalhada](#arquitetura-técnica-detalhada)

   1. [Camadas de Software](#camadas-de-software)
   2. [Injeção de Dependências](#injeção-de-dependências)
   3. [Padrões e Ferramentas](#padrões-e-ferramentas)
6. [Fluxos de Negócio](#fluxos-de-negócio)

   1. [Registro de Cobertura](#registro-de-cobertura)
   2. [Sincronização de Inadimplência](#sincronização-de-inadimplência)
   3. [Fluxo de Notificações](#fluxo-de-notificações)
7. [Observabilidade e Métricas](#observabilidade-e-métricas)
8. [Scripts de Seeds e CI/CD](#scripts-de-seeds-e-cicd)
9. [Testes Automatizados](#testes-automatizados)
10. [Contato e Suporte](#contato-e-suporte)

---

## Visão Geral do Projeto

O **Oralsin Gestão Inteligente** é um sistema completo para:

* Sincronizar dados de inadimplência de clínicas e pacientes com uma API externa (Oralsin).
* Armazenar e versionar informações de contratos, parcelas e pacientes.
* Gerar regras de notificação automática para cobranças via e-mail, SMS e WhatsApp.
* Expor dashboards de métricas (performance, contagem de registros, métricas de negócio) usando Prometheus e Grafana.
* Permitir configuração de parâmetros de negócio (períodos de vencimento, templates de mensagens, regras de agendamento).

A solução foi projetada para permitir **escala horizontal** (cada componente em contêiner independente), observar performance em tempo real e reduzir a inadimplência de forma automatizada.

---

## Casos de Uso & Proposta Comercial

1. **Clínicas de Saúde & Planos de Saúde**

   * **Problema**: Alto índice de inadimplência em consultas e procedimentos.
   * **Solução**:

     * Sincronização diária ou sob demanda com base em parâmetros configuráveis (períodos, filtros).
     * Geração automática de notificações de cobrança que combinam canais (e-mail, SMS, WhatsApp), aumentando cobertura de comunicação.
     * Dashboards para monitorar KPI’s, como taxa de recuperação, tempo médio para pagamento e volume de notificações enviadas.

2. **Serviços Financeiros e Cobranças Terceirizadas**

   * **Problema**: Processos de cobrança manuais, comunicação fragmentada e falta de centralização de métricas de contato.
   * **Solução**:

     * Histórico completo de contatos e campanhas segmentadas por perfil de paciente/clínica.
     * Redução de custos operacionais, pois o sistema lida automaticamente com falhas de entrega (retry) e fallback entre canais.

3. **Telemedicina & Clínicas Remotas**

   * **Problema**: Dificuldade em acompanhar pagamentos a distância e falta de confirmação de recebimento.
   * **Solução**:

     * Relatórios semanais de inadimplência enviados automaticamente aos gestores.

4. **Valor Comercial**

   * **Diferenciais**:

     * Arquitetura modular que permite integração com novos canais (Telegram, Firebase, etc.).
     * Métricas em tempo real para tomada de decisão ágil.

---

## Fluxos de Negócio e Regras

### 1. Registro de Cobertura e Sincronização Inicial

**Objetivo**: Cadastrar uma nova clínica no sistema e realizar a primeira sincronização de dados de inadimplência.

**Regras de Negócio**:

* Um usuário `admin` pode registrar uma nova clínica pelo nome.
* O sistema busca a clínica na API da Oralsin e, se encontrada, armazena seus dados localmente.
* Após o registro, uma sincronização inicial de inadimplência é disparada automaticamente para a nova clínica.
* A sincronização busca pacientes, contratos e parcelas em um intervalo de datas pré-definido.
* Os dados recebidos da API são persistidos no banco de dados local, atualizando registros existentes se necessário (upsert).

### 2. Sincronização de Inadimplência Contínua

**Objetivo**: Manter os dados de inadimplência do sistema atualizados com a API da Oralsin.

**Regras de Negócio**:

* A sincronização é executada periodicamente por uma tarefa agendada (Celery Beat).
* O processo é semelhante à sincronização inicial, mas focado em atualizar os dados existentes.
* A cada execução, o sistema incrementa métricas no Prometheus para monitoramento, como `SYNC_RUNS`, `SYNC_PATIENTS`, e `SYNC_DURATION_SECONDS`.

### 3. Fluxo de Notificações de Cobrança

**Objetivo**: Notificar os pacientes sobre parcelas em atraso de forma automática e escalonada.

**Regras de Negócio**:

* O sistema verifica periodicamente os agendamentos de contato (`ContactSchedule`) que estão pendentes e com a data de envio vencida.
* Para cada agendamento, o sistema:
    1.  Renderiza a mensagem apropriada (`Message`) para a etapa (`FlowStepConfig`) e o canal de comunicação definidos.
    2.  Envia a notificação para o paciente através do canal especificado (e-mail, SMS ou WhatsApp).
    3.  Registra o envio (ou a falha) no histórico de contatos (`ContactHistory`).
    4.  Se o envio for bem-sucedido, avança o fluxo de cobrança para a próxima etapa, se houver.
* O sistema permite o envio de notificações manuais através de um endpoint específico.

### 4. Escalonamento de Dívidas Antigas

**Objetivo**: Identificar dívidas muito antigas e escaloná-las para um processo de cobrança diferenciado.

**Regras de Negócio**:

* Uma tarefa periódica (`SyncOldDebtsCommand`) identifica parcelas vencidas há mais de 90 dias.
* Para cada dívida identificada, o sistema cria um `CollectionCase`, que representa um caso de cobrança a ser tratado de forma especial.
* Se a dívida já estiver associada a um `deal` em um sistema externo (como o Pipedrive), essa informação é vinculada ao `CollectionCase`.
* Um evento `DebtEscalatedEvent` é disparado para notificar outros sistemas sobre o escalonamento da dívida.

---

## Requisitos de Sistema

* **Hardware Sugerido (ambiente de produção)**

  * CPU: 4 vCPUs
  * Memória RAM: 8 GB
  * Armazenamento: 50 GB SSD
  * Rede: 1 Gbps

* **Software / Dependências**

  * Docker Engine >= 20.10
  * Docker Compose >= 1.29
  * Python 3.13 (para desenvolvimento local, opcional)
  * Git (para versionamento)

---

## Instalação e Execução

### Pré-requisitos

1. **Instalar Docker e Docker Compose**

   * Ubuntu/Debian:

     ```bash
     sudo apt update
     sudo apt install -y docker.io docker-compose
     sudo systemctl enable docker
     sudo usermod -aG docker $USER
     ```
   * Windows ou macOS: Instalar Docker Desktop (incluir Docker Compose).

2. **Clonar o Repositório**

   ```bash
   git clone https://github.com/SeuUsuario/oralsin-gestao-inteligente.git
   cd oralsin-gestao-inteligente
   ```

### Configuração de Ambiente

1. **Variáveis de Ambiente**
   Copie o arquivo de exemplo e ajuste as variáveis conforme seu ambiente:

   ```bash
   cp .env.example .env
   ```

   Edite `.env` definindo:

   ```ini
   # Dados do PostgreSQL
   POSTGRES_USER=oralsin_user
   POSTGRES_PASSWORD=oralsin_pass
   POSTGRES_DB=oralsin_db
   POSTGRES_PORT=5432

   # Dados do Redis
   REDIS_HOST=redis
   REDIS_PORT=6379
   REDIS_PASSWORD= # vazio se não usar senha

   # Dados do RabbitMQ
   RABBITMQ_DEFAULT_USER=oralsin
   RABBITMQ_DEFAULT_PASS=oralsin_pass
   RABBITMQ_DEFAULT_VHOST=/oralsin

   # Configurações Celery
   CELERY_BROKER_URL=amqp://oralsin:oralsin_pass@rabbitmq:5672/oralsin
   CELERY_RESULT_BACKEND=redis://:password@redis:6379/0

   # Configurações Oralsin API
   ORALSIN_API_BASE_URL=https://api.oralsin.com.br
   ORALSIN_API_KEY=seu_token_oralsin

   # Configurações JWT
   JWT_SECRET_KEY=sua_chave_secreta
   JWT_ALGORITHM=HS256
   JWT_EXPIRATION_SECONDS=3600

   # Ambiente Django
   DJANGO_SETTINGS_MODULE=src.settings

   # Logs e Observabilidade
   PROMETHEUS_PORT=9108
   ```

2. **Portas Expostas**

   * **8000**: Django (API REST + WebSockets)
   * **6379**: Redis
   * **5432**: PostgreSQL
   * **5672**: RabbitMQ
   * **15672**: RabbitMQ Management UI
   * **6379**: Redis
   * **9095**: Prometheus
   * **3000**: Grafana
   * **9108**: Métricas HTTP

### Execução com Docker Compose

1. **Build & Up**
   No diretório raiz, execute:

   ```bash
   docker-compose up -d --build
   ```

   Isso irá criar e subir os containers:

   * `postgres` (PostgreSQL)
   * `redis` (Redis)
   * `rabbitmq` (RabbitMQ + Management UI)
   * `celery_worker` (Celery Worker)
   * `celery_beat` (Celery Beat)
   * `django_app` (API Django + Core Python)
   * `prometheus` (Prometheus Server)
   * `grafana` (Grafana com dashboards provisionados)

2. **Verificar Logs**
   Para acompanhar logs de todos os serviços:

   ```bash
   docker-compose logs -f
   ```

   Ou de um serviço específico:

   ```bash
   docker-compose logs -f django_app
   ```

3. **Migrações e Seeds**
   Após subir, abra um shell no container Django e execute:

   ```bash
   docker-compose exec django_app bash
   python manage.py migrate
   python manage.py loaddata seed_initial_data.json
   ```

   (Se houver comandos de seed específicos, consulte [Scripts de Seeds](#scripts-de-seeds-e-cicd)).

4. **Acesso aos Serviços**

   * **API Django**: `http://localhost:8000/api/`
   * **RabbitMQ Management**: `http://localhost:15672/` (usuário/senha: definidos em `.env`)
   * **Prometheus**: `http://localhost:9095/`
   * **Grafana**: `http://localhost:3000/` (usuário/senha padrão: admin / admin)

---

## Arquitetura Técnica Detalhada

### Camadas de Software

1. **Infraestrutura**

   * **Docker & Docker Compose**: Define orquestração de serviços e redes internas.
   * **Makefile**: Atalhos para rebuild, seeds, testes e manutenção.
   * **Scripts Bash** (`docker-entrypoint.sh`, `rabbit_consumer_entrypoint.py`): Inicialização de serviços e consumers.

2. **Core (DDD + CQRS)**

   * **`libs/oralsin_core/domain`**:

     * Entidades (ex.: `ClinicEntity`, `PatientEntity`, `ContractEntity`, `InstallmentEntity`).
     * Value Objects (ex.: `Money`, `Address`).
     * Eventos de Domínio (ex.: `CoveredClinicRegisteredEvent`, `PaymentReceivedEvent`).
   * **`libs/oralsin_core/application`**:

     * **Commands**: DTOs para operações de escrita (ex.: `RegisterCoverageClinicCommand`, `SyncInadimplenciaCommand`).
     * **Command Handlers**: Implementam a lógica de negócio para cada comando (ex.: `RegisterCoverageClinicHandler`).
     * **Queries**: DTOs para operações de leitura paginadas e não-paginadas (ex.: `ListPatientsInDebtQuery`).
     * **Query Handlers**: Retornam dados por meio de repositórios (ex.: `GetDashboardSummaryHandler`).
   * **`libs/oralsin_core/adapters`**:

     * **API Clients** (`OralsinAPIClient`): Encapsula chamadas HTTP à API externa, usando Pydantic para validação de payload.
     * **Repositórios Django** (`PatientRepoImpl`, `ContractRepoImpl`, etc.): Implementam interfaces de repositório abstraídas nas entidades de domínio, fazendo o mapeamento entre entidades e modelos Django.
     * **Observability** (`decorators.py`, `metrics.py`): Decoradores para métricas (contagem, latência), endpoint ASGI para Prometheus.
     * **Segurança** (`HashService`, `JWTService`): Implementa hashing de senhas e autenticação JWT.

3. **Interface Django**

   * **Aplicativo Django Principal** (`src/`):

     * `settings.py`: Configurações de banco, cache, mensageria, CORS, middleware, apps instalados.
     * `urls.py`: Rotas API (versão, autenticação, endpoints de cobrança e notificação).
     * **Apps Django**:

       * `cobranca_inteligente_api`: Views e serializers responsáveis por endpoints de cobertura e sincronização de inadimplência.
       * `cordial_billing`: Lógica de integração com sistemas de cobrança externos (e.g., Pipedrive), sync de dívidas.
       * `notification_billing`: Configura comandos, queries e handlers para geração de agendamentos, publicação em RabbitMQ e processamento de notificações.
       * `plugins/django_interface`: Modelos Django que representam entidades de domínio, testes unitários, comandos de management para seeds.

4. **Mensageria e Tarefas Assíncronas**

   * **RabbitMQ**: Fila por clima de prioridade:

     * `queue_email`
     * `queue_sms`
     * `queue_whatsapp`
   * **Celery Worker**: Consome tarefas agendadas (por Celery Beat) e filas de notificação.
   * **Celery Beat**: Agendador periódico (ex.: rotinas de sincronização diária de inadimplência).

### Injeção de Dependências

* **Dependency Injector** (`libs/oralsin_core/adapters/config/composition_root.py`):

  * Conta com um container que efetua “wiring” (injeção automática) nos módulos Python.
  * Componentes registrados:

    * `ClinicRepository`, `PatientRepository`, `ContractRepository`, `InstallmentRepository`
    * `OralsinAPIClient`, `HashService`, `JWTService`
    * `RegisterCoverageClinicHandler`, `SyncInadimplenciaHandler`, `NotificationService`
    * `CommandBus`, `QueryBus`
  * Benefícios:

    * Baixo acoplamento e facilidade de testes (mock containers).
    * Configuração centralizada de singletons e escopos (ex.: repositório por request).

### Padrões e Ferramentas

* **Domain-Driven Design (DDD)**:

  * Isola regras de negócio nas entidades e serviços de domínio.
  * Usa eventos para notificar mudanças importantes em agregados (ex.: clínica registrada, dívida quitada).
* **CQRS (Command Query Responsibility Segregation)**:

  * Comandos (escrita) e Queries (leitura) segregados em módulos distintos, com handlers independentes.
  * Permite otimizar leitura (cache Redis, consultas específicas) sem impactar performance de escrita.
* **Repository Pattern**:

  * Interface de repositório (contrato), com implementação usando Django ORM (bulk inserts, transactions controladas).
* **Observabilidade**:

  * **Structlog**: Logs estruturados em JSON, enriquecidos com contexto (ID de correlação, nome do handler).
  * **Prometheus Client**: Métricas personalizadas (histogramas de latência, contadores de sincronização, gauges de fila RabbitMQ).
  * **Grafana**: Dashboards pré-configurados (ex.: dashboard de Sincronização, dashboard de Notificações, dashboard de Saúde do Sistema).
* **Testes Automatizados**:

  * **pytest** + **pytest-django**: Testes unitários para handlers de comando, queries e adapters.
  * Fixtures para mocks de API Oralsin, bancos de dados em memória (SQLite) e filas (kombu in-memory).

---

## Fluxos de Negócio

### 1. Registro de Cobertura

1. **Usuário ou Sistema Externo** envia requisição `POST /api/coverage/register` com payload:

   ```json
   {
     "clinic_name": "Clínica Exemplo LTDA",
     "external_id": "123456"
   }
   ```
2. **Django View** (`CoverageViewSet.register`) valida dados via serializer e despacha `RegisterCoverageClinicCommand`.
3. **CommandBus** invoca `RegisterCoverageClinicHandler`:

   * **OralsinAPIClient.get\_clinics(filter=clinic\_name)** → retorna lista de `OralsinClinicDTO`.
   * Para cada DTO:

     * Mapeia para `ClinicEntity`.
     * Persiste/atualiza em `ClinicRepoImpl` (tabela `plugins_django_interface.Clinic`).
     * Persiste dados associados (endereço, telefones) em tabelas relacionadas.
     * Cria `CoveredClinicEntity` e persiste em `CoveredClinic` → Gera evento `CoveredClinicRegisteredEvent`.

       * Exemplo de evento JSON:

         ```json
         {
           "event_type": "CoveredClinicRegistered",
           "payload": {
             "clinic_id": 42,
             "external_id": "123456",
             "timestamp": "2025-06-04T10:00:00Z"
           }
         }
         ```
   * Por fim, despacha `SyncInadimplenciaCommand(external_id, data_inicio=today, data_fim=today)`.
4. **Resposta HTTP**:

   ```json
   {
     "status": "success",
     "message": "Cobertura de clínica registrada e sincronização agendada."
   }
   ```

### 2. Sincronização de Inadimplência

1. **Agendamento**:

   * Pode ser acionado automaticamente após registro de cobertura ou periodicamente por Celery Beat (ex.: todos os dias às 02:00).
   * Celery Beat executa tarefa `run_sync_inadimplencia`, que publica `SyncInadimplenciaCommand` no `command_queue`.

2. **Execução do Handler** (`SyncInadimplenciaHandler`):

   * Recebe `SyncInadimplenciaCommand(external_id, data_inicio, data_fim)`.
   * **Obter Clínica Local**: `ClinicRepoImpl.get_by_external_id(external_id)`.
   * **Chamar OralsinAPIClient.get\_inadimplencia({external\_id, data\_inicio, data\_fim})** → retorna lista de pacientes, contratos e parcelas (DTOs).
   * Para cada `OralsinPacienteDTO`:

     1. Mapeia para `PatientEntity`, persiste via `PatientRepoImpl` (tabela `plugins_django_interface.Patient`).
     2. Persiste telefones em `PatientPhone`.
     3. Mapeia `OralsinContratoDTO` para `ContractEntity`, persiste em `ContractRepoImpl`.
     4. Mapeia lista de `OralsinParcelaDTO` e `OralsinParcelaAtualDetalheDTO` para `InstallmentEntity`.
     5. Realiza **bulk upsert** em `Installment` (método `merge_installments`):

        * Carrega registros existentes em intervalo de datas.
        * Compara atributos (valor, vencimento, status) e atualiza somente campos alterados.
   * Incrementa métricas em Prometheus:

     * `SYNC_RUNS{clinic=external_id}`
     * `SYNC_PATIENTS{clinic=external_id}`
     * `SYNC_DURATION_SECONDS{clinic=external_id}`
   * Finaliza com log estruturado:

     ```json
     {
       "event": "SyncInadimplenciaCompleted",
       "clinic_external_id": "123456",
       "total_patients": 120,
       "duration_seconds": 45.3
     }
     ```

3. **Resultado Final**: Banco atualizado com novas informações de inadimplência. Caso haja mudanças em parcelas, isso refletirá nos relatórios e notificações geradas posteriormente.

### 3. Fluxo de Notificações

1. **Configuração de Regras**

   * Via Django Admin ou endpoints de configuração, o usuário define:

     * Templates de mensagem (e-mail, SMS, WhatsApp) em `NotificationTemplate`.
     * Regras de agendamento (ex.: “Enviar 1 dia antes do vencimento, se parcela não quitada”).
   * O sistema popula registros em `ContactSchedule` (modelo Django), contendo:

     ```json
     {
       "clinic_id": 42,
       "patient_id": 101,
       "contract_id": 202,
       "installment_id": 303,
       "scheduled_date": "2025-06-05T08:00:00Z",
       "channel": "email",
       "template_id": 10
     }
     ```

2. **Publicação em RabbitMQ**

   * Celery Beat ou tarefa periódica verifica `ContactSchedule` para agendamentos do dia:

     * Para cada registro pendente, publica mensagem JSON na fila apropriada:

       * Fila `queue_email` para notificações por e-mail.
       * Fila `queue_sms` para notificações por SMS.
       * Fila `queue_whatsapp` para notificações por WhatsApp.

3. **Consumo e Envio**

   * **Celery Worker / Rabbit Consumer** consome as mensagens:

     * Deserializa payload e identifica canal.
     * Carrega `NotificationTemplate` correspondente (conteúdo, assunto, variáveis dinâmicas).
     * Formata mensagem (substitui placeholders: nome do paciente, valor, data de vencimento).
     * Chama o respectivo Notifier:

       * **SendGridNotifier** → envia e-mail.
       * **AssertivaNotifier** → envia SMS.
       * **DebtAppNotifier** → envia WhatsApp.
     * Caso ocorra falha de entrega, registra tentativa em `NotificationRetry` e aplica política de retry (ex.: 3 tentativas, intervalo exponencial).

4. **Persistência de Histórico**

   * Após envio (ou falha após todas as tentativas), cria registro em `ContactHistory`:

     ```json
     {
       "patient_id": 101,
       "installment_id": 303,
       "channel": "email",
       "sent_at": "2025-06-05T08:02:15Z",
       "status": "success", 
       "error_message": null
     }
     ```
   * Métricas relacionadas à notificação são incrementadas em Prometheus:

     * `NOTIFICATIONS_SENT_TOTAL{channel="email"}`
     * `NOTIFICATIONS_FAILED_TOTAL{channel="email"}`

---

## Observabilidade e Métricas

1. **Exposição de Métricas (Endpoint `/metrics`)**

   * Implementado em `libs/oralsin_core/adapters/observability/metrics.py` usando **Prometheus Python Client**.
   * Métricas expostas:

     * **Contadores**

       * `SYNC_RUNS_total{clinic}`: Quantas vezes a sincronização foi executada para cada clínica.
       * `SYNC_PATIENTS_total{clinic}`: Quantidade total de pacientes sincronizados.
       * `NOTIFICATIONS_SENT_total{channel}`: Total de notificações enviadas por canal.
       * `NOTIFICATIONS_FAILED_total{channel}`: Total de notificações com erro.
     * **Histogramas**

       * `SYNC_DURATION_seconds{clinic}`: Tempo de execução de cada sincronização.
       * `NOTIFICATION_DURATION_seconds{channel}`: Tempo de envio de cada notificação.
     * **Gauges**

       * `CACHE_HITS{query}` / `CACHE_MISSES{query}`: Taxa de hits e misses no Redis.
       * `RABBITMQ_QUEUE_LENGTH{queue}`: Tamanho de cada fila RabbitMQ (via exporter).
   * **Prometheus Server** configura `scrape_configs` em `prometheus.yml` para coletar:

     * Endpoint `/metrics` do Django (porta 9108).
     * Exporter do Celery (porta 9150).
     * Exporter do PostgreSQL (pg\_exporter, porta 9187).
     * Exporter do RabbitMQ (rabbitmq\_exporter, porta 9419).

2. **Dashboards Grafana**

   * Provisionados em `grafana/provisioning/dashboards/*.json` e `datasources.yml`.
   * Dashboards disponíveis:

     * **Sincronização de Inadimplência**:

       * Gráficos de latência de sync, contagem de pacientes, taxa de erros.
     * **Notificações**:

       * Volume de notificações por canal (diário, semanal, mensal).
       * Taxa de sucesso vs. falhas.
       * Tempo médio de envio.
     * **Saúde do Sistema**:

       * Utilização de CPU e memória dos containers.
       * Tamanho das filas RabbitMQ.
       * Latência de consultas ao PostgreSQL.

3. **Logs Estruturados (Structlog)**

   * Todos os componentes (handlers, services, API clients) utilizam **structlog** para gerar logs em JSON:

     * Campos comuns: `timestamp`, `level`, `module`, `event`, `message`, `contexto` (ID de correlação, usuário).
   * Exemplo:

     ```json
     {
       "timestamp": "2025-06-04T10:05:23.456Z",
       "level": "INFO",
       "module": "SyncInadimplenciaHandler",
       "event": "ParcelasAtualizadas",
       "clinic_external_id": "123456",
       "installment_id": 987,
       "updated_fields": ["valor", "status"]
     }
     ```
   * Esses logs podem ser coletados por soluções como **ELK Stack** (Elasticsearch, Logstash, Kibana) ou **Grafana Loki**.

---

## Scripts de Seeds e CI/CD

### Makefile

```makefile
# Makefile - tarefas de desenvolvimento e CI

# Reconstruir apenas o container da aplicação Django
.PHONY: rebuild-app
rebuild-app:
	docker-compose build django_app
	docker-compose up -d django_app

# Reconstruir todos os containers (limpa volumes e caches)
.PHONY: rebuild-all
rebuild-all:
	docker-compose down -v --remove-orphans
	docker-compose up -d --build

# Popula dados iniciais (seeds)
.PHONY: seed-complete
seed-complete:
	docker-compose exec django_app python manage.py migrate
	docker-compose exec django_app python manage.py loaddata seed_clinics.json
	docker-compose exec django_app python manage.py loaddata seed_templates.json
	docker-compose exec django_app python manage.py loaddata seed_schedules.json

# Executar testes de notificação em modo real
.PHONY: test-notifications
test-notifications:
	docker-compose exec django_app pytest tests/test_notifications.py

# Verificar status dos containers
.PHONY: ps
ps:
	docker-compose ps

# Limpar volumes e imagens não utilizados
.PHONY: clean
clean:
	docker system prune -f
	docker volume prune -f
```

### Pipeline CI/CD (exemplo GitHub Actions)

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Build Docker Images
        run: |
          docker-compose build

      - name: Run Migrations & Seeds
        run: |
          docker-compose up -d postgres redis rabbitmq
          docker-compose up -d django_app
          sleep 10
          docker-compose exec django_app python manage.py migrate
          docker-compose exec django_app python manage.py loaddata seed_initial_data.json

      - name: Run Tests
        run: |
          docker-compose exec django_app pytest --maxfail=1 --disable-warnings -q

      - name: Push Images to Registry
        if: github.ref == 'refs/heads/main'
        run: |
          docker login -u ${{ secrets.DOCKER_USER }} -p ${{ secrets.DOCKER_PASS }}
          docker tag oralsin_gestao_inteligente_django_app:latest seu-registry/oralsin_app:latest
          docker push seu-registry/oralsin_app:latest
```

---

## Testes Automatizados

* **Local de Testes**:

  * Usa **pytest** com banco de dados em memória (SQLite) para isolar testes de lógica.
  * Para isolar filas, configura `CELERY_TASK_ALWAYS_EAGER=True` em `settings.py`.

* **Estrutura de Testes**:

  ```
  tests/
  ├── test_coverage.py          # Testes de registro de cobertura e handlers
  ├── test_sync_inadimplencia.py # Testes de sincronização de inadimplência
  ├── test_notifications.py     # Testes de fluxo de notificações (integração com mocks)
  ├── conftest.py               # Fixtures comuns (API client mock, DB setup)
  └── helpers/
      └── mock_oralsin_client.py # Implementação de OralsinAPIClient simulado
  ```

* **Exemplo de Teste de Sincronização** (`tests/test_sync_inadimplencia.py`):

  ```python
  import pytest
  from oralsin_core.application.handlers.sync_inadimplencia_handler import SyncInadimplenciaHandler
  from tests.helpers.mock_oralsin_client import MockOralsinClient
  from oralsin_core.adapters.repositories.patient_repo import PatientRepoImpl

  @pytest.fixture
  def mock_client(monkeypatch):
      monkeypatch.setattr("oralsin_core.adapters.api_clients.OralsinAPIClient", MockOralsinClient)
      return MockOralsinClient()

  @pytest.mark.django_db
  def test_sync_inadimplencia_executes(mock_client, db):
      handler = SyncInadimplenciaHandler()
      command = SyncInadimplenciaCommand(external_id="123456", data_inicio="2025-06-01", data_fim="2025-06-01")
      result = handler.handle(command)
      patients = PatientRepoImpl().list_all()
      assert len(patients) == 2
  ```

## Contato e Suporte

Caso necessite de suporte técnico, customização ou queira adquirir licenças corporativas:

* **E-mail**: [mrschrodingers@gmail.com.br](mailto:suporte@suporte.com)
* **Nome**: Matheus Munhoz

Para contribuir com o projeto ou reportar issues, acesse o repositório no GitHub:

```
https://github.com/SeuUsuario/oralsin-gestao-inteligente
```

---

> **Licença**: MIT License
> **Autor**: -----