# HyperRAG Deployment Playbooks

## 1. Production Deployment

### Prerequisites
- Kubernetes cluster 1.24+
- Helm 3.8+
- kubectl configured
- Docker registry access

### Steps

1. **Prepare Environment**
```bash
# Clone repository
git clone <repo-url>
cd hyperrag

# Create namespace
kubectl create namespace hyperrag-prod

# Add Helm repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add minio https://helm.min.io/
helm repo update
```

2. **Configure Secrets**
```bash
# Create secrets
kubectl -n hyperrag-prod create secret generic hyperrag-secrets \
  --from-literal=postgres-password=<password> \
  --from-literal=minio-access-key=<access-key> \
  --from-literal=minio-secret-key=<secret-key> \
  --from-literal=jwt-secret=<jwt-secret>

# Create TLS certificates
kubectl -n hyperrag-prod create secret tls hyperrag-tls \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key
```

3. **Deploy Infrastructure**
```bash
# Deploy MinIO
helm install minio minio/minio \
  -n hyperrag-prod \
  -f platform/infra/helmfile/values/minio.yaml

# Deploy PostgreSQL
helm install postgres bitnami/postgresql \
  -n hyperrag-prod \
  -f platform/infra/helmfile/values/postgres.yaml

# Deploy Qdrant
helm install qdrant platform/infra/helmfile/charts/qdrant \
  -n hyperrag-prod \
  -f platform/infra/helmfile/values/qdrant.yaml

# Deploy NATS
helm install nats nats/nats \
  -n hyperrag-prod \
  -f platform/infra/helmfile/values/nats.yaml
```

4. **Deploy Monitoring Stack**
```bash
# Deploy Prometheus
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n hyperrag-prod \
  -f platform/infra/helmfile/values/prometheus.yaml

# Deploy Grafana
helm install grafana grafana/grafana \
  -n hyperrag-prod \
  -f platform/infra/helmfile/values/grafana.yaml

# Deploy Jaeger
helm install jaeger jaegertracing/jaeger \
  -n hyperrag-prod \
  -f platform/infra/helmfile/values/jaeger.yaml
```

5. **Deploy HyperRAG Services**
```bash
# Build and push Docker images
./build-images.sh

# Deploy services
helm install hyperrag platform/infra/helmfile/charts/hyperrag \
  -n hyperrag-prod \
  -f platform/infra/helmfile/values/hyperrag.yaml
```

6. **Verify Deployment**
```bash
# Check pods
kubectl -n hyperrag-prod get pods

# Check services
kubectl -n hyperrag-prod get svc

# Run tests
./test-system.py --env prod
```

## 2. Backup and Recovery

### Database Backup
```bash
# Backup PostgreSQL
kubectl -n hyperrag-prod exec -it postgres-0 -- \
  pg_dump -U hyperrag > backup.sql

# Backup to MinIO
mc cp backup.sql minio/backups/$(date +%Y%m%d)/
```

### Vector Database Backup
```bash
# Backup Qdrant collections
kubectl -n hyperrag-prod exec -it qdrant-0 -- \
  qdrant-backup create --path /backups

# Copy to persistent storage
kubectl -n hyperrag-prod cp qdrant-0:/backups ./qdrant-backup
```

### Recovery Procedure
```bash
# Restore PostgreSQL
kubectl -n hyperrag-prod exec -it postgres-0 -- \
  psql -U hyperrag -d hyperrag < backup.sql

# Restore Qdrant
kubectl -n hyperrag-prod cp ./qdrant-backup qdrant-0:/backups
kubectl -n hyperrag-prod exec -it qdrant-0 -- \
  qdrant-backup restore --path /backups
```

## 3. Scaling

### Horizontal Scaling
```bash
# Scale retriever service
kubectl -n hyperrag-prod scale deployment retriever --replicas=3

# Scale embedder service
kubectl -n hyperrag-prod scale deployment embedder --replicas=2

# Update HPA
kubectl -n hyperrag-prod apply -f platform/infra/k8s/hpa.yaml
```

### Resource Adjustment
```bash
# Update resource requests/limits
kubectl -n hyperrag-prod set resources deployment retriever \
  --requests=cpu=500m,memory=1Gi \
  --limits=cpu=2,memory=4Gi
```

## 4. Monitoring Setup

### Grafana Dashboards
```bash
# Import dashboards
kubectl -n hyperrag-prod cp \
  platform/infra/grafana/dashboards/ \
  grafana-0:/var/lib/grafana/dashboards/

# Configure datasources
kubectl -n hyperrag-prod apply -f \
  platform/infra/grafana/datasources/
```

### Alert Rules
```bash
# Apply Prometheus rules
kubectl -n hyperrag-prod apply -f \
  platform/infra/prometheus/rules/

# Configure alert manager
kubectl -n hyperrag-prod apply -f \
  platform/infra/prometheus/alertmanager/
```

## 5. Security Hardening

### Network Policies
```bash
# Apply network policies
kubectl -n hyperrag-prod apply -f \
  platform/infra/k8s/network-policies/

# Enable mTLS
kubectl -n hyperrag-prod apply -f \
  platform/infra/istio/mtls/
```

### RBAC Configuration
```bash
# Apply RBAC rules
kubectl -n hyperrag-prod apply -f \
  platform/infra/k8s/rbac/

# Update service accounts
kubectl -n hyperrag-prod apply -f \
  platform/infra/k8s/service-accounts/
```

## 6. Troubleshooting

### Log Collection
```bash
# Collect service logs
kubectl -n hyperrag-prod logs -l app=retriever > retriever.log
kubectl -n hyperrag-prod logs -l app=embedder > embedder.log

# Export traces
kubectl -n hyperrag-prod port-forward svc/jaeger-query 16686:16686
# Access http://localhost:16686
```

### Performance Analysis
```bash
# Check resource usage
kubectl -n hyperrag-prod top pods
kubectl -n hyperrag-prod top nodes

# Analyze network traffic
kubectl -n hyperrag-prod exec -it <pod> -- tcpdump -i any
```

## 7. Rollback Procedure

### Service Rollback
```bash
# Rollback deployment
kubectl -n hyperrag-prod rollout undo deployment/retriever

# Verify rollback
kubectl -n hyperrag-prod rollout status deployment/retriever
```

### Database Rollback
```bash
# Stop services
kubectl -n hyperrag-prod scale deployment --all --replicas=0

# Restore database
kubectl -n hyperrag-prod exec -it postgres-0 -- \
  psql -U hyperrag -d hyperrag < backup.sql

# Restart services
kubectl -n hyperrag-prod scale deployment --all --replicas=1
```

## 8. Maintenance

### Regular Tasks
```bash
# Update certificates
kubectl -n hyperrag-prod create secret tls hyperrag-tls \
  --cert=new-cert.pem \
  --key=new-key.pem \
  --dry-run=client -o yaml | kubectl apply -f -

# Rotate secrets
kubectl -n hyperrag-prod create secret generic hyperrag-secrets \
  --from-literal=postgres-password=<new-password> \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Health Checks
```bash
# Check service health
for svc in ingestor normalizer retriever chunker embedder evaluator; do
  kubectl -n hyperrag-prod exec -it svc/$svc -- curl localhost/health
done

# Verify data consistency
./verify-data.sh
```

## Contact Information

### Support Team
- **DevOps**: devops@hyperrag.ai
- **Security**: security@hyperrag.ai
- **Database**: dba@hyperrag.ai
- **ML Ops**: mlops@hyperrag.ai

### Emergency Procedures
1. Join emergency channel: #hyperrag-911
2. Page on-call engineer: @hyperrag-oncall
3. Follow incident response runbook
4. Update status page

## Reference

### URLs
- **Grafana**: https://grafana.hyperrag.ai
- **Prometheus**: https://prometheus.hyperrag.ai
- **Jaeger**: https://jaeger.hyperrag.ai
- **Documentation**: https://docs.hyperrag.ai

### Commands
```bash
# Quick health check
./health-check.sh

# Performance test
./load-test.sh

# Security scan
./security-scan.sh
```
