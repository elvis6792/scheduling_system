import asyncio
import sys
from pathlib import Path
from sqlmodel import select


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.models.domain import User, Role
from app.core.database import async_session_maker



async def set_user_role(username: str, role: str):
    valid_roles = [r.value for r in Role]
    if role not in valid_roles:
        print(f"Error: Invalid role '{role}'. Valid roles are: {valid_roles}")
        return

    print(f"Attempting to set role for user '{username}' to '{role}'...")

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if user is None:
            print(f"Error: User '{username}' not found in the database.")
            return

        old_role = user.role
        if old_role == role:
            print(f"User '{username}' already has the role '{role}'. No changes needed.")
            return

        user.role = role
        session.add(user)
        await session.commit()
        await session.refresh(user)

        print(f"Success! Role for user '{username}' has been changed from '{old_role}' to '{user.role}'.")



if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/set_user_role.py <username> <role>")
        print("Example: python scripts/set_user_role.py admin admin")
        sys.exit(1)

    username_to_update = sys.argv[1]
    role_to_set = sys.argv[2]

    asyncio.run(set_user_role(username_to_update, role_to_set))
