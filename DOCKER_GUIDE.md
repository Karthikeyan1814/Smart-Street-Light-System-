# Docker & GitHub Sharing Guide

This guide explains how to share this project with friends or teammates via GitHub without version mismatch issues, and how to run the entire system with Docker.

---

## 1. Does Docker Solve the Version Mismatch Problem?

**Yes, 100%.** This is the exact problem Docker was invented to solve.

### Why Version Errors Happen Without Docker
When you push code to GitHub:
- You **do not** push `.venv/` (Python virtual environment) or `node_modules/` because:
  - They contain hundreds of megabytes of compiled platform-specific binaries (Windows `.exe`/`.dll` vs Linux `.so` vs macOS `.dylib`).
  - They contain hardcoded local file paths for your specific machine.
- When your friend clones the repository without Docker:
  - They have to install Python and Node.js on their own machine.
  - If they have Python 3.12 or 3.13 while the code was built on Python 3.11, packages like `bcrypt` or `passlib` can fail to compile.
  - If they are on macOS or Linux while you are on Windows, system-level C dependencies might be missing.

### How Docker Completely Eliminates This
- **Self-Contained Container**: Docker creates an isolated Linux environment with the exact required Python version (`3.11-slim`) and Node.js version (`20-alpine`).
- **Identical Everywhere**: Whether your friend runs Windows 10/11, macOS (Intel/M-series Apple Silicon), or Ubuntu Linux, Docker runs the exact same container with identical dependencies.
- **Zero Host Setup**: Your friend does **not** need to install Python, pip, Node.js, or npm on their computer. They only need **Docker Desktop**.

---

## 2. What We Have Configured for You

We have already added all the necessary Docker files to this project:

| File | Purpose |
| :--- | :--- |
| `docker-compose.yml` | Starts both Backend (Port 5000) and Frontend (Port 5173) with a single command. |
| `backend/Dockerfile` | Packages Python 3.11, installs `backend/requirements.txt`, and runs FastAPI. |
| `frontend/Dockerfile` | Packages Node 20, installs npm dependencies, and runs the Vite dev server with Hot Module Reload. |
| `Dockerfile` | Multi-stage production container that builds the React frontend and serves it via the FastAPI backend on port 5000. |
| `.dockerignore` | Prevents local `.venv/`, `node_modules/`, and temporary caches from leaking into Docker images. |
| `.gitignore` | Configured so that virtual environments, local node_modules, and sensitive files are not pushed to GitHub. |
| `.env.example` | Template for environment variables. |

---

## 3. How to Push this Project to GitHub (Your Steps)

If you haven't initialized Git yet:

### Step 3.1: Open PowerShell in the project root
```powershell
cd D:\Smart-street-light-project
```

### Step 3.2: Initialize and commit
```powershell
# 1. Initialize git repository (if not already done)
git init

# 2. Add all files (the updated .gitignore will automatically exclude .venv and node_modules)
git add .

# 3. Commit your changes
git commit -m "Add Docker support and project files"
```

### Step 3.3: Push to your GitHub repository
Create a new empty repository on [GitHub](https://github.com/new), then run:
```powershell
# Link to your GitHub repository
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo-name>.git

# Push code
git push -u origin main
```

---

## 4. How Your Friend Runs the Project (Their Steps)

All your friend needs is **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** installed and running.

### Step 4.1: Clone the repository
```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

### Step 4.2: Start the entire project with one command
```bash
docker compose up --build
```
> **What happens automatically:**
> 1. Docker downloads the official lightweight Python and Node.js images.
> 2. It installs all Python packages in the backend container.
> 3. It installs all npm packages in the frontend container.
> 4. Both services start and link with each other.

### Step 4.3: Open the application in the browser
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Backend API**: [http://localhost:5000](http://localhost:5000)
- **Interactive API Documentation (Swagger)**: [http://localhost:5000/docs](http://localhost:5000/docs)

---

## 5. Helpful Docker Commands

### Run in the background (Detached mode)
```bash
docker compose up -d
```

### View live logs
```bash
docker compose logs -f
```

### View logs for backend or frontend specifically
```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### Stop the application
```bash
docker compose down
```

### Stop and wipe container data (Fresh clean start)
```bash
docker compose down -v
```

---

## 6. Alternative: Single-Container Unified Build

If you want to run the entire full stack (FastAPI serving the compiled React frontend) in a single container on port 5000:

```bash
# Build the unified image
docker build -t smart-street-light .

# Run the container
docker run -p 5000:5000 -v ${PWD}/backend/storage:/app/backend/storage smart-street-light
```

Access the complete dashboard at:
👉 **[http://localhost:5000/frontend/](http://localhost:5000/frontend/)**

