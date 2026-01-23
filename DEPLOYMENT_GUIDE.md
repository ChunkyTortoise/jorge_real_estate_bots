# Deployment Guide - Jorge's Real Estate AI Bots

**Production deployment setup for high-availability, scalable platform**

## 🎯 Deployment Overview

### Infrastructure Strategy
- **Development**: Local Docker setup
- **Staging**: DigitalOcean App Platform
- **Production**: DigitalOcean App Platform → AWS (for scale)
- **Monitoring**: DataDog + Sentry
- **CI/CD**: GitHub Actions

### Performance Targets
- **Response Time**: <500ms for lead analysis (5-minute rule compliance)
- **Uptime**: 99.9% during business hours
- **Scaling**: Support 50+ concurrent agents
- **Security**: SOC 2 Type II compliant

---

## 🏗️ PHASE 1: DEVELOPMENT ENVIRONMENT

### Local Development Setup

#### Prerequisites
```bash
# Install required tools
brew install docker docker-compose postgresql redis
pip install docker-compose

# Clone repository
git clone <repository-url>
cd jorge_real_estate_bots
```

#### Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your keys
nano .env
```

#### `.env` Configuration
```bash
# Core Application
DEBUG=true
ENVIRONMENT=development
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/jorge_bots_dev
REDIS_URL=redis://localhost:6379

# Claude AI
ANTHROPIC_API_KEY=your_claude_api_key
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# GoHighLevel
GHL_API_KEY=your_ghl_api_key
GHL_LOCATION_ID=your_location_id
GHL_WEBHOOK_SECRET=your_webhook_secret

# Property Data
ZILLOW_API_KEY=your_zillow_api_key
RENTSPIDER_API_KEY=your_rentspider_api_key

# Communication
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
SENDGRID_API_KEY=your_sendgrid_key

# Monitoring
SENTRY_DSN=your_sentry_dsn
DATADOG_API_KEY=your_datadog_key
```

#### Docker Compose Setup
```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: jorge_bots_dev
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  lead_bot:
    build: .
    command: uvicorn bots.lead_bot.main:app --host 0.0.0.0 --port 8001 --reload
    ports:
      - "8001:8001"
    depends_on:
      - postgres
      - redis
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/jorge_bots_dev
      - REDIS_URL=redis://redis:6379

  seller_bot:
    build: .
    command: uvicorn bots.seller_bot.main:app --host 0.0.0.0 --port 8002 --reload
    ports:
      - "8002:8002"
    depends_on:
      - postgres
      - redis

  buyer_bot:
    build: .
    command: uvicorn bots.buyer_bot.main:app --host 0.0.0.0 --port 8003 --reload
    ports:
      - "8003:8003"
    depends_on:
      - postgres
      - redis

  command_center:
    build: .
    command: streamlit run command_center/main.py --server.port 8501 --server.address 0.0.0.0
    ports:
      - "8501:8501"
    depends_on:
      - lead_bot
      - seller_bot
      - buyer_bot

volumes:
  postgres_data:
```

#### Development Commands
```bash
# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec lead_bot python -m alembic upgrade head

# View logs
docker-compose logs -f lead_bot

# Run tests
docker-compose exec lead_bot pytest tests/

# Stop all services
docker-compose down
```

---

## 🚀 PHASE 2: STAGING ENVIRONMENT (DigitalOcean)

### DigitalOcean App Platform Setup

#### Create App Platform Project
```yaml
# .do/app.yaml
name: jorge-bots-staging
region: nyc1

databases:
- name: postgres
  engine: PG
  version: "15"
  size: basic-xs
  num_nodes: 1

- name: redis
  engine: REDIS
  version: "7"
  size: basic-xs

services:
- name: lead-bot
  source_dir: /
  github:
    repo: your-username/jorge_real_estate_bots
    branch: staging
  build_command: pip install -r requirements.txt
  run_command: uvicorn bots.lead_bot.main:app --host 0.0.0.0 --port 8080
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  http_port: 8080
  envs:
  - key: DATABASE_URL
    scope: RUN_TIME
    type: SECRET
  - key: REDIS_URL
    scope: RUN_TIME
    type: SECRET
  - key: ANTHROPIC_API_KEY
    scope: RUN_TIME
    type: SECRET

- name: seller-bot
  source_dir: /
  github:
    repo: your-username/jorge_real_estate_bots
    branch: staging
  build_command: pip install -r requirements.txt
  run_command: uvicorn bots.seller_bot.main:app --host 0.0.0.0 --port 8080
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  http_port: 8080

- name: buyer-bot
  source_dir: /
  github:
    repo: your-username/jorge_real_estate_bots
    branch: staging
  build_command: pip install -r requirements.txt
  run_command: uvicorn bots.buyer_bot.main:app --host 0.0.0.0 --port 8080
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  http_port: 8080

- name: command-center
  source_dir: /
  github:
    repo: your-username/jorge_real_estate_bots
    branch: staging
  build_command: pip install -r requirements.txt
  run_command: streamlit run command_center/main.py --server.port 8080 --server.address 0.0.0.0
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  http_port: 8080

static_sites:
- name: docs
  source_dir: /docs
  github:
    repo: your-username/jorge_real_estate_bots
    branch: staging
```

#### Environment Variables Setup
```bash
# Set environment variables in DigitalOcean App Platform Console
doctl apps create --spec .do/app.yaml

# Add secrets via console or CLI
doctl apps update [APP_ID] --spec .do/app.yaml
```

#### Domain Configuration
```bash
# Add custom domain
# dashboard.jorge-bots-staging.com → command-center service
# api.jorge-bots-staging.com → load balancer for bot services

# SSL certificates (automatic with DigitalOcean)
```

---

## 🏢 PHASE 3: PRODUCTION ENVIRONMENT

### Production Infrastructure Requirements

#### DigitalOcean Production Setup (50+ agents)
```yaml
# .do/production.yaml
name: jorge-bots-production
region: nyc1

databases:
- name: postgres-primary
  engine: PG
  version: "15"
  size: db-s-2vcpu-4gb  # Scalable for production
  num_nodes: 1

- name: redis-primary
  engine: REDIS
  version: "7"
  size: db-s-1vcpu-2gb

services:
- name: lead-bot
  instance_count: 2  # High availability
  instance_size_slug: basic-s  # 1 vCPU, 512MB RAM
  autoscaling:
    min_instance_count: 2
    max_instance_count: 5
    metrics:
    - cpu:
        percent: 70
    - memory:
        percent: 80

- name: seller-bot
  instance_count: 2
  instance_size_slug: basic-s
  autoscaling:
    min_instance_count: 2
    max_instance_count: 3

- name: buyer-bot
  instance_count: 2
  instance_size_slug: basic-s
  autoscaling:
    min_instance_count: 2
    max_instance_count: 3

- name: command-center
  instance_count: 2
  instance_size_slug: basic-s
```

#### AWS Migration (Scale to 200+ agents)
```yaml
# aws-infrastructure.yml (Terraform)
provider "aws" {
  region = "us-east-1"
}

# ECS Cluster for container orchestration
resource "aws_ecs_cluster" "jorge_bots" {
  name = "jorge-bots-production"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier             = "jorge-bots-postgres"
  engine                 = "postgres"
  engine_version         = "15.3"
  instance_class         = "db.t3.medium"
  allocated_storage      = 20
  max_allocated_storage  = 100
  storage_type           = "gp2"
  storage_encrypted      = true

  db_name  = "jorge_bots"
  username = "postgres"
  password = random_password.postgres.result

  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.postgres.name

  skip_final_snapshot = false
  final_snapshot_identifier = "jorge-bots-postgres-final-snapshot"

  tags = {
    Name = "jorge-bots-postgres"
  }
}

# ElastiCache Redis
resource "aws_elasticache_subnet_group" "redis" {
  name       = "jorge-bots-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id         = "jorge-bots-redis"
  description                  = "Redis cluster for Jorge Bots"

  node_type            = "cache.t3.micro"
  port                 = 6379
  parameter_group_name = "default.redis7"

  num_cache_clusters         = 2
  automatic_failover_enabled = true

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "jorge-bots-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets           = aws_subnet.public[*].id

  enable_deletion_protection = true

  tags = {
    Name = "jorge-bots-alb"
  }
}

# ECS Task Definitions
resource "aws_ecs_task_definition" "lead_bot" {
  family                   = "jorge-lead-bot"
  network_mode            = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                     = 512
  memory                  = 1024

  container_definitions = jsonencode([
    {
      name  = "lead-bot"
      image = "your-ecr-repo/jorge-lead-bot:latest"

      portMappings = [
        {
          containerPort = 8001
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "DATABASE_URL"
          value = "postgresql://postgres:${random_password.postgres.result}@${aws_db_instance.postgres.endpoint}:5432/jorge_bots"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.lead_bot.name
          awslogs-region        = "us-east-1"
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

# Auto Scaling for ECS Services
resource "aws_appautoscaling_target" "lead_bot" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.jorge_bots.name}/${aws_ecs_service.lead_bot.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "lead_bot_cpu" {
  name               = "lead-bot-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.lead_bot.resource_id
  scalable_dimension = aws_appautoscaling_target.lead_bot.scalable_dimension
  service_namespace  = aws_appautoscaling_target.lead_bot.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
```

---

## 🔒 SECURITY CONFIGURATION

### SSL/TLS Setup

#### Production Domains
```bash
# Primary domains
api.jorge-bots.com         # API Gateway
dashboard.jorge-bots.com   # Command Center
lead.jorge-bots.com       # Lead Bot
seller.jorge-bots.com     # Seller Bot
buyer.jorge-bots.com      # Buyer Bot

# SSL certificates via Let's Encrypt/AWS Certificate Manager
```

#### Security Headers
```python
# security.py - Add to all FastAPI apps
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["jorge-bots.com", "*.jorge-bots.com"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashboard.jorge-bots.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

### Environment Secrets Management

#### Production Secrets (AWS Secrets Manager)
```bash
# Store secrets in AWS Secrets Manager
aws secretsmanager create-secret \
  --name "jorge-bots/production/claude-api-key" \
  --description "Claude AI API key for production" \
  --secret-string "your-claude-api-key"

aws secretsmanager create-secret \
  --name "jorge-bots/production/ghl-api-key" \
  --description "GoHighLevel API key" \
  --secret-string "your-ghl-api-key"
```

#### Secret Rotation
```python
# secrets_rotation.py
import boto3
from datetime import datetime, timedelta

def rotate_api_keys():
    """Rotate API keys every 90 days"""
    secrets_client = boto3.client('secretsmanager')

    # List secrets that need rotation
    secrets = secrets_client.list_secrets(
        Filters=[
            {
                'Key': 'name',
                'Values': ['jorge-bots/production/']
            }
        ]
    )

    for secret in secrets['SecretList']:
        last_rotated = secret.get('LastRotatedDate')
        if not last_rotated or (datetime.now() - last_rotated) > timedelta(days=90):
            # Trigger rotation
            rotate_secret(secret['Name'])
```

---

## 📊 MONITORING & ALERTING

### DataDog Integration

#### Application Monitoring
```python
# monitoring.py
from datadog import initialize, statsd
import time

# Initialize DataDog
options = {
    'api_key': 'your_datadog_api_key',
    'app_key': 'your_datadog_app_key'
}
initialize(**options)

# Performance monitoring decorator
def monitor_performance(metric_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                statsd.increment(f'{metric_name}.success')
                return result
            except Exception as e:
                statsd.increment(f'{metric_name}.error')
                raise
            finally:
                duration = time.time() - start_time
                statsd.histogram(f'{metric_name}.duration', duration)
        return wrapper
    return decorator

# Usage example
@monitor_performance('lead_bot.analyze_lead')
async def analyze_lead(lead_data):
    # Lead analysis implementation
    pass
```

#### Critical Alerts
```yaml
# datadog-alerts.yml
alerts:
  - name: "Lead Response Time > 5 minutes"
    query: "avg(last_5m):avg:lead_bot.response_time{*} > 300"
    message: "CRITICAL: Lead response time exceeding 5 minutes. 10x conversion multiplier at risk!"
    tags: ["team:jorge", "priority:critical"]

  - name: "API Error Rate > 1%"
    query: "avg(last_5m):sum:api.errors{*}/sum:api.requests{*} > 0.01"
    message: "High API error rate detected. Check logs immediately."

  - name: "Claude API Failures"
    query: "avg(last_5m):sum:claude.api.errors{*} > 0"
    message: "Claude API failures detected. Check authentication and rate limits."

  - name: "Database Connection Failures"
    query: "avg(last_5m):sum:database.connection.errors{*} > 0"
    message: "Database connection issues. Check PostgreSQL status."
```

### Health Checks

#### Application Health Endpoints
```python
# health.py
from fastapi import FastAPI
import redis
import psycopg2
import httpx

@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }

    # Database check
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # Redis check
    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
        health_status["checks"]["redis"] = "healthy"
    except Exception as e:
        health_status["checks"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # Claude API check
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.anthropic.com/v1/messages",
                                      headers={"Authorization": f"Bearer {CLAUDE_API_KEY}"})
            if response.status_code in [200, 401]:  # 401 is expected for health check
                health_status["checks"]["claude_api"] = "healthy"
            else:
                health_status["checks"]["claude_api"] = f"unhealthy: {response.status_code}"
                health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["checks"]["claude_api"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    return health_status

@app.get("/health/liveness")
async def liveness_check():
    """Simple liveness check for Kubernetes"""
    return {"status": "alive"}

@app.get("/health/readiness")
async def readiness_check():
    """Readiness check - are we ready to serve traffic?"""
    # Check if all dependencies are available
    health = await health_check()
    if health["status"] == "healthy":
        return {"status": "ready"}
    else:
        raise HTTPException(503, "Not ready")
```

---

## 🔄 CI/CD PIPELINE

### GitHub Actions Workflow

#### `.github/workflows/deploy.yml`
```yaml
name: Deploy Jorge Real Estate Bots

on:
  push:
    branches: [main, staging]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: jorge-real-estate-bots

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: password
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run linting
      run: |
        ruff check .
        ruff format --check .

    - name: Run type checking
      run: mypy bots/

    - name: Run tests
      run: |
        pytest tests/ --cov=bots/ --cov-report=xml
      env:
        DATABASE_URL: postgresql://postgres:password@localhost:5432/test_db
        REDIS_URL: redis://localhost:6379
        ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/staging'

    steps:
    - uses: actions/checkout@v4

    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ github.repository }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=sha,prefix={{branch}}-

    - name: Build and push Docker images
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/staging'

    steps:
    - name: Deploy to DigitalOcean App Platform (Staging)
      uses: digitalocean/app_action@v1.1.5
      with:
        app_name: jorge-bots-staging
        token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}
        images: '[
          {
            "name": "lead-bot",
            "image": "${{ env.REGISTRY }}/${{ github.repository }}/${{ env.IMAGE_NAME }}:staging-${{ github.sha }}"
          },
          {
            "name": "seller-bot",
            "image": "${{ env.REGISTRY }}/${{ github.repository }}/${{ env.IMAGE_NAME }}:staging-${{ github.sha }}"
          },
          {
            "name": "buyer-bot",
            "image": "${{ env.REGISTRY }}/${{ github.repository }}/${{ env.IMAGE_NAME }}:staging-${{ github.sha }}"
          }
        ]'

  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production

    steps:
    - name: Deploy to Production
      uses: digitalocean/app_action@v1.1.5
      with:
        app_name: jorge-bots-production
        token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}
        images: '[
          {
            "name": "lead-bot",
            "image": "${{ env.REGISTRY }}/${{ github.repository }}/${{ env.IMAGE_NAME }}:main-${{ github.sha }}"
          },
          {
            "name": "seller-bot",
            "image": "${{ env.REGISTRY }}/${{ github.repository }}/${{ env.IMAGE_NAME }}:main-${{ github.sha }}"
          },
          {
            "name": "buyer-bot",
            "image": "${{ env.REGISTRY }}/${{ github.repository }}/${{ env.IMAGE_NAME }}:main-${{ github.sha }}"
          }
        ]'

    - name: Run production health checks
      run: |
        # Wait for deployment to complete
        sleep 60

        # Check all service health endpoints
        curl -f https://api.jorge-bots.com/lead/health || exit 1
        curl -f https://api.jorge-bots.com/seller/health || exit 1
        curl -f https://api.jorge-bots.com/buyer/health || exit 1
        curl -f https://dashboard.jorge-bots.com/health || exit 1

    - name: Send deployment notification
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        text: "🚀 Jorge Real Estate Bots deployed to production successfully!"
      env:
        SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
      if: always()
```

### Database Migrations

#### Alembic Configuration
```python
# alembic/env.py
from alembic import context
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig
import os

# Import your models
from bots.shared.database import Base

config = context.config

# Set SQLAlchemy URL from environment
config.set_main_option('sqlalchemy.url', os.getenv('DATABASE_URL'))

fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True
        )

        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

#### Migration Commands
```bash
# Generate migration
alembic revision --autogenerate -m "Add lead scoring fields"

# Run migrations
alembic upgrade head

# Rollback migrations
alembic downgrade -1

# Production migration strategy
# 1. Deploy new code with backward-compatible changes
# 2. Run migration
# 3. Deploy code that uses new schema
# 4. Remove old schema in next release
```

---

## 🔧 OPERATIONAL PROCEDURES

### Backup & Recovery

#### Database Backup Strategy
```bash
# Daily automated backups
#!/bin/bash
# backup-database.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="jorge_bots_backup_${DATE}.sql"

# Create backup
pg_dump $DATABASE_URL > /backups/$BACKUP_FILE

# Compress backup
gzip /backups/$BACKUP_FILE

# Upload to S3
aws s3 cp /backups/${BACKUP_FILE}.gz s3://jorge-bots-backups/database/

# Keep only last 30 days of backups locally
find /backups -name "*.gz" -mtime +30 -delete

# Verify backup integrity
if [ $? -eq 0 ]; then
    echo "Backup successful: ${BACKUP_FILE}.gz"
else
    echo "Backup failed!" | mail -s "Backup Failure" admin@jorge-bots.com
fi
```

#### Recovery Procedures
```bash
# Database recovery from backup
#!/bin/bash
# restore-database.sh

BACKUP_FILE=$1
if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.gz>"
    exit 1
fi

# Download backup from S3
aws s3 cp s3://jorge-bots-backups/database/$BACKUP_FILE .

# Decompress
gunzip $BACKUP_FILE

# Stop application services
docker-compose stop lead_bot seller_bot buyer_bot command_center

# Create new database
createdb jorge_bots_restored

# Restore backup
psql jorge_bots_restored < ${BACKUP_FILE%%.gz}

# Update connection string
export DATABASE_URL="postgresql://postgres:password@localhost:5432/jorge_bots_restored"

# Start services
docker-compose up -d

echo "Database restored successfully"
```

### Performance Optimization

#### Database Performance
```sql
-- performance-indexes.sql
-- Optimize common queries

-- Lead bot indexes
CREATE INDEX CONCURRENTLY idx_leads_created_at ON contacts(created_at) WHERE tags ? 'lead';
CREATE INDEX CONCURRENTLY idx_leads_score ON contacts(ai_lead_score) WHERE ai_lead_score > 0;
CREATE INDEX CONCURRENTLY idx_leads_temperature ON contacts(lead_temperature);

-- Seller bot indexes
CREATE INDEX CONCURRENTLY idx_sellers_property_address ON contacts(property_address) WHERE property_address IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_sellers_estimated_value ON contacts(estimated_property_value) WHERE estimated_property_value > 0;

-- Buyer bot indexes
CREATE INDEX CONCURRENTLY idx_buyers_budget ON contacts(budget_min, budget_max) WHERE budget_min > 0;
CREATE INDEX CONCURRENTLY idx_buyers_score ON contacts(buyer_score) WHERE buyer_score > 0;

-- Composite indexes for common filters
CREATE INDEX CONCURRENTLY idx_leads_active ON contacts(lead_temperature, created_at) WHERE tags ? 'lead' AND created_at > NOW() - INTERVAL '30 days';
```

#### Application Performance
```python
# performance_optimization.py
import asyncio
from functools import wraps
import time

# Connection pooling
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,  # Use external connection pooler (PgBouncer)
    echo=False,
    pool_pre_ping=True
)

# Caching decorator
import redis
import pickle
import hashlib

redis_client = redis.Redis.from_url(REDIS_URL)

def cache_result(ttl=300, key_prefix=""):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{hashlib.md5(str(args).encode() + str(kwargs).encode()).hexdigest()}"

            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                return pickle.loads(cached)

            # Execute function and cache result
            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, ttl, pickle.dumps(result))

            return result
        return wrapper
    return decorator

# Usage
@cache_result(ttl=600, key_prefix="lead_analysis")
async def analyze_lead_cached(lead_data):
    return await analyze_lead(lead_data)
```

### Scaling Procedures

#### Horizontal Scaling Checklist
- [ ] **Database**: Add read replicas for heavy read workloads
- [ ] **Application**: Increase instance count in load balancer
- [ ] **Cache**: Add Redis cluster for distributed caching
- [ ] **CDN**: Implement CloudFlare for static assets
- [ ] **Monitoring**: Scale monitoring infrastructure

#### Database Scaling
```bash
# Add read replica
aws rds create-db-instance-read-replica \
  --db-instance-identifier jorge-bots-read-replica \
  --source-db-instance-identifier jorge-bots-postgres \
  --db-instance-class db.t3.medium

# Configure read/write splitting in application
```

---

**This deployment guide provides everything needed to scale Jorge's Real Estate AI Bot Platform from development through enterprise production deployment.**