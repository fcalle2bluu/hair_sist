"""Crea (o restablece) un usuario administrador.

Uso:
    python -m scripts.create_admin --email admin@misalon.com --name "Admin" --password "secreto123"

En servidores (ej. Render) se puede usar en el comando de arranque con las variables
ADMIN_EMAIL y ADMIN_PASSWORD y la opción --if-none, que solo lo crea si todavía no hay
ningún administrador (así no se pisa la contraseña en cada despliegue):
    python -m scripts.create_admin --if-none
"""

import argparse
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Role, User


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea un usuario administrador")
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL"))
    parser.add_argument("--name", default=os.environ.get("ADMIN_NAME", "Administrador"))
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD"))
    parser.add_argument(
        "--if-none", action="store_true", help="No hace nada si ya existe algún administrador"
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.if_none and db.scalar(select(User.id).where(User.role == Role.ADMIN).limit(1)):
            print("Ya existe un administrador; no se hizo nada.")
            return

        if not args.email or not args.password:
            parser.error("Indica --email y --password (o las variables ADMIN_EMAIL y ADMIN_PASSWORD)")
        if not 4 <= len(args.password) <= 72:
            parser.error("La contraseña debe tener entre 4 y 72 caracteres")

        email = args.email.strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, full_name=args.name, role=Role.ADMIN, hashed_password="")
            db.add(user)
            action = "creado"
        else:
            action = "actualizado"
        user.role = Role.ADMIN
        user.is_active = True
        user.hashed_password = hash_password(args.password)
        db.commit()
    print(f"Administrador {action}: {email}")


if __name__ == "__main__":
    main()
