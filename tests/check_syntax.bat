@echo off
call conda activate goodq_zenml
cd L:\goodq4all
python cli\run_ingestion.py --help
