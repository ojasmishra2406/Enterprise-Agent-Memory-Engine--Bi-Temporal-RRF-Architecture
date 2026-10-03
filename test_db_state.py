from app.database import SessionLocal
from app.models import Memory
from sqlalchemy import select
import asyncio

async def main():
    async with SessionLocal() as db:
        stmt = select(Memory).where(Memory.id.in_([
            '87eba12e-9305-4641-ac76-e81c1125284c',
            '304df755-5583-46ab-ba8f-3111056eabaa',
            '488ec483-ab5a-4c0f-af76-e1cf47c538a4'
        ]))
        mems = (await db.scalars(stmt)).all()
        for m in mems:
            print(f"ID: {m.id}, State: {m.temporal_state.name}, SupersededBy: {m.superseded_by_id}, Content: {m.content}")

asyncio.run(main())
