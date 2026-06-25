# Runbook de deploy — Oracle Cloud Always Free

> Plan de ejecución. Backend (uvicorn + scheduler + Postgres + Redis) en una VM ARM Ampere
> "Always Free"; frontend Next.js en Vercel. Fecha: 2026-06-09.

## Arquitectura objetivo

```
  Usuario ──https──>  app.tudominio.com   (Vercel · Next.js · TLS auto)
                              │
                              └─ fetch https ─> api.tudominio.com
                                                     │
                                          ┌──────────▼───────────┐  Oracle VM (Ampere, Ubuntu)
                                          │  Caddy (reverse proxy │
                                          │   + TLS Let's Encrypt)│
                                          │        │             │
                                          │   uvicorn :8000      │  docker-compose
                                          │   postgres :5432     │  (red interna)
                                          │   redis    :6379     │
                                          └──────────────────────┘
```

Regla de oro: el frontend va por **https** (Vercel), así que el backend **también tiene que ser
https**. Un backend en `http://<ip>` sería bloqueado por *mixed content* desde el navegador. De ahí
que el dominio (al menos un subdominio para la API) sea **necesario**, no opcional.

---

## El tema dominio (lo que preguntaste)

### ¿Necesito un dominio?
**Sí, para la API.** No por estética, sino porque:
- Let's Encrypt **no emite certificados TLS para una IP pelada** → sin dominio no hay https en el backend.
- Sin https en el backend, el frontend https de Vercel no lo puede llamar (mixed content).
- El **frontend** en cambio **no** necesita dominio propio: Vercel te da `tu-proyecto.vercel.app`
  con https gratis. Podés vivir con eso y comprar dominio solo más adelante.

Conclusión: necesitás **un hostname con https apuntando a la VM** para la API. Hay dos formas:

### Opción 1 — Dominio propio (recomendado, ~US$10–15/año)
1. Comprar el dominio en un **registrar barato**:
   - **Cloudflare Registrar**: lo vende **a precio costo** (sin markup), el renovado más barato a largo plazo. Requiere usar Cloudflare como DNS (gratis).
   - Alternativas: Namecheap, Porkbun.
2. DNS (en Cloudflare o el registrar):
   - `api`  → **A record** → IP pública de la VM Oracle.
   - `app`  → **CNAME/A** según lo que indique Vercel (al agregar el dominio en el panel de Vercel).
3. En la VM, **Caddy** detecta el dominio y **auto-provisiona y renueva** el cert Let's Encrypt. Cero trabajo manual de TLS.

> Si usás Cloudflare como DNS, dejá el registro `api` en modo **DNS-only (nube gris)** para que Caddy
> maneje Let's Encrypt directo. (Si activás el proxy naranja, hay que configurar TLS "Full strict"
> con origin cert — más vueltas; para empezar, gris es lo simple.)

### Opción 2 — Dominio gratis (hobby, $0)
Hostnames gratis que **sí soportan Let's Encrypt**:
- **DuckDNS** → `tunombre.duckdns.org` (subdominio gratis, clásico para self-hosting).
- **sslip.io / nip.io** → DNS wildcard que mapea la IP en el propio nombre, ej.
  `api-129-146-1-2.sslip.io` resuelve a `129.146.1.2` sin configurar nada. Caddy puede sacar cert para ese hostname.
- Evitar **Freenom** (.tk/.ml): prácticamente muerto/poco confiable.

Trade-off: gratis y funcional, pero el nombre se ve menos "pro". Perfecto para uso personal; podés
migrar a dominio propio después sin tocar la arquitectura (solo cambiás el hostname en Caddy y en
la env var del frontend).

### IP estática (importante, no te saltees esto)
La IP pública de la VM por defecto es **efímera**. Si parás/reiniciás la instancia, **puede cambiar**
y te rompe el A record. Solución: **reservar la IP pública** en Oracle (*Reserved Public IP*, dentro
de los límites Always Free) y asignarla a la VNIC de la VM. Así el A record nunca se desincroniza.

---

## Fase 0 — Pre-requisitos
- Cuenta Oracle Cloud (pide tarjeta para verificar; Always Free no cobra).
- Cuenta Vercel (gratis, login con GitHub).
- (Opción 1) un dominio comprado.
- Las API keys de datos a mano (Polygon, Finnhub, Alpha Vantage, etc.).

## Fase 1 — Provisionar la VM
1. Crear instancia **VM.Standard.A1.Flex** (Ampere ARM). Pedir p. ej. **2 OCPU / 12 GB RAM**
   (entrás holgado en Always Free, que permite hasta 4 OCPU / 24 GB).
   - Imagen: **Ubuntu 22.04 (aarch64)**.
   - Guardar la **clave SSH** que generes.
   - Si la región tira "out of capacity" para Ampere, reintentar (otro AD/región) — gotcha conocido.
2. **Reservar IP pública** y asignarla a la instancia.
3. **Abrir puertos — son DOS firewalls** (gotcha clásico de Oracle):
   - **VCN Security List / NSG** (firewall del cloud): ingress TCP **80** y **443** desde `0.0.0.0/0`.
   - **iptables de Ubuntu** (la imagen viene restrictiva): abrir 80/443 también, o el tráfico igual no entra.
     ```
     sudo iptables -I INPUT 5 -p tcp --dport 80  -j ACCEPT
     sudo iptables -I INPUT 5 -p tcp --dport 443 -j ACCEPT
     sudo netfilter-persistent save
     ```

## Fase 2 — Setup del host
```bash
ssh ubuntu@<IP>
sudo apt update && sudo apt -y upgrade
# Docker + compose
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu      # relogin después
# Clonar repo
git clone git@github.com:CuchiBJ/stock-analysis-platform.git
cd stock-analysis-platform
```
- Confirmar que el reloj/NTP está activo (`timedatectl`) — en VM viene por defecto; esto elimina la
  causa raíz del skew que vimos en la laptop.

## Fase 3 — Contenerizar (trabajo de código pendiente)
Falta agregar al repo:
- **`backend/Dockerfile`** — Python 3.9-slim (arm64), instala `requirements.txt`, arranca uvicorn
  **sin** `--reload` (en prod no se usa).
- **`docker-compose.yml`** (raíz) con servicios:
  - `db` (postgres:16), volumen persistente en el disco de la VM.
  - `redis` (redis:7).
  - `api` (build del backend), `depends_on` db/redis, `restart: always`, lee env del `.env`.
  - `caddy` (caddy:2) como reverse proxy → TLS automático para `api.tudominio.com` → `api:8000`.
- **`Caddyfile`**:
  ```
  api.tudominio.com {
      reverse_proxy api:8000
  }
  ```
- **`.env`** en la VM (NO se commitea; ya gitignoreado) con `DATABASE_URL`, `REDIS_URL`, API keys.

> Cuando quieras, esto lo armo yo: Dockerfile + compose + Caddyfile son reutilizables y es el próximo
> paso natural.

## Fase 4 — Migrar la base (370 MB)
```bash
# en la laptop:
pg_dump --no-owner --format=custom stock_analysis > dump.pgcustom
scp dump.pgcustom ubuntu@<IP>:~
# en la VM (con el contenedor db corriendo):
docker compose exec -T db pg_restore --no-owner -d stock_analysis < ~/dump.pgcustom
# correr migraciones alembic por las dudas:
docker compose exec api alembic upgrade head
```

## Fase 5 — Levantar y verificar
```bash
docker compose up -d --build
curl https://api.tudominio.com/api/v1/health/data-freshness   # is_stale:false, heartbeats ok
```
- Confirmar que el scheduler arranca y escribe (ver heartbeats).

## Fase 6 — Frontend en Vercel
1. Importar el repo en Vercel, root = `frontend/`.
2. Env var `NEXT_PUBLIC_API_URL=https://api.tudominio.com` (o el `*.vercel.app` si todavía no comprás dominio — pero entonces la API necesita igual su https vía Opción 2).
3. (Opcional) agregar `app.tudominio.com` como dominio del proyecto en Vercel.

## Fase 7 — Operación
- **Backups Postgres** desde el día 1: cron diario `pg_dump` → Object Storage de Oracle (Always Free
  da 20 GB) o a otro lado.
- **Auto-arranque**: `restart: always` en compose hace que todo vuelva solo si la VM reinicia.
- **Updates**: `git pull && docker compose up -d --build` para desplegar cambios.
- **Monitoreo**: el panel `/health` + el PipelineHealthChip ya te muestran si el scheduler está vivo.

---

## Checklist de gotchas
- [ ] IP pública **reservada** (no efímera).
- [ ] Puertos 80/443 abiertos en **ambos** firewalls (VCN **y** iptables).
- [ ] A record `api` → IP de la VM; en Cloudflare dejarlo **DNS-only** si Caddy maneja TLS.
- [ ] uvicorn en prod **sin `--reload`**.
- [ ] `.env` con secrets **no** commiteado.
- [ ] Cron de backup configurado.
- [ ] Capacidad Ampere: reintentar si "out of capacity".
```
