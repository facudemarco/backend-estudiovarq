from typing import Optional, List
from fastapi import APIRouter, HTTPException, Form
from sqlalchemy import text
from Database.dbGetConnection import engine
import uuid

router = APIRouter()

@router.get('/houses')
def get_houses():
    try:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT * FROM Houses"))
            rows = result.mappings().all()
            if not rows:
                raise HTTPException(status_code=404, detail="No houses found.")
            houses = []
            for house in rows:
                hid = house["id"]
                main = conn.execute(
                    text("SELECT url FROM houses_main_imgs WHERE house_id = :id"),
                    {"id": hid}
                ).fetchone()
                images = conn.execute(
                    text("SELECT url FROM houses_imgs WHERE house_id = :id"),
                    {"id": hid}
                ).scalars().all()
                data = dict(house)
                data["main_image"] = main[0] if main else None
                data["images"] = images
                houses.append(data)
            return houses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/houses/{id}')
def get_house_by_id(id: str):
    try:
        with engine.connect() as conn:
            res = conn.execute(
                text("SELECT * FROM Houses WHERE id = :id"), {"id": id}
            ).mappings().first()
            if not res:
                raise HTTPException(status_code=404, detail="House not found.")
            main = conn.execute(
                text("SELECT url FROM houses_main_imgs WHERE house_id = :id"), {"id": id}
            ).fetchone()
            images = conn.execute(
                text("SELECT url FROM houses_imgs WHERE house_id = :id"), {"id": id}
            ).scalars().all()
            house = dict(res)
            house["main_image"] = main[0] if main else None
            house["images"] = images
            return house
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/houses/create_house')
async def create_house(
    title: str = Form(...),
    houseType: str = Form(...),
    main_image: str = Form(..., description="Main image"),
    images: List[str] = Form(default=[], description="Additional images")
):
    generated_id = str(uuid.uuid4())
    try:
        # main image
        normalized_main = []
        for img in main_image:
            if isinstance(img, str) and "," in img:
                normalized_main.extend([i.strip() for i in img.split(",") if i.strip()])
            elif img:
                normalized_main.append(img)
        
        normalized_images = []
        for img in images:
            if isinstance(img, str) and "," in img:
                normalized_images.extend([i.strip() for i in img.split(",") if i.strip()])
            elif img:
                normalized_images.append(img)
        
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO Houses (id, title, houseType) VALUES (:id, :title, :houseType)"),
                {"id": generated_id, "title": title, "houseType": houseType}
            )
                
            # Main image insertion
            for img in normalized_main:
                conn.execute(
                    text("INSERT INTO houses_main_imgs (id, house_id, url) VALUES (:id, :house_id, :url)"),
                    {"id": str(uuid.uuid4()), "house_id": generated_id, "url": img}
                )
            
            # Additional images insertion
            for img in normalized_images:
                conn.execute(
                    text("INSERT INTO houses_imgs (id, house_id, url) VALUES (:id, :house_id, :url)"),
                    {"id": str(uuid.uuid4()), "house_id": generated_id, "url": img}
                )
                    
        return {"message": f"House created successfully, ID: {generated_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put('/houses/{id}')
async def update_house(
    house_id: str = Form(...),
    title: Optional[str] = Form(...),
    houseType: Optional[str] = Form(...),
    main_image: Optional[str] = Form(default=None, description="New main image (optional)"),
    images: List[str] | None= Form(default=[], description="New additional images (optional)")
):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    UPDATE Houses SET 
                        title = :title,
                        houseType = :houseType
                    WHERE id = :id
                """),
                {"id": house_id, "title": title, "houseType": houseType}
            )
            
            if main_image is not None:
                conn.execute(
                    text("DELETE FROM houses_main_imgs WHERE house_id = :id"),
                    {"id": house_id}
                )
                normalized_main = []
                for d in main_image:
                    if isinstance(d, str) and "," in d:
                        normalized_main.extend([x.strip() for x in d.split(",") if x.strip()])
                    elif d:
                        normalized_main.append(d.strip())
                for s in normalized_main:
                    conn.execute(
                        text("INSERT INTO houses_main_imgs (id, house_id, url) VALUES (:id, :house_id, :url)"),
                        {"id": str(uuid.uuid4()), "house_id": house_id, "url": s}
                    )
            
            if images is not None:
                conn.execute(
                    text("DELETE FROM houses_imgs WHERE house_id = :id"),
                    {"id": house_id}
                )
                normalized_images = []
                for d in images:
                    if isinstance(d, str) and "," in d:
                        normalized_images.extend([x.strip() for x in d.split(",") if x.strip()])
                    elif d:
                        normalized_images.append(d.strip())
                for s in normalized_images:
                    conn.execute(
                        text("INSERT INTO houses_imgs (id, house_id, url) VALUES (:id, :house_id, :url)"),
                        {"id": str(uuid.uuid4()), "house_id": house_id, "url": s}
                    )

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="House not found.")
        return {"message": "House updated successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
@router.delete('/houses/{id}')
def delete_house(id: str):
    try:
        urls = []
        with engine.connect() as conn:
            urls += conn.execute(
                text("SELECT url FROM houses_imgs WHERE house_id = :id"),
                {"id": id}
            ).scalars().all()
            main = conn.execute(
                text("SELECT url FROM houses_main_imgs WHERE house_id = :id"),
                {"id": id}
            ).fetchone()
            if main:
                urls.append(main[0])

        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM houses_imgs WHERE house_id = :id"),
                {"id": id}
            )
            conn.execute(
                text("DELETE FROM houses_main_imgs WHERE house_id = :id"),
                {"id": id}
            )
            result = conn.execute(
                text("DELETE FROM Houses WHERE id = :id"),
                {"id": id}
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="House not found.")

        return {"message": "House and associated images deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
