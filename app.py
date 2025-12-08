from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import csv
import io

from parser import run_parser   # ВАЖНО: теперь run_parser ожидает query


app = FastAPI(
    title="TikTok Parser API",
    description="API для запуска TikTok-парсера",
    version="1.1.0"
)

# CORS для Google Sheets, браузера, Notion и т.д.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "message": "TikTok Parser API работает. Используйте /run?query=слово"}


# -------------------------------
#       JSON endpoint
# -------------------------------
@app.get("/run")
def run(query: str = Query(..., description="Поисковый запрос TikTok")):
    """
    Возвращает JSON данные
    """
    try:
        data = run_parser(query)
        return {"status": "success", "count": len(data), "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# -------------------------------
#       CSV endpoint
# -------------------------------
@app.get("/csv")
def run_csv(query: str = Query(..., description="Поисковый запрос TikTok")):
    """
    Возвращает CSV файл
    """
    try:
        data = run_parser(query)

        # Создаём CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output)

        # Заголовки
        writer.writerow(["url", "description", "views", "likes", "date", "hashtags", "author"])

        # Данные
        for item in data:
            writer.writerow([
                item.get("url", ""),
                item.get("description", "").replace(",", " "),
                item.get("views", 0),
                item.get("likes", 0),
                item.get("date", ""),
                item.get("hashtags", ""),
                item.get("author", "")
            ])

        output.seek(0)

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=result_{query}.csv"}
        )

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})



# -------------------------------
#       Local run
# -------------------------------
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
