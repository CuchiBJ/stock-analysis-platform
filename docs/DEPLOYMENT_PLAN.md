# Plan de deploy a cloud — Stock Analysis Platform

> Documento de decisión. No ejecuta cambios. Comparar caminos y elegir antes de tocar nada.
> Fecha: 2026-06-09. **Verificar términos de free tiers al momento de ejecutar — cambian seguido.**

## 1. El constraint que define todo

La app **no** es un request-response típico. Tiene un **scheduler always-on**: un loop asyncio
(`DataScheduler._scheduler_loop`) que corre dentro del proceso uvicorn y debe estar vivo 24/7
durante horario de mercado (price cada 15 min, FAST cada 5, SLOW cada 30, tareas nocturnas).

Eso elimina cualquier hosting que **duerma por inactividad** o que sea **serverless scale-to-zero**:
si el proceso se apaga, el scheduler deja de actualizar datos.

Piezas a hostear:
- **Backend** FastAPI/uvicorn + scheduler (un solo proceso always-on).
- **Postgres** — hoy **370 MB**, creciendo (ver §2).
- **Redis** — cache / websocket manager.
- **Frontend** Next.js.

Secrets necesarios: `DATABASE_URL`, `REDIS_URL`, y API keys de datos (Polygon, Finnhub,
Alpha Vantage, etc.).

## 2. Tamaño y crecimiento de la base (dato que manda en Postgres)

| Tabla | Size | Filas |
|---|---|---|
| stock_prices | 294 MB | 1.66M |
| stock_metrics | 58 MB | 109k |
| resto | ~18 MB | — |
| **Total** | **370 MB** | — |

Crecimiento estimado (precios diarios de ~5–6k símbolos + métricas diarias):
**~50–100 MB/mes ≈ 0.6–1.2 GB/año**.

**Implicancia:** los Postgres administrados gratis (Neon / Supabase ≈ **0.5 GB**) **ya no entran
cómodos y los cruzás en semanas**. Esto empuja fuerte hacia **Postgres self-hosted en una VM**
(limitado solo por disco: 30–200 GB) o aceptar un Postgres pago chico.

## 3. Por qué los free tiers comunes NO sirven

| Servicio | Problema para este caso |
|---|---|
| **Render free (web)** | Se **duerme** a los 15 min de inactividad → mata el scheduler. Workers no son free. Postgres free expira a 90 días. |
| **Railway / Fly** | Always-on y buenos, pero **no gratis sostenido** (~US$5/mes). |
| **Cloud Run / Lambda** | Serverless scale-to-zero; un loop constante pelea el modelo (mantener instancia caliente = costo). |
| **Neon / Supabase free** | Postgres 0.5 GB → tu DB no entra / lo superás rápido. |
| **AWS / Azure free** | VM gratis solo **12 meses**, después cobran. |

## 4. Caminos viables

### Path A — Oracle Cloud "Always Free" + Vercel  ·  **costo: $0 (indefinido)**
- VM **ARM Ampere A1**: hasta **4 vCPU / 24 GB RAM / 200 GB disco**, gratis para siempre.
- Corrés **todo** en la VM con `docker-compose`: uvicorn+scheduler, Postgres, Redis.
- Frontend en **Vercel free** (nativo Next.js).
- **Pros:** gratis de verdad y con margen enorme (RAM y disco de sobra para años de datos);
  server estable con NTP → el problema de skew de reloj prácticamente desaparece.
- **Contras:** la capacidad ARM a veces cuesta provisionarla en regiones populares; pide tarjeta
  para verificar; **vos administrás el server** (updates de SO, backups, TLS, monitoreo).

### Path B — GCP e2-micro "Always Free" + Vercel  ·  **costo: $0 (indefinido)**
- VM **e2-micro**: 0.25–1 vCPU compartido / **1 GB RAM** / 30 GB, en regiones us, gratis para siempre.
- Mismo esquema docker-compose + Vercel.
- **Pros:** gratis para siempre, ecosistema GCP.
- **Contras:** **1 GB RAM es ajustado** para Postgres + Redis + uvicorn juntos (andable para carga
  hobby, pero con poco aire; quizá Postgres administrado aparte). 30 GB disco alcanza ~años igual.

### Path C — Railway Hobby  ·  **costo: ~US$5/mes**
- Deploy del backend como **servicio always-on** desde el repo + **plugins** de Postgres y Redis.
- Frontend en Vercel (o en Railway).
- **Pros:** **máxima comodidad**, sin administrar server; deploy por git push; secrets y métricas
  integrados; backups del Postgres gestionados.
- **Contras:** no es gratis; el costo escala con uso/almacenamiento (igual barato a esta escala).
- *Alternativa equivalente:* **Fly.io** (máquinas always-on + Fly Postgres), modelo y precio similares.

## 5. Proyección de costo a medida que crece la DB

| Momento | DB aprox | Path A (Oracle) | Path B (GCP micro) | Path C (Railway) |
|---|---|---|---|---|
| Hoy | 0.37 GB | $0 | $0 | ~$5/mes |
| +1 año | ~1.3 GB | $0 | $0 | ~$5–8/mes |
| +3 años | ~3 GB | $0 (200 GB disco) | $0 (30 GB disco) | ~$8–12/mes |

> Nota: se puede aplicar **retención** (p. ej. recortar `stock_prices` a N años o agregar a barras
> semanales para historia vieja) para mantener la DB chica en cualquier camino.

## 6. Trabajo de migración común a todos los caminos

1. **Contenerizar el backend** — falta `Dockerfile` (Python 3.9, uvicorn). En Path A/B también un
   `docker-compose.yml` con servicios db (postgres), redis, api.
2. **Mover la base** — `pg_dump` del local → `pg_restore` en destino. 370 MB es rápido.
3. **Secrets** — pasar `DATABASE_URL`, `REDIS_URL` y API keys a variables de entorno del proveedor
   (no commitear; hoy están en `.env`, ya gitignoreado).
4. **Frontend** — setear `NEXT_PUBLIC_API_URL` (o equivalente) apuntando al backend cloud; deploy en Vercel.
5. **Scheduler / reloj** — asegurar NTP en el server (en VM viene por defecto). La salvaguarda
   anti-skew ya está, pero un server que no se suspende elimina la causa raíz.
6. **Arranque** — definir cómo levanta el scheduler en prod (hoy va con uvicorn `--reload`; en prod
   sin reload, con `restart: always` en compose o el equivalente del PaaS).

## 7. Pasos por camino (alto nivel)

**Path A (Oracle):**
1. Crear cuenta Oracle Cloud → provisionar VM Ampere (Ubuntu), abrir puertos 80/443.
2. Instalar Docker + compose; clonar repo; crear `.env` con secrets.
3. `docker-compose up -d` (api + postgres + redis); restaurar dump.
4. Reverse proxy + TLS (Caddy/Nginx + Let's Encrypt) para el backend.
5. Deploy frontend en Vercel apuntando al dominio del backend.
6. (Opcional) backups automáticos del Postgres (cron `pg_dump` → object storage).

**Path C (Railway):**
1. Conectar repo a Railway; agregar `Dockerfile` del backend.
2. Agregar plugins Postgres y Redis; copiar sus URLs a env vars del servicio.
3. Restaurar dump al Postgres de Railway.
4. Deploy; verificar heartbeats en `/health/data-freshness`.
5. Frontend en Vercel apuntando a la URL pública de Railway.

## 8. Riesgos / gotchas

- **Oracle ARM capacity:** puede requerir reintentar la creación de la VM en distinto AD/región.
- **Backups:** en self-host son tu responsabilidad — definir cron de `pg_dump` desde el día 1.
- **API rate limits:** las keys de datos siguen siendo el cuello de botella, no cambian por el host.
- **Costo oculto en serverless:** evitar Cloud Run/Lambda para el backend por el loop constante.
- **TLS/dominio:** Vercel lo da gratis para el frontend; el backend en VM necesita proxy + cert.

## 9. Recomendación

- **Costo cero real:** **Path A (Oracle Always Free Ampere) + Vercel.** Margen de RAM/disco para
  años, server estable. A cambio de administrar la VM.
- **Mínimo esfuerzo operativo:** **Path C (Railway ~US$5/mes).** Si valorás no babysittear un server,
  estos US$5 compran tranquilidad; a esta escala es barato.
- **Path B (GCP micro)** solo si querés $0 y preferís ecosistema GCP, asumiendo el apriete de RAM.

Próximo paso sugerido cuando decidas: empezar por **contenerizar el backend** (Dockerfile +
compose), que es trabajo reutilizable en cualquiera de los tres caminos.
