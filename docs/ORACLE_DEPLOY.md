# Deploy productivo en Oracle Cloud Infrastructure

Runbook reproducible para frontend, API, scheduler, PostgreSQL, Redis y TLS en una VM Ampere A1.

## Instancia activa

- Región: `us-ashburn-1`.
- Hostname HTTPS: `129-159-125-184.sslip.io`.
- IP pública reservada: `129.159.125.184`.
- Cómputo: `VM.Standard.A1.Flex`, 2 OCPU y 12 GB RAM.
- Almacenamiento: boot volume de 50 GB y volumen de datos de 100 GB montado en
  `/srv/stock-platform`.
- SSH: permitido únicamente desde la IP operativa `/32`; HTTP/HTTPS públicos.

## Estado del repositorio

El entorno productivo está definido en:

- `infra/oci/terraform/`: VCN, subnet pública, reglas 22/80/443, VM Ampere A1, IP pública
  reservada y `cloud-init` de hardening.
- `compose.production.yml`: PostgreSQL, Redis, migraciones, API, scheduler, frontend y Caddy.
- `infra/oci/Caddyfile`: HTTPS automático y reverse proxy.
- `infra/oci/scripts/`: deploy, backup y restore.
- `infra/oci/systemd/`: backup diario con retención local de 14 días.

El `docker-compose.yml` de la raíz continúa siendo exclusivamente para desarrollo local.

## Arquitectura

```text
Internet --HTTPS--> Caddy :443 -- /api, /health --> FastAPI :8000
                              `-- demás rutas ----> Next.js :3000
                    red Docker |-> PostgreSQL :5432
                               |-> Redis :6379
                               `-> scheduler (proceso separado)
```

PostgreSQL, Redis y FastAPI no publican puertos en la VM. Sólo SSH, HTTP y HTTPS se permiten
desde la VCN; SSH debe limitarse a la IP del operador.

## Límite Always Free vigente

La cuota Ampere A1 Always Free actual es de **2 OCPU y 12 GB de RAM agregados** por tenancy,
con 200 GB agregados de Block Volume en la home region. La configuración por defecto usa una
VM `VM.Standard.A1.Flex` de 2 OCPU/12 GB y un boot volume de 100 GB.

Verificá los límites en la documentación oficial antes de ejecutar `terraform apply`; superar
la cuota o crear recursos fuera de la home region puede generar cargos.

## 1. Requisitos de cuenta y DNS

Necesitás:

1. Una cuenta OCI y su **home region**.
2. Los OCID de tenancy y compartment.
3. Autenticación local del provider de OCI (archivo `~/.oci/config` o variables de entorno
   compatibles con el provider).
4. Terraform >= 1.6.
5. Una clave SSH pública.
6. Un hostname para la aplicación, por ejemplo `app.example.com`.

Se puede usar dominio propio o un hostname compatible con Let's Encrypt como `sslip.io`
durante la transición.

## 2. Provisionar OCI con Terraform

```bash
cd infra/oci/terraform
cp terraform.tfvars.example terraform.tfvars
```

Completá `terraform.tfvars`. Para obtener tu IP pública y restringir SSH:

```bash
curl -4 https://ifconfig.me
# ssh_allowed_cidr = "TU_IP/32"
```

Inicializá y revisá el plan:

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

Si Oracle devuelve `Out of host capacity`, cambiá `availability_domain_number` a otro índice
disponible y repetí el plan. No aumentes OCPU/RAM para resolver capacidad.

El output `reserved_public_ip` es la IP estable que debe recibir el A record del hostname de API.
Esperá a que `cloud-init` termine antes de desplegar:

```bash
ssh ubuntu@IP_RESERVADA 'cloud-init status --wait'
```

## 3. Publicar el código en la VM

El directorio esperado es `/opt/stock-analysis`. Si la VM puede leer el repo por SSH:

```bash
ssh ubuntu@IP_RESERVADA
git clone git@github.com:CuchiBJ/stock-analysis-platform.git /opt/stock-analysis
cd /opt/stock-analysis
```

Para un repo privado, agregá primero una deploy key de sólo lectura o copiá el checkout desde
la máquina local con `rsync`. No copies `.env`, dumps ni el estado local de Terraform.

## 4. Configurar secretos

En la VM:

```bash
cd /opt/stock-analysis
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -hex 32
```

Usá el valor hexadecimal como `POSTGRES_PASSWORD` y dentro de `DATABASE_URL`. Completá además:

- `POLYGON_API_KEY`.
- `ANTHROPIC_API_KEY`, sólo si se usa el chat integrado.
- `IBKR_FLEX_TOKEN` y `IBKR_FLEX_QUERY_ID`, sólo si se usa el sync.
- `CORS_ORIGINS`, con los orígenes HTTPS adicionales que necesiten llamar a la API.
- `API_DOMAIN`, el hostname cuyo A record apunta a la IP reservada.

`.env.production` está ignorado por Git. No pongas secretos en `terraform.tfvars`, `cloud-init` ni
el historial del shell.

## 5. Restaurar la base existente

En la máquina local:

```bash
pg_dump --format=custom --no-owner --no-acl stock_analysis > stock_analysis.dump
scp stock_analysis.dump ubuntu@IP_RESERVADA:/opt/stock-analysis/backups/
```

En la VM, iniciá sólo PostgreSQL y restaurá:

```bash
cd /opt/stock-analysis
docker compose --env-file .env.production -f compose.production.yml up -d postgres
infra/oci/scripts/restore-postgres.sh /opt/stock-analysis/backups/stock_analysis.dump
```

El restore exige escribir `RESTORE`, detiene API/scheduler, aplica `pg_restore` y luego Alembic.

Si se trata de una instalación vacía, omití el dump: el servicio `migrate` crea/aplica el esquema
antes de iniciar la API y el scheduler.

## 6. Desplegar y habilitar backups

```bash
cd /opt/stock-analysis
infra/oci/scripts/deploy.sh
sudo infra/oci/scripts/install-operations.sh
```

Verificaciones:

```bash
docker compose --env-file .env.production -f compose.production.yml ps
curl -fsS https://API_DOMAIN/health
curl -fsS https://API_DOMAIN/api/v1/health/data-freshness
systemctl list-timers stock-analysis-backup.timer
```

La primera emisión del certificado sólo funciona después de que DNS resuelva a la IP reservada
y los puertos TCP 80/443 sean accesibles. QUIC/HTTP3 usa UDP 443 y también está habilitado.

Los backups diarios quedan en `/srv/stock-platform/backups`. Son una primera red de seguridad,
pero no protegen contra pérdida de la VM: antes de producción real, agregá copia off-host a OCI
Object Storage o a otro proveedor.

## 7. Frontend

El frontend se construye con `frontend/Dockerfile.production`. Compose inyecta
`NEXT_PUBLIC_API_URL=https://API_DOMAIN` durante el build y Caddy lo publica en el mismo
hostname. `/api/*`, `/health`, `/docs*`, `/redoc*` y `/openapi.json` se enrutan a FastAPI;
las demás rutas se enrutan a Next.js.

Para reconstruir únicamente la interfaz:

```bash
docker compose --env-file .env.production -f compose.production.yml build frontend
docker compose --env-file .env.production -f compose.production.yml up -d frontend caddy
```

## 8. Actualizaciones y rollback

Deploy normal:

```bash
cd /opt/stock-analysis
git fetch --all --prune
git switch main
git pull --ff-only
infra/oci/scripts/deploy.sh
```

Antes de una migración relevante:

```bash
infra/oci/scripts/backup-postgres.sh
```

Para volver código atrás, seleccioná un commit conocido y ejecutá el deploy. No reviertas una
migración de base a ciegas; restaurá un backup validado si el cambio de esquema no es compatible.

## Checklist de salida

- [ ] La infraestructura está en la home region y no incluye recursos pagos inesperados.
- [ ] La IP es `RESERVED`, no efímera.
- [ ] SSH está limitado a una IP `/32`.
- [ ] DNS A resuelve a la IP reservada.
- [ ] `.env.production` tiene permisos 600 y no está en Git.
- [ ] Frontend, API, scheduler, PostgreSQL, Redis y Caddy están `running/healthy`.
- [ ] Alembic llegó a `head`.
- [ ] `/health` responde por HTTPS.
- [ ] El endpoint de data freshness muestra heartbeats recientes.
- [ ] El timer de backup está activo y un restore de prueba fue validado.
- [ ] El dashboard carga datos reales y WebSocket por HTTPS.
