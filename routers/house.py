from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from models.houses import Houses
from sqlalchemy import text
from Database.dbGetConnection import engine 
import uuid
import os
import shutil

router = APIRouter()

IMAGES_DIR = "/app/images"
DOMAIN_URL = "https://api-estudiovarq.iwebtecnology.com/images"

# Get all houses
@router.get('/houses')
def getHouses():
    try:
        with engine.begin() as connection:
            result = connection.execute(text("SELECT * FROM Houses"))
            row = result.mappings().all()
            if row is None:
                raise HTTPException(status_code=404, detail="House not found.")
            return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Filter houses by id
@router.get('/houses/{id}')
def getHousesById(id: str):
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT * FROM Houses WHERE id = :id"),
                {"id": id}
            )
            row = result.mappings().first()
            if row is None:
                raise HTTPException(status_code=404, detail="House not found.")

            images_result = connection.execute(
                text("SELECT url FROM houses_imgs WHERE house_id = :id"),
                {"id": id}
            )
            images = [img[0] for img in images_result]
            row_dict = dict(row)
            row_dict["images"] = images
            return row_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Create House (con imágenes)
@router.post('/houses/create_house')
async def createHouse(
    title: str = Form(...),
    houseType: str = Form(...),
    images: list[UploadFile] = File(default=[])
):
    generated_id = str(uuid.uuid4())

    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Houses (id, title, houseType)
                    VALUES (:id, :title, :houseType)
                """),
                {"id": generated_id, "title": title, "houseType": houseType}
            )

            for img in images:
                print("IMAGES_DIR:", IMAGES_DIR)
                print("Exists?", os.path.exists(IMAGES_DIR))
                print("Absolute path:", os.path.abspath(IMAGES_DIR))

                if not os.path.exists(IMAGES_DIR):
                    os.makedirs(IMAGES_DIR, exist_ok=True)
                    
                ext = os.path.splitext(str(img.filename or "file.jpg"))[1]
                filename = f"{uuid.uuid4()}{ext}"
                filepath = os.path.join(IMAGES_DIR, filename)
                with open(filepath, "wb") as buffer:
                    shutil.copyfileobj(img.file, buffer)
                public_url = f"{DOMAIN_URL}/{filename}"
                conn.execute(
                    text("""
                        INSERT INTO houses_imgs (id, house_id, url)
                        VALUES (:id, :house_id, :url)
                    """),
                    {"id": str(uuid.uuid4()), "house_id": generated_id, "url": public_url}
                )
        return {"message": f"House created successfully, ID: {generated_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Modify House
@router.put('/houses/{id}')
async def modHouse(
    id: str,
    title: str = Form(...),
    houseType: str = Form(...),
    images: list[UploadFile] = File(default=[])
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
                {"id": id, "title": title, "houseType": houseType}
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="House not found.")
            # Guardar imágenes nuevas si hay
            for img in images:
                ext = os.path.splitext(str(img.filename or "file.jpg"))[1]
                filename = f"{uuid.uuid4()}{ext}"
                filepath = os.path.join(IMAGES_DIR, filename)
                with open(filepath, "wb") as buffer:
                    shutil.copyfileobj(img.file, buffer)
                public_url = f"{DOMAIN_URL}/{filename}"
                conn.execute(
                    text("""
                        INSERT INTO houses_imgs (id, house_id, url)
                        VALUES (:id, :house_id, :url)
                    """),
                    {"id": str(uuid.uuid4()), "house_id": id, "url": public_url}
                )
        return {"message": "House updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Delete house (y borra imágenes físicas)
@router.delete('/houses/{id}')
def delHouse(id: str):
    try:
        with engine.connect() as conn:

            result = conn.execute(
                text("SELECT url FROM houses_imgs WHERE house_id = :id"),
                {"id": id}
            )
            image_urls = [row[0] for row in result]
        for url in image_urls:
            filename = url.split("/images/")[-1]
            path = os.path.join(IMAGES_DIR, filename)
            if os.path.exists(path):
                os.remove(path)

        with engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM Houses WHERE id = :id"),
                {"id": id}
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="House not found.")
        return {"message": "House and associated images deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")