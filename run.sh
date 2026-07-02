#!/bin/bash
cd "$(dirname "$0")"
./venv/bin/streamlit run ui/app.py --server.port 8501 --server.headless false
