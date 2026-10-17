/* Agenda diaria por estilista: crear, ver, reprogramar y cambiar estado de citas. */

document.addEventListener("alpine:init", () => {
  Alpine.data("agenda", () => ({
    day: Fmt.today(),
    employees: [],
    mobileEmpId: null, // estilista visible en celular (una columna a la vez)
    appointments: [],
    loading: false,
    pxPerMin: 80 / 60, // 80 px por hora
    detail: null,
    cancelMode: null, // "cancelada" | "no_asistio"
    cancelReason: "",
    form: null,
    newClient: null,
    slots: [],
    slotsLoading: false,
    saving: false,

    async init() {
      const app = Alpine.store("app");
      if (app.params.dia) this.day = app.params.dia;
      try {
        let employees = await API.get("/employees");
        if (app.user.role === "estilista") employees = employees.filter((e) => e.id === app.user.employee_id);
        this.employees = employees;
        this.mobileEmpId = employees[0]?.id ?? null;
        await this.load();
      } catch (e) {
        app.error(e);
      }
    },

    async load() {
      this.loading = true;
      try {
        this.appointments = await API.get("/appointments", { date_from: this.day });
      } catch (e) {
        Alpine.store("app").error(e);
      } finally {
        this.loading = false;
      }
    },

    shift(n) {
      this.day = n === 0 ? Fmt.today() : Fmt.addDays(this.day, n);
      this.load();
    },

    /* ---------- Cuadrícula ---------- */
    get weekday() {
      return Fmt.weekday(this.day);
    },

    get range() {
      let start = 24 * 60, end = 0;
      for (const emp of this.employees) {
        for (const b of emp.schedules) {
          if (b.weekday !== this.weekday) continue;
          start = Math.min(start, Fmt.toMinutes(b.start_time));
          end = Math.max(end, Fmt.toMinutes(b.end_time));
        }
      }
      for (const a of this.appointments) {
        start = Math.min(start, Fmt.minutesOfDay(a.start_at));
        end = Math.max(end, Fmt.minutesOfDay(a.end_at));
      }
      if (start >= end) [start, end] = [9 * 60, 19 * 60];
      return { start: Math.floor(start / 60) * 60, end: Math.ceil(end / 60) * 60 };
    },

    get hours() {
      const out = [];
      for (let m = this.range.start; m < this.range.end; m += 60) out.push(m);
      return out;
    },

    apptsOf(emp) {
      return this.appointments.filter((a) => a.employee.id === emp.id);
    },

    activeCount(emp) {
      return this.apptsOf(emp).filter((a) => !["cancelada", "no_asistio"].includes(a.status)).length;
    },

    apptStyle(a) {
      const s = Fmt.minutesOfDay(a.start_at), e = Fmt.minutesOfDay(a.end_at);
      const top = (s - this.range.start) * this.pxPerMin;
      const height = Math.max((e - s) * this.pxPerMin - 2, 20);
      return `top:${top}px;height:${height}px;--c:${a.employee.color}`;
    },

    /** Franjas fuera del horario del estilista (se muestran rayadas). */
    offZones(emp) {
      const { start, end } = this.range;
      const blocks = emp.schedules
        .filter((b) => b.weekday === this.weekday)
        .map((b) => [Fmt.toMinutes(b.start_time), Fmt.toMinutes(b.end_time)])
        .sort((x, y) => x[0] - y[0]);
      const zones = [];
      let cursor = start;
      for (const [s, e] of blocks) {
        if (s > cursor) zones.push([cursor, s]);
        cursor = Math.max(cursor, e);
      }
      if (cursor < end) zones.push([cursor, end]);
      return zones.map(([s, e]) => `top:${(s - start) * this.pxPerMin}px;height:${(e - s) * this.pxPerMin}px`);
    },

    get nowStyle() {
      if (this.day !== Fmt.today()) return null;
      const m = Fmt.minutesOfDay(new Date().toISOString());
      if (m < this.range.start || m > this.range.end) return null;
      return `top:${(m - this.range.start) * this.pxPerMin}px`;
    },

    clickGrid(emp, ev) {
      if (!Alpine.store("app").isStaff || ev.target.closest(".appt")) return;
      const rect = ev.currentTarget.getBoundingClientRect();
      const minutes = this.range.start + Math.floor((ev.clientY - rect.top) / this.pxPerMin / 15) * 15;
      this.openNew(emp, Fmt.hhmm(minutes));
    },

    /* ---------- Formulario de cita ---------- */
    openNew(emp = null, time = "") {
      this.form = {
        id: null,
        client: null,
        employee_id: emp?.id ?? (Alpine.store("app").isMobile ? this.mobileEmpId : null) ?? this.employees[0]?.id ?? "",
        service_ids: [],
        date: this.day,
        time,
        notes: "",
      };
      this.newClient = null;
      this.slots = [];
    },

    openEdit(a) {
      this.form = {
        id: a.id,
        client: a.client,
        employee_id: a.employee.id,
        service_ids: a.services.map((s) => s.service_id),
        date: Fmt.dayOf(a.start_at),
        time: Fmt.time(a.start_at),
        notes: a.notes || "",
      };
      this.detail = null;
      this.newClient = null;
      this.loadSlots();
    },

    get formEmployee() {
      return this.employees.find((e) => e.id === Number(this.form?.employee_id));
    },

    get formServices() {
      return (this.formEmployee?.services ?? []).filter((s) => s.is_active || this.form.service_ids.includes(s.id));
    },

    get formSummary() {
      const chosen = this.formServices.filter((s) => this.form.service_ids.includes(s.id));
      return {
        price: chosen.reduce((sum, s) => sum + Number(s.price), 0),
        minutes: chosen.reduce((sum, s) => sum + s.duration_minutes, 0),
      };
    },

    toggleService(id) {
      const ids = this.form.service_ids;
      this.form.service_ids = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
      this.loadSlots();
    },

    onEmployeeChange() {
      const offered = new Set((this.formEmployee?.services ?? []).map((s) => s.id));
      this.form.service_ids = this.form.service_ids.filter((id) => offered.has(id));
      this.loadSlots();
    },

    async loadSlots() {
      const f = this.form;
      if (!f || !f.employee_id || !f.service_ids.length || !f.date) {
        this.slots = [];
        return;
      }
      this.slotsLoading = true;
      try {
        const res = await API.get("/appointments/availability", {
          employee_id: f.employee_id,
          day: f.date,
          service_ids: f.service_ids,
        });
        this.slots = res.slots.map((s) => Fmt.time(s));
      } catch (e) {
        Alpine.store("app").error(e);
      } finally {
        this.slotsLoading = false;
      }
    },

    startNewClient(name) {
      const [first, ...rest] = name.trim().split(/\s+/);
      this.newClient = { first_name: first || "", last_name: rest.join(" "), phone: "" };
    },

    async saveNewClient() {
      try {
        const c = this.newClient;
        this.form.client = await API.post("/clients", {
          first_name: c.first_name,
          last_name: c.last_name || "",
          phone: c.phone || null,
        });
        this.newClient = null;
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    async save() {
      const f = this.form;
      const app = Alpine.store("app");
      if (!f.client) return app.toast("Elige un cliente", "error");
      if (!f.service_ids.length) return app.toast("Elige al menos un servicio", "error");
      if (!f.time) return app.toast("Elige la hora", "error");
      const body = {
        client_id: f.client.id,
        employee_id: Number(f.employee_id),
        start_at: `${f.date}T${f.time}:00`,
        service_ids: f.service_ids,
        notes: f.notes || null,
      };
      this.saving = true;
      try {
        if (f.id) await API.patch(`/appointments/${f.id}`, body);
        else await API.post("/appointments", body);
        app.toast(f.id ? "Cita actualizada" : "Cita agendada");
        this.form = null;
        this.day = f.date;
        await this.load();
      } catch (e) {
        app.error(e);
      } finally {
        this.saving = false;
      }
    },

    /* ---------- Detalle y estados ---------- */
    openDetail(a) {
      this.detail = a;
      this.cancelMode = null;
      this.cancelReason = "";
    },

    can(status) {
      const app = Alpine.store("app");
      const a = this.detail;
      if (!a) return false;
      const transitions = {
        pendiente: ["confirmada", "en_curso", "completada", "cancelada", "no_asistio"],
        confirmada: ["en_curso", "completada", "cancelada", "no_asistio"],
        en_curso: ["completada"],
      };
      if (!(transitions[a.status] || []).includes(status)) return false;
      return app.isStaff || ["en_curso", "completada"].includes(status);
    },

    get canEdit() {
      return Alpine.store("app").isStaff && ["pendiente", "confirmada"].includes(this.detail?.status);
    },

    get canCharge() {
      const a = this.detail;
      return Alpine.store("app").isStaff && a && !a.is_paid && !["cancelada", "no_asistio"].includes(a.status);
    },

    async setStatus(status, reason = null) {
      try {
        const updated = await API.post(`/appointments/${this.detail.id}/status`, { status, reason: reason || null });
        this.appointments = this.appointments.map((a) => (a.id === updated.id ? updated : a));
        this.detail = updated;
        this.cancelMode = null;
        Alpine.store("app").toast(`Cita: ${STATUS[status].toLowerCase()}`);
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    charge() {
      Alpine.store("app").go("caja", { cita: this.detail.id });
    },
  }));
});
