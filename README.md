# Log Intelligence

**An AI-powered log analysis platform that ingests logs from multiple sources, clusters them by semantic similarity, and answers natural-language questions about what's happening in your systems.**

[![Java](https://img.shields.io/badge/Java-21-007396?logo=openjdk&logoColor=white)](#)
[![Spring Boot](https://img.shields.io/badge/Spring_Boot-3-6DB33F?logo=spring&logoColor=white)](#)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](#)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)](#)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](#)
[![Kafka](https://img.shields.io/badge/Apache_Kafka-7.5-231F20?logo=apachekafka&logoColor=white)](#)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-8.11-005571?logo=elasticsearch&logoColor=white)](#)

Ask your logs things like *"show payment service errors in the last 6 hours"* and get a human-readable summary of what went wrong, automatically clustered into related incidents.

---

## Architecture

```
                ┌─────────────────────────────────────────┐
                │  Log Sources (7+)                       │
                │  ─────────────────                      │
                │  • Files (any app)                      │
                │  • nginx / Apache access logs           │
                │  • Windows Event Log                    │
                │  • GitHub Actions (CI runs)             │
                │  • MariaDB / PostgreSQL logs            │
                │  • Docker container stdout              │
                └────────────────┬────────────────────────┘
                                 │  Kafka producer
                                 ▼
                        ┌────────────────┐
                        │  Apache Kafka  │  app-logs topic
                        └────────┬───────┘
                                 │
                                 ▼
              ┌──────────────────────────────────┐
              │  Spring Boot Backend             │
              │  • Kafka consumer → ES indexer   │
              │  • REST API (RBAC + JWT)         │
              │  • WebSocket push for live UI    │
              └────────┬─────────────┬───────────┘
                       │             │
              ┌────────▼─────┐  ┌────▼─────────┐
              │ Elasticsearch│  │   MongoDB    │
              │ (log search) │  │   (users)    │
              └──────────────┘  └──────────────┘
                       ▲
                       │  REST search
                       │
              ┌────────┴───────────────┐
              │  Python AI Service     │
              │  • NL → filter parser  │
              │  • Sentence embeddings │
              │  • K-Means clustering  │
              │  • LLM root-cause      │
              │    summarization (Groq)│
              └────────┬───────────────┘
                       │  /analyze
                       ▼
              ┌────────────────────────┐
              │  React Frontend (Vite) │
              │  • Auth + dashboard    │
              │  • Charts & filters    │
              │  • Live WebSocket feed │
              └────────────────────────┘
```

---

## What it does

- **Ingests logs in real time** from heterogeneous sources via a unified Python collector framework
- **Indexes into Elasticsearch** through a Spring Boot Kafka consumer for fast search
- **Parses natural-language queries** with an LLM into structured filters (level, service, time window)
- **Embeds matching logs** using `text-embedding-3-small`-class sentence vectors
- **Clusters semantically similar errors** with K-Means so 50 stack traces become 3 incidents
- **Generates root-cause summaries** with an LLM, citing representative log lines per cluster
- **Enforces role-based access** — `BASIC_USER` sees only their team's logs, `ADMIN` sees everything
- **Streams new logs to the UI** via WebSocket without polling

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, Tailwind CSS, Recharts, Axios |
| Backend | Spring Boot 3, Spring Security, Spring Kafka, Elasticsearch Java Client |
| AI Service | Python 3.11, Flask, scikit-learn, Groq SDK (Llama 3.3) |
| Log Collectors | Python 3.11, kafka-python-ng, watchdog, docker-py, pywin32 |
| Data | Apache Kafka, Elasticsearch 8.11, MongoDB 7, Kibana |
| Auth | JWT (HS256), BCrypt, RBAC via Spring Security |
| Infra | Docker Compose, nginx (frontend), GitHub Actions (CI) |

---

## Quick start

### Prerequisites

- Docker Desktop (Windows / macOS / Linux)
- A free [Groq API key](https://console.groq.com) for the LLM calls
- ~4 GB free RAM (Elasticsearch alone takes 1 GB)

### Run the stack

```bash
git clone https://github.com/Devanshadlakha/log-intelligence
cd log-intelligence

# Configure secrets
cp .env.example .env
# Edit .env — fill in GROQ_API_KEY and generate strong MONGO_PASS / JWT_SECRET

# Bring everything up
docker compose up -d --build

# Open the dashboard
# Windows / macOS / Linux  →  http://localhost
```

That's it. The compose file boots Zookeeper, Kafka, Elasticsearch, Kibana, MongoDB, the Spring backend, the AI service, the React frontend, and the log-collectors process.

### Generate strong secrets

```bash
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(64))"
python -c "import secrets; print('MONGO_PASS=' + secrets.token_urlsafe(24))"
```

### Optional: Windows Event Log capture

The Linux container can't read Windows Event Viewer, so a host-side process handles it:

```cmd
start-windows-collector.bat
```

This pushes Windows System / Application events into the same Kafka topic alongside the Docker stack.

---

## Configuration

### `.env` (project root)

```ini
GROQ_API_KEY=gsk_...
MONGO_USER=logadmin
MONGO_PASS=<strong random string>
JWT_SECRET=<at least 64 chars random>
CORS_ORIGINS=http://localhost
GITHUB_TOKEN=<optional, for higher GitHub API rate limits>
```

### `log-collectors/config.docker.yaml`

Drives which sources are tailed inside the container. Each collector supports a `min_level` filter (`INFO` / `WARN` / `ERROR`) so noisy sources only surface real problems:

```yaml
collectors:
  file_watcher:
    enabled: true
    paths:
      - path: "/var/log/mariadb/general.log"
        service_name: "mariadb"
      - path: "/var/log/app/myapp.log"
        service_name: "myapp"

  web_server:
    enabled: true
    files:
      - path: "/var/log/nginx-volume/access.log"
        service_name: "nginx"
        min_level: WARN     # only 4xx/5xx

  github_actions:
    enabled: true
    repositories:
      - owner: "your-username"
        repo:  "your-repo"
    poll_interval_seconds: 60

  docker:
    enabled: true
    min_level: WARN
    containers:
      - log-backend
      - log-ai-service
      - log-frontend
```

---

## Project structure

```
log-intelligence/
├── backend/                  Spring Boot — REST + Kafka consumer + WebSocket
│   └── src/main/java/com/logintel/
│       ├── auth/             JWT, BCrypt, role-based access control
│       ├── consumer/         Kafka → Elasticsearch indexer
│       ├── search/           REST API + ES query builder
│       ├── websocket/        STOMP/SockJS for live UI feed
│       └── config/           Kafka, security, CORS configuration
│
├── ai-service/               Python Flask — query parser + clustering + LLM
│   ├── app.py                /analyze entry point
│   ├── query_parser.py       NL → structured filter (Groq)
│   ├── embeddings.py         Sentence vectorization
│   ├── clustering.py         K-Means on log embeddings
│   ├── summarizer.py         LLM root-cause summaries
│   ├── anomaly_detection.py  Outlier detection on log volumes
│   ├── hybrid_search.py      Keyword + semantic hybrid scoring
│   └── cache.py              In-memory cache for repeated queries
│
├── frontend/                 React + Vite + Tailwind
│   ├── nginx.conf            Reverse-proxy backend & AI service
│   └── src/components/       Dashboard, charts, search, auth
│
├── log-collectors/           Pluggable source adapters
│   └── collectors/
│       ├── file_watcher.py     Tail any log file
│       ├── web_server.py       Parse Common Log Format
│       ├── windows_event.py    pywin32 → Event Viewer
│       ├── github_actions.py   Poll GitHub API
│       ├── database.py         MariaDB / PostgreSQL logs
│       └── docker_logs.py      docker-py stream
│
├── docker-compose.yml        One-command stack
└── .env.example              Secret template
```

---

## Log sources at a glance

| Source | Format | Service tag | Level mapping |
|--------|--------|-------------|---------------|
| File Watcher | Any (configurable regex) | configurable | INFO / WARN / ERROR / FATAL → mapped |
| Web Server | nginx Combined Log Format | `nginx` | 2xx/3xx → INFO, 4xx → WARN, 5xx → ERROR |
| Windows Event | pywin32 EventLog API | `windows-event-{type}` | EventType → mapped |
| GitHub Actions | GitHub REST API | `github-actions-{repo}` | success → INFO, cancelled → WARN, failure → ERROR |
| Database | MySQL/PostgreSQL log files | `mysql` / `postgresql` | Parsed from log prefix |
| Docker | Docker SDK log stream | `docker-{container}` | Extracted from line via regex |

---

## API

### `POST /analyze` (AI service, port 5000)

```json
{ "query": "show payment service errors in last 6 hours", "timeRange": "6" }
```

Returns clusters, a root-cause summary, and the matching logs.

### `GET /api/logs/search` (backend, port 8080)

```
?level=ERROR&service=nginx&keyword=timeout&hoursAgo=24
```

Returns up to 200 logs, role-filtered.

### `GET /api/logs/services`

Returns the distinct service list — used by the AI service for dynamic service discovery in NL queries.

---

## Roles

| Role | Sees |
|------|------|
| `BASIC_USER` | Only sources tagged with their `allowedSources` |
| `DEVELOPER` | All `application` and `infra` logs |
| `ADMIN` | Everything |

Roles are enforced at the service layer in Spring, and the JWT is forwarded from the AI service to the backend so RBAC applies end-to-end.

---

## Production deployment

Designed to run on a single 4 GB Linux VM (Hetzner / DigitalOcean / Oracle Cloud Free Tier):

1. Push the repo to a server, copy a populated `.env`.
2. `docker compose up -d --build`.
3. Put a TLS-terminating reverse proxy (Caddy or nginx + certbot) in front of port 80.
4. Add your domain to `CORS_ORIGINS`.
5. Enable Elasticsearch auth before exposing the host beyond your IP.

Internal service ports (9200 ES, 9092 Kafka, 27017 Mongo) are bound to `127.0.0.1` by default and are **not** reachable from the public internet.

---

## Author

**Devansh Adlakha**
[GitHub](https://github.com/Devanshadlakha) · devadilak13@gmail.com
