"""Crea (o restablece) un usuario administrador.

Uso:
    python -m scripts.create_admin --email admin@misalon.com --name "Admin" --password "secreto123"
"""

import argparse

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Role, User


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea un usuario administrador")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Administrador")
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    if not 8 <= len(args.password) <= 72:
        parser.error("La contraseña debe tener entre 8 y 72 caracteres")

    email = args.email.strip().lower()
    with SessionLocal() as db:
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
