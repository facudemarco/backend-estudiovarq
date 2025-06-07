from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from sqlalchemy import text
from Database.dbGetConnection import engine
import uuid
import os
import shutil

router = APIRouter()

IMAGES_DIR = "/app/images"
DOMAIN_URL = "https://api-estudiovarq.iwebtecnology.com/images"

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
    main_image: UploadFile = File(..., description="Main image"),
    images: list[UploadFile] = File(default=[], description="Other images")
):
    generated_id = str(uuid.uuid4())
    try:
        if not os.path.exists(IMAGES_DIR):
            os.makedirs(IMAGES_DIR, exist_ok=True)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO Houses (id, title, houseType) VALUES (:id, :title, :houseType)"),
                {"id": generated_id, "title": title, "houseType": houseType}
            )
            # main image
            ext = os.path.splitext(main_image.filename or "file.jpg")[1]
            fname = f"{uuid.uuid4()}{ext}"
            path = os.path.join(IMAGES_DIR, fname)
            with open(path, "wb") as buf:
                shutil.copyfileobj(main_image.file, buf)
            url_main = f"{DOMAIN_URL}/{fname}"
            conn.execute(
                text("INSERT INTO houses_main_imgs (id, house_id, url) VALUES (:id, :house_id, :url)"),
                {"id": str(uuid.uuid4()), "house_id": generated_id, "url": url_main}
            )
            # other images
            for img in images:
                ext = os.path.splitext(img.filename or "file.jpg")[1]
                fname = f"{uuid.uuid4()}{ext}"
                path = os.path.join(IMAGES_DIR, fname)
                with open(path, "wb") as buf:
                    shutil.copyfileobj(img.file, buf)
                url = f"{DOMAIN_URL}/{fname}"
                conn.execute(
                    text("INSERT INTO houses_imgs (id, house_id, url) VALUES (:id, :house_id, :url)"),
                    {"id": str(uuid.uuid4()), "house_id": generated_id, "url": url}
                )
        return {"message": f"House created successfully, ID: {generated_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put('/houses/{id}')
async def update_house(
    id: str,
    title: str = Form(...),
    houseType: str = Form(...),
    main_image: UploadFile = File(None, description="New main image (optional)"),
    images: list[UploadFile] = File(default=[], description="Additional images")
):
    try:
        if not os.path.exists(IMAGES_DIR):
            os.makedirs(IMAGES_DIR, exist_ok=True)
        with engine.begin() as conn:
            res = conn.execute(
                text("UPDATE Houses SET title = :title, houseType = :houseType WHERE id = :id"),
                {"id": id, "title": title, "houseType": houseType}
            )
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="House not found.")
            if main_image:
                ext = os.path.splitext(main_image.filename or "file.jpg")[1]
                fname = f"{uuid.uuid4()}{ext}"
                path = os.path.join(IMAGES_DIR, fname)
                with open(path, "wb") as buf:
                    shutil.copyfileobj(main_image.file, buf)
                url_main = f"{DOMAIN_URL}/{fname}"
                conn.execute(
                    text("UPDATE houses_main_imgs SET url = :url WHERE house_id = :id"),
                    {"id": id, "url": url_main}
                )
            for img in images:
                ext = os.path.splitext(img.filename or "file.jpg")[1]
                fname = f"{uuid.uuid4()}{ext}"
                path = os.path.join(IMAGES_DIR, fname)
                with open(path, "wb") as buf:
                    shutil.copyfileobj(img.file, buf)
                url = f"{DOMAIN_URL}/{fname}"
                conn.execute(
                    text("INSERT INTO houses_imgs (id, house_id, url) VALUES (:id, :house_id, :url)"),
                    {"id": str(uuid.uuid4()), "house_id": id, "url": url}
                )
        return {"message": "House updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete('/houses/{id}')
def delete_house(id: str):
    try:
        with engine.connect() as conn:
            urls = list(conn.execute(
                text("SELECT url FROM houses_imgs WHERE house_id = :id"), {"id": id}
            ).scalars().all())
            main = conn.execute(
                text("SELECT url FROM houses_main_imgs WHERE house_id = :id"), {"id": id}
            ).fetchone()
            if main:
                urls.append(main[0])
        for u in urls:
            fname = u.split("/images/")[-1]
            fpath = os.path.join(IMAGES_DIR, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
        with engine.begin() as conn:
            res = conn.execute(text("DELETE FROM Houses WHERE id = :id"), {"id": id})
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="House not found.")
        return {"message": "House and associated images deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
