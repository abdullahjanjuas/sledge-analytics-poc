"""Starts the dashboard. In PyCharm: right-click this file -> Run 'run_dashboard',
then open http://localhost:8501 in your browser. Stop it with the red square."""
import sys

from streamlit.web import cli as stcli

print("Dashboard starting... open http://localhost:8501 in your browser")
sys.argv = ["streamlit", "run", "dashboard.py", "--server.headless=true"]
sys.exit(stcli.main())
