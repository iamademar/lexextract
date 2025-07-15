from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db import get_db
from ..models import Client
from ..schemas.client import ClientRead, ClientCreate, ClientUpdate

router = APIRouter()

@router.get("/", response_model=list[ClientRead])
async def list_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client))
    return result.scalars().all()

@router.post("/", response_model=ClientRead, status_code=201)
async def create_client(payload: ClientCreate, db: AsyncSession = Depends(get_db)):
    new = Client(**payload.model_dump())
    db.add(new)
    await db.commit()
    await db.refresh(new)
    return new

@router.put("/{client_id}", response_model=ClientRead)
async def update_client(client_id: int, payload: ClientUpdate, db: AsyncSession = Depends(get_db)):
    # Fetch existing client
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Update only non-None fields from payload
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(client, field, value)
    
    await db.commit()
    await db.refresh(client)
    return client

@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    # Fetch existing client
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Delete the client
    await db.delete(client)
    await db.commit()
    
    # Return no content (204)
    return

@router.get("/{client_id}", response_model=ClientRead)
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return client