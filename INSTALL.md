# Installation Guide for CL-SRS

## Quick Start (Automatic)

```bash
./start.sh
```

## Manual Installation

If you encounter issues with the automatic script, follow these steps:

### 1. Set up Python Environment

```bash
cd app/api
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Python Dependencies

For most systems:
```bash
pip install -r requirements-simple.txt
```

If you have compilation issues (especially on macOS with Python 3.13):
```bash
# Install pre-built wheels only
pip install --only-binary :all: -r requirements-simple.txt
```

### 3. Set up Environment Variables

```bash
cd ../..
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 4. Install UI Dependencies

```bash
cd app/ui
npm install
```

### 5. Run the Application

**Terminal 1 - Start API:**
```bash
cd app/api
source venv/bin/activate
python ../../run_api.py
```

**Terminal 2 - Start UI:**
```bash
cd app/ui
npm run dev
```

### 6. Access the Application

- UI: http://localhost:5173
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Troubleshooting

### Issue: `lxml` or `pydantic-core` compilation errors

**Solution:** Use `requirements-simple.txt` which avoids packages that need compilation.

### Issue: Network Error in UI

**Solution:** Make sure the API server is running on port 8000. Test with:
```bash
curl http://localhost:8000/health
```

### Issue: OpenAI API errors

**Solution:** Make sure your OpenAI API key is set in `.env`:
```
OPENAI_API_KEY=sk-...
```

### Issue: Port already in use

**Solution:** Kill existing processes:
```bash
# Find process using port 8000
lsof -i :8000
# Kill it
kill -9 <PID>

# Or use different port
API_PORT=8001 python run_api.py
```

## Dependencies Explained

The project uses simplified dependencies to avoid compilation:

- **fastapi/uvicorn**: Web framework and server
- **pydantic v1**: Data validation (v1 to avoid Rust compilation)
- **beautifulsoup4/html2text**: HTML processing without lxml
- **openai**: For LLM integration
- **httpx**: Async HTTP client
- **sqlalchemy/aiosqlite**: Database (SQLite only)

## System Requirements

- Python 3.9+ (3.11 recommended)
- Node.js 16+
- 2GB RAM minimum
- macOS, Linux, or Windows

## Support

If you continue to have issues:
1. Check the API logs: `tail -f /tmp/clsrs-api.log`
2. Run the test script: `./test_api.sh`
3. Make sure all ports are available (5173 for UI, 8000 for API)