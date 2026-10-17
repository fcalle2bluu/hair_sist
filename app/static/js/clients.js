/* Clientes: búsqueda, ficha, notas/fórmulas e historial de citas. */

document.addEventListener("alpine:init", () => {
  Alpine.data("clients", () => ({
    q: "",
    page: { items: [], total: 0 },
    skip: 0,
    limit: 25,
    loading: false,
    selected: null,
    notes: [],
    history: [],
    noteForm: { kind: "general", content: "" },
    form: null,
    saving: false,

    async init() {
      this.load();
      const id = Alpine.store("app").params.id;
      if (id) {
        try {
          this.open(await API.get(`/clients/${id}`));
        } catch (e) {
          Alpine.store("app").error(e);
        }
      }
    },

    async load() {
      this.loading = true;
      try {
        this.page = await API.get("/clients", { q: this.q.trim(), skip: this.skip, limit: this.limit });
      } catch (e) {
        Alpine.store("app").error(e);
      } finally {
        this.loading = false;
      }
    },

    search() {
      this.skip = 0;
      this.load();
    },

    pageBy(n) {
      this.skip = Math.max(0, this.skip + n * this.limit);
      this.load();
    },

    async open(client) {
      this.selected = client;
      this.notes = [];
      this.history = [];
      try {
        [this.notes, this.history] = await Promise.all([
          API.get(`/clients/${client.id}/notes`),
          API.get(`/clients/${client.id}/appointments`),
        ]);
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    get completedVisits() {
      return this.history.filter((a) => a.status === "completada");
    },

    newClient() {
      this.form = { id: null, first_name: "", last_name: "", phone: "", email: "", birth_date: "", allergies: "", notes: "" };
    },

    editClient() {
      const c = this.selected;
      this.form = Object.fromEntries(
        ["id", "first_name", "last_name", "phone", "email", "birth_date", "allergies", "notes"].map((k) => [k, c[k] ?? ""])
      );
    },

    async save() {
      const f = this.form;
      const body = {
        first_name: f.first_name,
        last_name: f.last_name || "",
        ...cleanForm(f, ["phone", "email", "birth_date", "allergies", "notes"]),
      };
      this.saving = true;
      try {
        const saved = f.id ? await API.patch(`/clients/${f.id}`, body) : await API.post("/clients", body);
        Alpine.store("app").toast(f.id ? "Cliente actualizado" : "Cliente registrado");
        this.form = null;
        await this.load();
        this.open(saved);
      } catch (e) {
        Alpine.store("app").error(e);
      } finally {
        this.saving = false;
      }
    },

    async addNote() {
      if (!this.noteForm.content.trim()) return;
      try {
        const note = await API.post(`/clients/${this.selected.id}/notes`, this.noteForm);
        this.notes = [note, ...this.notes];
        this.noteForm = { kind: this.noteForm.kind, content: "" };
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    async deactivate() {
      if (!confirm(`¿Desactivar a ${this.selected.first_name}? Su historial se conserva.`)) return;
      try {
        await API.del(`/clients/${this.selected.id}`);
        Alpine.store("app").toast("Cliente desactivado");
        this.selected = null;
        this.load();
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },
  }));
});
