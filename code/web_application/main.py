import os

import bcrypt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

from database import Base, engine, get_db
from models import Recall, User
from routers.auth import router as auth_router
from routers.api_auth import router as api_auth_router
from routers.recalls import router as recalls_router
from routers.bench import router as bench_router

# this is my backend for grocery recall notices app.
# product name is the main field and the supplier is the second field.
# studend id 019146491
# my student id ends in 6491 so my port number is 8000 + (6491 mod 900) = 8191.
PORT_BASE = 8191

app = FastAPI(title="Grocery Supply and Recall Notices API", version="1.0.0")

SECRET_KEY = os.getenv("SECRET_KEY", "data260-s6491-dev-only-secret-key")

SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "900"))

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="s6491_session",
    https_only=True,
    same_site="lax",
    max_age=SESSION_MAX_AGE,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(api_auth_router)
app.include_router(recalls_router)
app.include_router(bench_router)

# This lets the browser load my html, css and js files.
app.mount("/static", StaticFiles(directory="static"), name="static")


Base.metadata.create_all(bind=engine)


def _seed():
    db = next(get_db())
    try:
        if db.query(Recall).count() == 0:
            db.add_all([
                Recall(
                    product_name="Trader Joe's Organic Frozen Blueberries, 16oz",
                    supplier="Trader Joe's",
                    email="rohan1@gmail.com",
                    description="Small tear near the top seal, frost buildup on the berries at the top of the bag.",
                    recall_type="Packaging / Seal Failure",
                ),
                Recall(
                    product_name="Safeway Signature Rotisserie Chicken",
                    supplier="Safeway Deli",
                    email="rohan1@gmail.com",
                    description="Served lukewarm from the hot case, pack date on the label was two days old.",
                    recall_type="Spoiled or Quality Issue",
                ),
                Recall(
                    product_name="Kirkland Signature Trail Mix, 4lb",
                    supplier="Costco Wholesale",
                    email="rohan1@gmail.com",
                    description="Ingredient panel does not list peanuts but whole peanuts are clearly in the bag.",
                    recall_type="Undeclared Allergen",
                ),
            ])

        if db.query(User).filter(User.email == "admin@s6491.com").first() is None:
            db.add(User(
                name="admin",
                email="admin@s6491.com",
                password_hash=bcrypt.hashpw(b"Recall@6491", bcrypt.gensalt()).decode(),
            ))

        db.commit()
    finally:
        db.close()


_seed()


import webbrowser

# This starts the server on my port and opens the page in my browser.
if __name__ == "__main__":
    webbrowser.open(f"http://localhost:{PORT_BASE}")
    uvicorn.run(app, host="0.0.0.0", port=PORT_BASE)
