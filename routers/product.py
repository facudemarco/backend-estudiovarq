# from fastapi import APIRouter, HTTPException
# from models.product import Product
# from sqlalchemy import text
# from Database.dbGetConnection import engine 
# import uuid

# router = APIRouter()

# # Get all products

# @router.get('/products')

# def getProducts():
#     try:
#         with engine.begin() as connection:
#             result = connection.execute(
#                 text("SELECT * FROM Products"),
#             )
#             row = result.mappings().all()
#             if row is None:
#                 raise HTTPException(status_code=404, detail="Product not found.")
#             return row
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    
# # Filter products by id

# @router.get('/products/{id}')

# def getProductById(id: str):
#     try:
#         with engine.connect() as connection:
#             result = connection.execute(
#                 text("SELECT * FROM Products WHERE id = :id"),
#                 {"id": id}
#             )
#             row = result.mappings().first()
#             if row is None:
#                 raise HTTPException(status_code=404, detail="Product not found.")
#             return row
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # Filter products by periodo

# @router.get('/products/periodo/{periodo}')
# def getProductByPeriodo(periodo: str):
#     try:
#         with engine.connect() as connection:
#             result = connection.execute(
#                 text("SELECT * FROM Products WHERE periodo = :periodo"),
#                 {"periodo": periodo}
#             )
#             row = result.mappings().all()

#             if row is None:
#                 print(f"[INFO] Product not found with this periodo: {periodo}")
#                 raise HTTPException(status_code=404, detail="Product not found.")
            
#             return row

#     except Exception as e:
#         print(f"[ERROR] Error en /products/periodo/{periodo} -> {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")

# # Filter products by id in periodo

# @router.get('/products/{periodo}/{id}')

# def getProductByIdInPeriodo(periodo: str, id: str):
#     try:
#         with engine.connect() as connection:
#             result = connection.execute(
#                 text("SELECT * FROM Products WHERE periodo = :periodo AND id = :id"),
#                 {"periodo": periodo, "id": id}
#             )
#             row = result.mappings().first()
#             if row is None:
#                 raise HTTPException(status_code=404, detail="Product not found.")
#             return row
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# # Crear producto
# @router.post('/products/create_product')

# def createProduct(product: Product):
#     generated_id = str(uuid.uuid4())

#     query = text("""
#         INSERT INTO Products (
#             ID, destino, subtitulo, date, date2, date3, days, nights,
#             regimen, transporte, periodo, paquete, descripcion, moneda, precio,
#             adicional, image, desde, hotel, incluye, incluye2, incluye3, incluye4,
#             observaciones, observaciones2, observaciones3, itinerario, itinerario2,
#             itinerario3, itinerario4, itinerario5, itinerario6, itinerario7,
#             itinerario8, tarifas, tarifas2, tarifas3, tarifas4, tarifas5
#         ) VALUES (
#             :ID, :destino, :subtitulo, :date, :date2, :date3, :days, :nights,
#             :regimen, :transporte, :periodo, :paquete, :descripcion, :moneda, :precio,
#             :adicional, :image, :desde, :hotel, :incluye, :incluye2, :incluye3, :incluye4,
#             :observaciones, :observaciones2, :observaciones3, :itinerario, :itinerario2,
#             :itinerario3, :itinerario4, :itinerario5, :itinerario6, :itinerario7,
#             :itinerario8, :tarifas, :tarifas2, :tarifas3, :tarifas4, :tarifas5
#         )
#     """)

#     try:
#         with engine.begin() as conn:
#             conn.execute(query, {
#                 "ID": generated_id,
#                 "destino": product.destino,
#                 "subtitulo": product.subtitulo,
#                 "date": product.date,
#                 "date2": product.date2,
#                 "date3": product.date3,
#                 "days": product.days,
#                 "nights": product.nights,
#                 "regimen": product.regimen,
#                 "transporte": product.transporte,
#                 "periodo": product.periodo,
#                 "paquete": product.paquete,
#                 "descripcion": product.descripcion,
#                 "moneda": product.moneda,
#                 "precio": product.precio,
#                 "adicional": product.adicional,
#                 "image": product.image,
#                 "desde": product.desde,
#                 "hotel": product.hotel,
#                 "incluye": product.incluye,
#                 "incluye2": product.incluye2,
#                 "incluye3": product.incluye3,
#                 "incluye4": product.incluye4,
#                 "observaciones": product.observaciones,
#                 "observaciones2": product.observaciones2,
#                 "observaciones3": product.observaciones3,
#                 "itinerario": product.itinerario,
#                 "itinerario2": product.itinerario2,
#                 "itinerario3": product.itinerario3,
#                 "itinerario4": product.itinerario4,
#                 "itinerario5": product.itinerario5,
#                 "itinerario6": product.itinerario6,
#                 "itinerario7": product.itinerario7,
#                 "itinerario8": product.itinerario8,
#                 "tarifas": product.tarifas,
#                 "tarifas2": product.tarifas2,
#                 "tarifas3": product.tarifas3,
#                 "tarifas4": product.tarifas4,
#                 "tarifas5": product.tarifas5
#             })

#         return {"message": f"Product created successfully, ID: {generated_id}"}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# # Modificar producto
# @router.put('/products/{id}')
# def modProduct(id: str, product: Product):
#     query = text("""
#         UPDATE Products SET 
#             destino = :destino,
#             subtitulo = :subtitulo,
#             date = :date,
#             date2 = :date2,
#             date3 = :date3,
#             days = :days,
#             nights = :nights,
#             regimen = :regimen,
#             transporte = :transporte,
#             periodo = :periodo,
#             paquete = :paquete,
#             descripcion = :descripcion,
#             moneda = :moneda,
#             precio = :precio,
#             adicional = :adicional,
#             image = :image,
#             desde = :desde,
#             hotel = :hotel,
#             incluye = :incluye,
#             incluye2 = :incluye2,
#             incluye3 = :incluye3,
#             incluye4 = :incluye4,
#             observaciones = :observaciones,
#             observaciones2 = :observaciones2,
#             observaciones3 = :observaciones3,
#             itinerario = :itinerario,
#             itinerario2 = :itinerario2,
#             itinerario3 = :itinerario3,
#             itinerario4 = :itinerario4,
#             itinerario5 = :itinerario5,
#             itinerario6 = :itinerario6,
#             itinerario7 = :itinerario7,
#             itinerario8 = :itinerario8,
#             tarifas = :tarifas,
#             tarifas2 = :tarifas2,
#             tarifas3 = :tarifas3,
#             tarifas4 = :tarifas4,
#             tarifas5 = :tarifas5
#         WHERE ID = :id
#     """)

#     try:
#         with engine.begin() as conn:
#             result = conn.execute(query, {
#                 "id": id,
#                 "destino": product.destino,
#                 "subtitulo": product.subtitulo,
#                 "date": product.date,
#                 "date2": product.date2,
#                 "date3": product.date3,
#                 "days": product.days,
#                 "nights": product.nights,
#                 "regimen": product.regimen,
#                 "transporte": product.transporte,
#                 "periodo": product.periodo,
#                 "paquete": product.paquete,
#                 "descripcion": product.descripcion,
#                 "moneda": product.moneda,
#                 "precio": product.precio,
#                 "adicional": product.adicional,
#                 "image": product.image,
#                 "desde": product.desde,
#                 "hotel": product.hotel,
#                 "incluye": product.incluye,
#                 "incluye2": product.incluye2,
#                 "incluye3": product.incluye3,
#                 "incluye4": product.incluye4,
#                 "observaciones": product.observaciones,
#                 "observaciones2": product.observaciones2,
#                 "observaciones3": product.observaciones3,
#                 "itinerario": product.itinerario,
#                 "itinerario2": product.itinerario2,
#                 "itinerario3": product.itinerario3,
#                 "itinerario4": product.itinerario4,
#                 "itinerario5": product.itinerario5,
#                 "itinerario6": product.itinerario6,
#                 "itinerario7": product.itinerario7,
#                 "itinerario8": product.itinerario8,
#                 "tarifas": product.tarifas,
#                 "tarifas2": product.tarifas2,
#                 "tarifas3": product.tarifas3,
#                 "tarifas4": product.tarifas4,
#                 "tarifas5": product.tarifas5
#             })

#             if result.rowcount == 0:
#                 raise HTTPException(status_code=404, detail="Product not found.")

#         return {"message": "Product updated successfully"}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# # Eliminar producto
# @router.delete('/products/{id}')

# def delProducts(id: str):
#     query = text("DELETE FROM Products WHERE ID = :id")

#     try:
#         with engine.begin() as conn:
#             result = conn.execute(query, {"id": id})

#             if result.rowcount == 0:
#                 raise HTTPException(status_code=404, detail="Product not found.")

#         return {"message": "Product deleted successfully"}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")