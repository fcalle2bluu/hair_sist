/* Núcleo de la interfaz: cliente de la API, formatos y estado global (sesión, rutas, avisos). */

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

const API = {
  token: localStorage.getItem("token"),

  setToken(token) {
    this.token = token;
    if (token) localStorage.setItem("token", token);
    else localStorage.removeItem("token");
  },

  async request(method, path, body, { form = false } = {}) {
    const headers = {};
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    let payload;
    if (form) {
      payload = new URLSearchParams(body);
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    const res = await fetch("/api" + path, { method, headers, body: payload });
    if (res.status === 401 && !form) {
      Alpine.store("app").logout();
      throw new ApiError("Tu sesión expiró, vuelve a ingresar", 401);
    }
    if (res.status === 204) return null;
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new ApiError(errorMessage(data), res.status);
    return data;
  },

  get(path, params) { return this.request("GET", path + queryString(params)); },
  post(path, body) { return this.request("POST", path, body ?? {}); },
  patch(path, body) { return this.request("PATCH", path, body); },
  put(path, body) { return this.request("PUT", path, body); },
  del(path) { return this.request("DELETE", path); },
};

function queryString(params) {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => sp.append(key, v));
    else sp.append(key, value);
  }
  const s = sp.toString();
  return s ? "?" + s : "";
}

const FIELD_NAMES = {
  first_name: "Nombre", last_name: "Apellido", phone: "Teléfono", email: "Email", password: "Contraseña",
  full_name: "Nombre", price: "Precio", duration_minutes: "Duración", name: "Nombre", amount: "Monto",
  start_at: "Inicio", service_ids: "Servicios", concept: "Concepto", reason: "Motivo",
};

function errorMessage(data) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const field = e.loc?.[e.loc.length - 1];
        return `${FIELD_NAMES[field] ?? field ?? ""}: ${e.msg}`.replace(/^: /, "");
      })
      .join(" · ");
  }
  return "Ocurrió un error inesperado";
}

/** Convierte "" en null para los campos opcionales de un formulario. */
function cleanForm(form, keys) {
  const out = {};
  for (const key of keys) {
    const value = form[key];
    out[key] = value === "" || value === undefined ? null : value;
  }
  return out;
}

/* ---------- Formatos (siempre en la zona horaria del salón) ---------- */
const Fmt = {
  tz: "America/La_Paz",
  currency: "Bs",

  money(value) {
    const n = Number(value || 0);
    return `${this.currency} ${n.toLocaleString("es", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  },
  time(iso) {
    if (!iso) return "";
    return new Intl.DateTimeFormat("es", { timeZone: this.tz, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
  },
  dateTime(iso) {
    if (!iso) return "";
    return new Intl.DateTimeFormat("es", { timeZone: this.tz, day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
  },
  date(iso) {
    if (!iso) return "";
    return new Intl.DateTimeFormat("es", { timeZone: this.tz, day: "2-digit", month: "short", year: "numeric" }).format(new Date(iso));
  },
  /** "YYYY-MM-DD" → "viernes, 17 de octubre de 2026" */
  dayLong(day) {
    if (!day) return "";
    const text = new Intl.DateTimeFormat("es", { timeZone: "UTC", weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date(day + "T12:00:00Z"));
    return text.charAt(0).toUpperCase() + text.slice(1);
  },
  /** "YYYY-MM-DD" → "17 oct 2026" (fechas sin hora, como cumpleaños) */
  plainDate(day) {
    if (!day) return "";
    return new Intl.DateTimeFormat("es", { timeZone: "UTC", day: "numeric", month: "short", year: "numeric" }).format(new Date(day + "T12:00:00Z"));
  },
  today() {
    return new Intl.DateTimeFormat("en-CA", { timeZone: this.tz }).format(new Date());
  },
  dayOf(iso) {
    if (!iso) return "";
    return new Intl.DateTimeFormat("en-CA", { timeZone: this.tz }).format(new Date(iso));
  },
  addDays(day, n) {
    const d = new Date(day + "T12:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  },
  /** Minutos desde la medianoche en la zona del salón. */
  minutesOfDay(iso) {
    const parts = new Intl.DateTimeFormat("en-US", { timeZone: this.tz, hour: "numeric", minute: "numeric", hourCycle: "h23" }).formatToParts(new Date(iso));
    const get = (type) => Number(parts.find((p) => p.type === type).value);
    return get("hour") * 60 + get("minute");
  },
  /** 0 = lunes ... 6 = domingo */
  weekday(day) {
    return (new Date(day + "T12:00:00Z").getUTCDay() + 6) % 7;
  },
  hhmm(minutes) {
    return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
  },
  toMinutes(hhmm) {
    const [h, m] = hhmm.split(":").map(Number);
    return h * 60 + m;
  },
  duration(minutes) {
    const h = Math.floor(minutes / 60), m = minutes % 60;
    return h ? (m ? `${h} h ${m} min` : `${h} h`) : `${m} min`;
  },
  initials(name) {
    return (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
  },
};

const WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const WEEKDAYS_SHORT = ["L", "M", "X", "J", "V", "S", "D"];

const STATUS = {
  pendiente: "Pendiente",
  confirmada: "Confirmada",
  en_curso: "En curso",
  completada: "Completada",
  cancelada: "Cancelada",
  no_asistio: "No asistió",
};
const ROLES = { admin: "Administrador", recepcionista: "Recepcionista", estilista: "Estilista" };
const PAY_METHODS = { efectivo: "Efectivo", tarjeta: "Tarjeta", transferencia: "Transferencia", otro: "Otro" };

const ICONS = {
  agenda: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>',
  clientes: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  caja: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h4"/></svg>',
  servicios: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.12 15.88M14.47 14.48 20 20M8.12 8.12 12 12"/></svg>',
  estilistas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 7h7l-5.5 4.5L18.5 21 12 16.5 5.5 21l2-7.5L2 9h7z"/></svg>',
  usuarios: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
};

const ALL_ROLES = ["admin", "recepcionista", "estilista"];
const NAV = [
  { route: "agenda", label: "Agenda", roles: ALL_ROLES },
  { route: "clientes", label: "Clientes", roles: ALL_ROLES },
  { route: "caja", label: "Caja", roles: ["admin", "recepcionista"] },
  { route: "servicios", label: "Servicios", roles: ALL_ROLES },
  { route: "estilistas", label: "Estilistas", roles: ALL_ROLES },
  { route: "usuarios", label: "Usuarios", roles: ["admin"] },
];

document.addEventListener("alpine:init", () => {
  Alpine.store("app", {
    ready: false,
    user: null,
    config: null,
    route: "agenda",
    params: {},
    toasts: [],
    menuOpen: false,
    isMobile: false,

    async init() {
      const mq = window.matchMedia("(max-width: 760px)");
      this.isMobile = mq.matches;
      mq.addEventListener("change", (e) => (this.isMobile = e.matches));
      try {
        this.config = await API.get("/config");
        Fmt.tz = this.config.timezone;
        Fmt.currency = this.config.currency_symbol;
        document.title = this.config.app_name;
      } catch (e) {
        this.error(e);
      }
      if (API.token) {
        try {
          this.user = await API.get("/auth/me");
        } catch {
          API.setToken(null);
        }
      }
      this.readHash();
      window.addEventListener("hashchange", () => this.readHash());
      this.ready = true;
    },

    readHash() {
      const [path, query] = location.hash.replace(/^#\/?/, "").split("?");
      const route = NAV.some((n) => n.route === path) ? path : "agenda";
      this.params = Object.fromEntries(new URLSearchParams(query || ""));
      this.route = this.canSee(route) ? route : "agenda";
      this.menuOpen = false;
    },

    go(route, params) {
      location.hash = "#/" + route + queryString(params);
    },

    get nav() {
      return NAV.filter((n) => this.canSee(n.route));
    },

    get currentLabel() {
      return NAV.find((n) => n.route === this.route)?.label ?? "";
    },

    canSee(route) {
      const item = NAV.find((n) => n.route === route);
      return !!(this.user && item && item.roles.includes(this.user.role));
    },

    get isAdmin() { return this.user?.role === "admin"; },
    get isStaff() { return ["admin", "recepcionista"].includes(this.user?.role); },

    async login(email, password) {
      const token = await API.request("POST", "/auth/login", { username: email, password }, { form: true });
      API.setToken(token.access_token);
      this.user = await API.get("/auth/me");
      this.readHash();
    },

    logout() {
      API.setToken(null);
      this.user = null;
    },

    toast(message, type = "ok") {
      const id = Date.now() + Math.random();
      this.toasts.push({ id, message, type });
      setTimeout(() => (this.toasts = this.toasts.filter((t) => t.id !== id)), type === "error" ? 6000 : 3500);
    },

    error(e) {
      this.toast(e?.message || String(e), "error");
    },
  });

  /* Pantalla de inicio de sesión */
  Alpine.data("loginForm", () => ({
    email: "",
    password: "",
    loading: false,
    errorMsg: "",
    async submit() {
      this.loading = true;
      this.errorMsg = "";
      try {
        await Alpine.store("app").login(this.email, this.password);
        this.password = "";
      } catch (e) {
        this.errorMsg = e.message;
      } finally {
        this.loading = false;
      }
    },
  }));

  /* Cambio de contraseña (menú del usuario) */
  Alpine.data("passwordForm", () => ({
    open: false,
    current: "",
    next: "",
    saving: false,
    async save() {
      this.saving = true;
      try {
        await API.post("/auth/change-password", { current_password: this.current, new_password: this.next });
        Alpine.store("app").toast("Contraseña actualizada");
        this.open = false;
        this.current = this.next = "";
      } catch (e) {
        Alpine.store("app").error(e);
      } finally {
        this.saving = false;
      }
    },
  }));
});

/* Buscador de clientes reutilizable (agenda y caja). */
function clientPicker() {
  return {
    query: "",
    results: [],
    open: false,
    async search() {
      const q = this.query.trim();
      if (q.length < 2) {
        this.results = [];
        this.open = false;
        return;
      }
      try {
        this.results = (await API.get("/clients", { q, limit: 8 })).items;
        this.open = true;
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },
  };
}
