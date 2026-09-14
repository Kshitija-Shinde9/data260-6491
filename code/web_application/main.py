from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import uvicorn

# this is my backend for grocery recall notices app.
# product name is the main field and the supplier is the second field.
# studend id 019146491
# my student id ends in 6491 so my port number is 8000 + (6491 mod 900) = 8191.
PORT_BASE = 8191

app = FastAPI(title="Grocery Supply and Recall Notices API", version="1.0.0")

# This lets the browser load my html, css and js files.
app.mount("/static", StaticFiles(directory="static"), name="static")


# This is what one saved recall notice looks like.
class RecallNotice(BaseModel):
    id: int
    product_name: str      # primary field
    supplier: str          # secondary field
    email: str = ""
    description: str = ""
    recall_type: str = ""


# This is what the form sends when I add a new notice.
class RecallCreate(BaseModel):
    product_name: str
    supplier: str
    email: str = ""
    description: str = ""
    recall_type: str = ""


# This is what the form sends when I change a notice.
class RecallUpdate(BaseModel):
    product_name: str
    supplier: str


# My notices are kept in this list, so they disappear when I stop the server.
recalls: List[RecallNotice] = [
    RecallNotice(
        id=1,
        product_name="Trader Joe's Organic Frozen Blueberries, 16oz",
        supplier="Trader Joe's",
        email="rohan1@gmail.com",
        description="Small tear near the top seal, frost buildup on the berries at the top of the bag.",
        recall_type="Packaging / Seal Failure",
    ),
    RecallNotice(
        id=2,
        product_name="Safeway Signature Rotisserie Chicken",
        supplier="Safeway Deli",
        email="rohan1@gmail.com",
        description="Served lukewarm from the hot case, pack date on the label was two days old.",
        recall_type="Spoiled or Quality Issue",
    ),
    RecallNotice(
        id=3,
        product_name="Kirkland Signature Trail Mix, 4lb",
        supplier="Costco Wholesale",
        email="rohan1@gmail.com",
        description="Ingredient panel does not list peanuts but whole peanuts are clearly in the bag.",
        recall_type="Undeclared Allergen",
    ),
]


@app.get("/")
async def read_root():
    """Show my main web page."""
    return FileResponse("static/index.html")


@app.get("/api/recalls", response_model=List[RecallNotice])
async def get_recalls(response: Response, search: str = ""):
    """Q4 - send back all the notices, or only the ones that match the search word."""
    # This stops the browser from showing me an old copy of the list.
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    term = search.strip().lower()
    if not term:
        return recalls

    # I make both sides lowercase so searching COSTCO also finds Costco.
    return [
        recall for recall in recalls
        if term in recall.product_name.lower() or term in recall.supplier.lower()
    ]


@app.delete("/api/recalls/highest", status_code=204)
async def delete_highest_recall():
    """Q3 - delete the notice that has the biggest ID number."""
    # This must stay above the other delete below, or the word "highest" is read as a number and it breaks.
    if not recalls:
        raise HTTPException(status_code=404, detail="There are no recall notices to delete")

    highest = max(recalls, key=lambda recall: recall.id)
    recalls.remove(highest)

    print(f"Deleted highest-ID recall notice: {highest}")
    return None


@app.get("/api/recalls/{recall_id}", response_model=RecallNotice)
async def get_recall(recall_id: int):
    """Send back one notice when I give its ID."""
    recall = next((recall for recall in recalls if recall.id == recall_id), None)
    if not recall:
        raise HTTPException(status_code=404, detail="Recall notice not found")
    return recall


@app.post("/api/recalls", response_model=RecallNotice, status_code=201)
async def create_recall(recall_data: RecallCreate):
    """Q1 - add a new notice using what the user typed into the form."""
    if not recall_data.product_name.strip():
        raise HTTPException(status_code=400, detail="Product name is required")
    if not recall_data.supplier.strip():
        raise HTTPException(status_code=400, detail="Supplier / brand is required")

    # The new ID is one bigger than the biggest ID I already have.
    new_id = max([recall.id for recall in recalls], default=0) + 1
    new_recall = RecallNotice(id=new_id, **recall_data.model_dump())
    recalls.append(new_recall)

    print(f"Created recall notice: {new_recall}")
    return new_recall


@app.put("/api/recalls/{recall_id}", response_model=RecallNotice)
async def update_recall(recall_id: int, recall_data: RecallUpdate):
    """Q2 - change the product name and supplier of one notice, the question asks for ID 1."""
    recall = next((recall for recall in recalls if recall.id == recall_id), None)

    if not recall:
        raise HTTPException(status_code=404, detail="Recall notice not found")

    if not recall_data.product_name.strip():
        raise HTTPException(status_code=400, detail="Product name is required")
    if not recall_data.supplier.strip():
        raise HTTPException(status_code=400, detail="Supplier / brand is required")

    recall.product_name = recall_data.product_name
    recall.supplier = recall_data.supplier

    print(f"Updated recall notice: {recall}")
    return recall


@app.delete("/api/recalls/{recall_id}", status_code=204)
async def delete_recall(recall_id: int):
    """Delete one notice when I give its ID."""
    recall_index = next(
        (index for index, recall in enumerate(recalls) if recall.id == recall_id),
        None,
    )

    if recall_index is None:
        raise HTTPException(status_code=404, detail="Recall notice not found")

    deleted_recall = recalls.pop(recall_index)
    print(f"Deleted recall notice: {deleted_recall}")
    return None


import webbrowser

# This starts the server on my port and opens the page in my browser.
if __name__ == "__main__":
    webbrowser.open(f"http://localhost:{PORT_BASE}")
    uvicorn.run(app, host="0.0.0.0", port=PORT_BASE)
