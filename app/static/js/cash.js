/* Caja: apertura, cobro (POS), movimientos, cierre con arqueo y anulaciones. */

const round2 = (n) => Math.round(n * 100) / 100;

document.addEventListener("alpine:init", () => {
  Alpine.data("cashView", () => ({
    loading: true,
    session: null,
    sales: [],
    pending: [],
    services: [],
    employees: [],
    history: [],
    openForm: { amount: "", notes: "" },
    pos: null,
    movement: null,
    closing: null,
    closed: null,
    receipt: null,
    voiding: null,
    saving: false,

    async init() {
      await this.load();
      try {
        [this.services, this.employees] = await Promise.all([API.get("/services"), API.get("/employees")]);
      } catch (e) {
        Alpine.store("app").error(e);
      }
      this.$watch("$store.app.params", (p) => p.cita && this.openFromAppointment(Number(p.cita)));
      const cita = Alpine.store("app").params.cita;
      if (cita) this.openFromAppointment(Number(cita));
    },

    async load() {
      const app = Alpine.store("app");
      try {
        this.session = await API.get("/cash/current");
        if (this.session) {
          const [sales, appts] = await Promise.all([
            API.get("/sales", {
              cash_session_id: this.session.id,
              date_from: Fmt.dayOf(this.session.opened_at),
              date_to: Fmt.today(),
            }),
            API.get("/appointments", { date_from: Fmt.today(), status: ["pendiente", "confirmada", "en_curso", "completada"] }),
          ]);
          this.sales = sales;
          this.pending = appts.filter((a) => !a.is_paid);
        }
        if (app.isAdmin) this.history = await API.get("/cash/sessions", { limit: 10 });
      } catch (e) {
        app.error(e);
      } finally {
        this.loading = false;
      }
    },

    async openSession() {
      this.saving = true;
      try {
        await API.post("/cash/open", {
          opening_amount: Number(this.openForm.amount || 0).toFixed(2),
          notes: this.openForm.notes || null,
        });
        Alpine.store("app").toast("Caja abierta");
        this.openForm = { amount: "", notes: "" };
        this.closed = null;
        await this.load();
      } catch (e) {
        Alpine.store("app").error(e);
      } finally {
        this.saving = false;
      }
    },

    /* ---------- Cobro ---------- */
    blankItem() {
      return { service_id: "", employee_id: "", unit_price: "", quantity: 1, discount: "0" };
    },

    newPos(appointment = null) {
      this.pos = {
        appointment_id: appointment?.id ?? null,
        appointmentLabel: appointment ? `${Fmt.time(appointment.start_at)} · ${appointment.employee.first_name}` : "",
        client: appointment?.client ?? null,
        items: appointment
          ? appointment.services.map((s) => ({
              service_id: s.service_id,
              employee_id: appointment.employee.id,
              unit_price: s.price,
              quantity: 1,
              discount: "0",
            }))
          : [this.blankItem()],
        discount: "0",
        payments: [{ method: "efectivo", amount: "" }],
        received: "",
        notes: "",
      };
      this.fillPayment();
    },

    async openFromAppointment(id) {
      const app = Alpine.store("app");
      app.go("caja"); // limpia el parámetro de la URL
      if (!this.session) return app.toast("Abre la caja antes de cobrar", "error");
      try {
        const a = await API.get(`/appointments/${id}`);
        if (a.is_paid) return app.toast("Esta cita ya fue cobrada", "error");
        this.newPos(a);
      } catch (e) {
        app.error(e);
      }
    },

    serviceName(id) {
      return this.services.find((s) => s.id === Number(id))?.name ?? "";
    },

    onServiceChange(item) {
      const s = this.services.find((x) => x.id === Number(item.service_id));
      if (s) item.unit_price = s.price;
      this.fillPayment();
    },

    itemTotal(i) {
      return Math.max(0, round2(Number(i.unit_price || 0) * Number(i.quantity || 1) - Number(i.discount || 0)));
    },

    get posSubtotal() {
      return round2(this.pos.items.reduce((sum, i) => sum + this.itemTotal(i), 0));
    },

    get posTotal() {
      return Math.max(0, round2(this.posSubtotal - Number(this.pos.discount || 0)));
    },

    get paidSum() {
      return round2(this.pos.payments.reduce((sum, p) => sum + Number(p.amount || 0), 0));
    },

    get remaining() {
      return round2(this.posTotal - this.paidSum);
    },

    get cashPaid() {
      return this.pos.payments.filter((p) => p.method === "efectivo").reduce((s, p) => s + Number(p.amount || 0), 0);
    },

    get change() {
      return this.pos.received ? round2(Number(this.pos.received) - this.cashPaid) : 0;
    },

    /** Con un solo medio de pago, el monto sigue automáticamente al total. */
    fillPayment() {
      if (this.pos.payments.length === 1) this.pos.payments[0].amount = this.posTotal.toFixed(2);
    },

    addPayment() {
      this.pos.payments.push({ method: "tarjeta", amount: this.remaining > 0 ? this.remaining.toFixed(2) : "" });
    },

    async submitSale() {
      const app = Alpine.store("app");
      const p = this.pos;
      const items = p.items
        .filter((i) => i.service_id)
        .map((i) => ({
          service_id: Number(i.service_id),
          employee_id: i.employee_id ? Number(i.employee_id) : null,
          quantity: Number(i.quantity || 1),
          unit_price: Number(i.unit_price || 0).toFixed(2),
          discount: Number(i.discount || 0).toFixed(2),
        }));
      if (!items.length) return app.toast("Agrega al menos un servicio", "error");
      if (this.remaining !== 0) return app.toast("Los pagos deben sumar el total", "error");
      const payments = p.payments
        .filter((x) => Number(x.amount) > 0)
        .map((x) => ({ method: x.method, amount: Number(x.amount).toFixed(2), reference: x.reference || null }));
      this.saving = true;
      try {
        const sale = await API.post("/sales", {
          client_id: p.client?.id ?? null,
          appointment_id: p.appointment_id,
          items,
          discount: Number(p.discount || 0).toFixed(2),
          payments,
          notes: p.notes || null,
        });
        this.receipt = { ...sale, change: this.change > 0 ? this.change : 0 };
        this.pos = null;
        app.toast("Venta registrada");
        this.load();
      } catch (e) {
        app.error(e);
      } finally {
        this.saving = false;
      }
    },

    /* ---------- Movimientos y cierre ---------- */
    async saveMovement() {
      const m = this.movement;
      try {
        await API.post("/cash/movements", { type: m.type, amount: Number(m.amount || 0).toFixed(2), concept: m.concept });
        Alpine.store("app").toast(m.type === "ingreso" ? "Ingreso registrado" : "Egreso registrado");
        this.movement = null;
        this.load();
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    get closeDiff() {
      if (this.closing?.counted === "" || !this.session) return null;
      return round2(Number(this.closing.counted) - Number(this.session.summary.expected_cash));
    },

    async closeSession() {
      try {
        this.closed = await API.post("/cash/close", {
          counted_cash: Number(this.closing.counted || 0).toFixed(2),
          notes: this.closing.notes || null,
        });
        this.closing = null;
        this.session = null;
        Alpine.store("app").toast("Caja cerrada");
        this.load();
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    async confirmVoid() {
      try {
        await API.post(`/sales/${this.voiding.sale.id}/void`, { reason: this.voiding.reason });
        Alpine.store("app").toast("Venta anulada");
        this.voiding = null;
        this.load();
      } catch (e) {
        Alpine.store("app").error(e);
      }
    },

    clientName(c) {
      return c ? `${c.first_name} ${c.last_name}`.trim() : "Cliente ocasional";
    },
  }));
});
