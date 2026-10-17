# Hair Sist — Sistema para peluquería y salón de belleza

API REST con **FastAPI + PostgreSQL** (SQLAlchemy 2, Alembic, JWT).

## Módulos (fase 1: básicos)

| Módulo | Qué hace |
|---|---|
| Autenticación y usuarios | Login JWT y roles `admin`, `recepcionista` y `estilista` |
| Clientes | Ficha, búsqueda, alergias, notas y fórmulas técnicas, historial de citas |
| Servicios | Categorías y servicios con precio y duración |
| Estilistas | Especialidades, horario semanal (admite turno partido) y ausencias |
| Agenda y citas | Disponibilidad, creación, reprogramación, estados y validación de cruces |
| Caja y ventas | Apertura y cierre con arqueo, cobro con pagos mixtos, movimientos de efectivo y anulación de ventas |

**Fase 2 (intermedios):** inventario, comisiones, reportes y notificaciones.

## Puesta en marcha

```powershell
# 1. Base de datos
docker compose up -d

# 2. Entorno Python
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# 3. Configuración: copia el ejemplo y cambia SECRET_KEY
copy .env.example .env

# 4. Migraciones
alembic upgrade head

# 5. Usuario administrador (y, opcionalmente, datos de ejemplo)
python -m scripts.create_admin --email admin@misalon.com --password "TuClave123"
python -m scripts.seed_demo

# 6. Servidor
uvicorn app.main:app --reload
```

> **Windows:** si `activate` falla con "la ejecución de scripts está deshabilitada", ejecuta una vez
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, o usa los ejecutables del entorno
> sin activarlo: `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`.

- **Interfaz web:** http://localhost:8000
- **Documentación de la API:** http://localhost:8000/docs (botón **Authorize** con tu email y contraseña)

## Interfaz web

La sirve el mismo FastAPI desde `app/static/`. Usa HTML, CSS y [Alpine.js](https://alpinejs.dev), guardado en `app/static/vendor/`, así que no necesita Node, compilación ni internet.

| Pantalla | Quién la ve | Qué permite |
|---|---|---|
| Agenda | todos | Vista por día y por estilista. Clic en un espacio libre para agendar, clic en una cita para confirmarla, iniciarla, reprogramarla, cancelarla o cobrarla |
| Clientes | todos | Búsqueda, ficha con alergias, notas y fórmulas, historial de citas |
| Caja | admin, recepción | Abrir y cerrar caja, cobrar (pagos mixtos y vuelto), ingresos y egresos, ticket imprimible, anular ventas (solo admin) |
| Servicios | todos (edita admin) | Catálogo por categorías |
| Estilistas | todos (edita admin) | Datos, servicios que realiza, horario semanal, ausencias y usuario vinculado |
| Usuarios | admin | Altas, roles, activar o desactivar, restablecer contraseña |

El símbolo de moneda se configura con `CURRENCY_SYMBOL` en `.env` (por defecto `Bs`).

## Pruebas

```powershell
pytest
```

Las pruebas crean y usan una base aparte (`hair_sist_test`) en el mismo Postgres.

## Reglas de negocio importantes

- **Citas sin cruces:** la API valida el horario del estilista, sus ausencias, que realice los servicios y que no tenga otra cita a esa hora. Además, Postgres lo garantiza con una restricción de exclusión (`btree_gist`), así que dos recepcionistas no pueden reservar el mismo horario a la vez.
- **Precio y duración congelados:** la cita guarda el precio y la duración de cada servicio al momento de reservar. Si luego cambia el precio del catálogo, las citas ya creadas no se alteran.
- **Estados de la cita:** `pendiente → confirmada → en_curso → completada`. También puede pasar a `cancelada` o `no_asistio`, que liberan el horario.
- **Cobro:** con `appointment_id` y sin `items`, la venta cobra los servicios de la cita y la marca como completada. La suma de los pagos debe coincidir con el total, y una cita no puede cobrarse dos veces.
- **Caja:** solo puede haber una caja abierta. Al cerrarla se calcula el efectivo esperado (apertura + ventas en efectivo + ingresos − egresos) y la diferencia con lo contado. Las ventas solo se pueden anular mientras su caja siga abierta.
- **Estilistas:** solo ven sus propias citas y únicamente pueden marcarlas como `en_curso` o `completada`.
- **Fechas:** si un `start_at` llega sin zona horaria, se interpreta en la zona `TIMEZONE` del `.env`.

## Estructura

```
app/
  api/deps.py         autenticación, roles y utilidades
  api/routes/         endpoints por módulo
  core/               configuración, seguridad y zona horaria
  db/                 sesión y base declarativa
  models/             tablas SQLAlchemy
  schemas/            modelos Pydantic de entrada y salida
  services/           lógica de negocio (agenda, ventas y caja)
alembic/              migraciones
scripts/              crear admin y datos de ejemplo
tests/
```

## Despliegue en Render

1. Crea una base **PostgreSQL** en Render (New → Postgres) en la misma región que el servicio y copia su **Internal Database URL**.
2. Crea un **Web Service** desde este repositorio con:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:**
     ```
     alembic upgrade head && python -m scripts.create_admin --if-none && uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
3. En **Environment Variables** agrega:

   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | la Internal Database URL de Render (se adapta sola al driver) |
   | `SECRET_KEY` | una clave larga y aleatoria |
   | `TIMEZONE` | `America/La_Paz` |
   | `CURRENCY_SYMBOL` | `Bs` |
   | `ADMIN_EMAIL` | email del primer administrador |
   | `ADMIN_PASSWORD` | su contraseña (mín. 8 caracteres) |

En cada arranque se aplican las migraciones. El administrador solo se crea si todavía no existe ninguno, así que cambiar `ADMIN_PASSWORD` después no modifica la contraseña. La versión de Python se fija en `.python-version`.
