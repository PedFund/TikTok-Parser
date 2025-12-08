from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# Импорт твоей функции из парсера
from parser import run_parser   # Если такой функции нет — мы её добавим на следующем шаге

app = FastAPI(
    title="TikTok Parser API",
    description="API для запуска TikTok-парсера",
    version="1.0.0"
)

# Разрешаем запросы откуда угодно (Google Sheets, браузер, и т.д.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "message": "TikTok Parser API работает. Используйте /run"}

@app.get("/run")
def run():
    """
    Запускает парсер и возвращает JSON.
    """
    try:
        data = run_parser()
        return {"status": "success", "count": len(data), "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/run_csv")
def run_csv():
    """
    Запускает парсер и возвращает CSV как файл.
    """
    try:
        data = run_parser()
        if not data:
            return Response("empty", media_type="text/plain")

        # Формируем CSV
        header = "url,description,views,likes,date,hashtags\n"
        rows = []

        for item in data:
            row = [
                item.get("url", ""),
                item.get("description", "").replace(",", " "),
                str(item.get("views", "")),
                str(item.get("likes", "")),
                item.get("date", ""),
                " ".join(item.get("hashtags", [])),
            ]
            rows.append(",".join(row))

        csv_data = header + "\n".join(rows)

        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=result.csv"}
        )

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
