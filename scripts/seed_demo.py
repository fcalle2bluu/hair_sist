"""Carga datos de ejemplo: categorías, servicios, estilistas con horario y clientes.

Uso:
    python -m scripts.seed_demo
"""

from datetime import time
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Client, Employee, EmployeeSchedule, Service, ServiceCategory

CATALOG = {
    "Cabello": [
        ("Corte de dama", "35.00", 45),
        ("Corte de caballero", "20.00", 30),
        ("Brushing", "25.00", 40),
        ("Tinte completo", "90.00", 120),
        ("Mechas / balayage", "150.00", 180),
    ],
    "Uñas": [
        ("Manicure", "20.00", 40),
        ("Pedicure", "30.00", 50),
        ("Uñas acrílicas", "70.00", 90),
    ],
    "Estética": [
        ("Diseño de cejas", "15.00", 20),
        ("Limpieza facial", "60.00", 60),
    ],
}

STYLISTS = [
    ("Ana", "Torres", "#ec4899", ["Cabello"]),
    ("Luis", "Ramírez", "#3b82f6", ["Cabello"]),
    ("María", "Quispe", "#10b981", ["Uñas", "Estética"]),
]

CLIENTS = [
    ("Carla", "Mendoza", "987654321"),
    ("Jorge", "Paredes", "912345678"),
    ("Lucía", "Fernández", "998877665"),
]


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(ServiceCategory.id).limit(1)):
            print("Ya hay datos cargados; no se hizo nada.")
            return

        services_by_category: dict[str, list[Service]] = {}
        for category_name, items in CATALOG.items():
            category = ServiceCategory(name=category_name)
            services_by_category[category_name] = [
                Service(category=category, name=name, price=Decimal(price), duration_minutes=minutes)
                for name, price, minutes in items
            ]
            db.add_all(services_by_category[category_name])

        for first, last, color, categories in STYLISTS:
            employee = Employee(first_name=first, last_name=last, color=color)
            employee.services = [s for c in categories for s in services_by_category[c]]
            # Lunes a sábado 9:00-13:00 y 14:00-19:00
            employee.schedules = [
                EmployeeSchedule(weekday=day, start_time=start, end_time=end)
                for day in range(6)
                for start, end in ((time(9), time(13)), (time(14), time(19)))
            ]
            db.add(employee)

        db.add_all(Client(first_name=f, last_name=l, phone=p) for f, l, p in CLIENTS)
        db.commit()
    print("Datos de demostración cargados.")


if __name__ == "__main__":
    main()
