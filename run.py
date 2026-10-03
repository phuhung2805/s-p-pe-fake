import uvicorn

if __name__ == "__main__":
    print("=======================================================================")
    print(" Starting Secure Multi-Vendor E-Commerce Platform Server...")
    print(" Local Web Portal:   http://localhost:8000")
    print(" Swagger API Docs:   http://localhost:8000/docs")
    print(" ReDoc API Docs:     http://localhost:8000/redoc")
    print("=======================================================================")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
