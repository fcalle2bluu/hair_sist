/* Servicios, estilistas y usuarios. */

document.addEventListener("alpine:init", () => {
  /* ---------- Servicios ---------- */
  Alpine.data("servicesView", () => ({
    categories: [],
    services: [],
    category: "",
    q: "",
    showInactive: false,
    form: null,
    catForm: null,
    saving: false,

    init() {
      this.load();
    },

    async load() {
      try {
        [this.categories, this.services] = await Promise.all([
          API.get("/service-categories"),
          API.get("/services", { include_inactive: this.showInactive }),
        ]);
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    get filtered() {
      const q = this.q.trim().toLowerCase();
      return this.services.filter(
        (s) =>
          (this.category === "" || s.category_id === this.category || (this.category === null && !s.category_id)) &&
          (!q || s.name.toLowerCase().includes(q))
      );
    },

    countIn(categoryId) {
      return this.services.filter((s) => s.category_id === categoryId).length;
    },

    newService() {
      this.form = { id: null, name: "", category_id: this.category || "", description: "", price: "", duration_minutes: 30 };
    },

    edit(s) {
      this.form = {
        id: s.id,
        name: s.name,
        category_id: s.category_id ?? "",
        description: s.description ?? "",
        price: s.price,
        duration_minutes: s.duration_minutes,
      };
    },

    async save() {
      const f = this.form;
      const body = {
        name: f.name,
        category_id: f.category_id ? Number(f.category_id) : null,
        description: f.description || null,
        price: Number(f.price || 0).toFixed(2),
        duration_minutes: Number(f.duration_minutes),
      };
      this.saving = true;
      try {
        if (f.id) await API.patch(`/services/${f.id}`, body);
        else await API.post("/services", body);
        Alpine.store("app").toast("Servicio guardado");
        this.form = null;
        this.load();
      } catch (e) {
        Alpine.store("app").error(e);
      } finally {
        this.saving = false;
      }
    },

    async toggleActive(s) {
      try {
        if (s.is_active) await API.del(`/services/${s.id}`);
        else await API.patch(`/services/${s.id}`, { is_active: true });
        Alpine.store("app").toast(s.is_active ? "Servicio desactivado" : "Servicio activado");
        this.load();
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    async saveCategory() {
      const f = this.catForm;
      try {
        if (f.id) await API.patch(`/service-categories/${f.id}`, { name: f.name });
        else await API.post("/service-categories", { name: f.name });
        Alpine.store("app").toast("Categoría guardada");
        this.catForm = null;
        this.load();
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },
  }));

  /* ---------- Estilistas ---------- */
  Alpine.data("employeesView", () => ({
    employees: [],
    services: [],
    users: [],
    showInactive: false,
    form: null,
    tab: "datos",
    schedule: [],
    timeOff: [],
    toForm: { start: "", end: "", reason: "" },
    saving: false,

    init() {
      this.load();
    },

    async load() {
      const app = Alpine.store("app");
      try {
        const [employees, services, users] = await Promise.all([
          API.get("/employees", { include_inactive: this.showInactive }),
          API.get("/services"),
          app.isAdmin ? API.get("/users") : Promise.resolve([]),
        ]);
        Object.assign(this, { employees, services, users });
      } catch (e) {
        app.error(e);
      }
    },

    worksOn(emp, day) {
      return emp.schedules.some((b) => b.weekday === day);
    },

    hoursOn(emp, day) {
      return emp.schedules
        .filter((b) => b.weekday === day)
        .map((b) => `${b.start_time.slice(0, 5)}–${b.end_time.slice(0, 5)}`)
        .join(", ");
    },

    get linkableUsers() {
      return this.users.filter((u) => u.is_active && (!u.employee_id || u.employee_id === this.form?.id));
    },

    newEmployee() {
      this.form = { id: null, first_name: "", last_name: "", phone: "", email: "", color: "#a8456a", user_id: "", service_ids: [], is_active: true };
      this.schedule = WEEKDAYS.map((_, d) => (d < 6 ? [{ start: "09:00", end: "19:00" }] : []));
      this.timeOff = [];
      this.tab = "datos";
    },

    async edit(emp) {
      this.form = {
        id: emp.id,
        first_name: emp.first_name,
        last_name: emp.last_name,
        phone: emp.phone ?? "",
        email: emp.email ?? "",
        color: emp.color,
        user_id: emp.user_id ?? "",
        service_ids: emp.services.map((s) => s.id),
        is_active: emp.is_active,
      };
      this.schedule = WEEKDAYS.map((_, d) =>
        emp.schedules.filter((b) => b.weekday === d).map((b) => ({ start: b.start_time.slice(0, 5), end: b.end_time.slice(0, 5) }))
      );
      this.tab = "datos";
      this.timeOff = [];
      try {
        this.timeOff = await API.get(`/employees/${emp.id}/time-off`);
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    toggleService(id) {
      const ids = this.form.service_ids;
      this.form.service_ids = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
    },

    copyMonday() {
      for (let d = 1; d < 6; d++) this.schedule[d] = this.schedule[0].map((b) => ({ ...b }));
    },

    async save() {
      const f = this.form;
      const body = {
        first_name: f.first_name,
        last_name: f.last_name || "",
        phone: f.phone || null,
        email: f.email || null,
        color: f.color,
        user_id: f.user_id ? Number(f.user_id) : null,
      };
      const blocks = this.schedule.flatMap((list, d) => list.map((b) => ({ weekday: d, start_time: b.start, end_time: b.end })));
      this.saving = true;
      try {
        let id = f.id;
        if (id) {
          await API.patch(`/employees/${id}`, { ...body, is_active: f.is_active });
          await API.put(`/employees/${id}/services`, { service_ids: f.service_ids });
        } else {
          id = (await API.post("/employees", { ...body, service_ids: f.service_ids })).id;
        }
        await API.put(`/employees/${id}/schedule`, blocks);
        Alpine.store("app").toast("Estilista guardado");
        this.form = null;
        this.load();
      } catch (e) {
        Alpine.store("app").error(e);
      } finally {
        this.saving = false;
      }
    },

    async addTimeOff() {
      const t = this.toForm;
      if (!t.start || !t.end) return Alpine.store("app").toast("Indica inicio y fin", "error");
      try {
        const created = await API.post(`/employees/${this.form.id}/time-off`, {
          start_at: t.start,
          end_at: t.end,
          reason: t.reason || null,
        });
        this.timeOff = [...this.timeOff, created].sort((a, b) => a.start_at.localeCompare(b.start_at));
        this.toForm = { start: "", end: "", reason: "" };
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    async removeTimeOff(t) {
      try {
        await API.del(`/employees/${this.form.id}/time-off/${t.id}`);
        this.timeOff = this.timeOff.filter((x) => x.id !== t.id);
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },
  }));

  /* ---------- Usuarios ---------- */
  Alpine.data("usersView", () => ({
    users: [],
    form: null,
    saving: false,

    init() {
      this.load();
    },

    async load() {
      try {
        this.users = await API.get("/users");
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    newUser() {
      this.form = { id: null, email: "", full_name: "", role: "recepcionista", password: "", is_active: true };
    },

    edit(u) {
      this.form = { id: u.id, email: u.email, full_name: u.full_name, role: u.role, password: "", is_active: u.is_active };
    },

    async save() {
      const f = this.form;
      const body = { email: f.email, full_name: f.full_name, role: f.role };
      if (f.password) body.password = f.password;
      this.saving = true;
      try {
        if (f.id) await API.patch(`/users/${f.id}`, { ...body, is_active: f.is_active });
        else await API.post("/users", { ...body, password: f.password });
        Alpine.store("app").toast("Usuario guardado");
        this.form = null;
        this.load();
      } catch (e) {
        Alpine.store("app").error(e);
      } finally {
        this.saving = false;
      }
    },
  }));
});
