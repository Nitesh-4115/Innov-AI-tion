import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json
import os
# Ensure current workspace is on path
sys.path.insert(0, os.path.abspath(os.getcwd()))
import models
from config import get_settings

engine = create_engine(get_settings().DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)
s = Session()
acts = s.query(models.AgentActivity).filter(models.AgentActivity.patient_id==3).order_by(models.AgentActivity.timestamp.desc()).all()
for a in acts:
    print('ID', a.id, 'action', a.action, 'is_successful', a.is_successful, 'input', a.input_data, 'output', a.output_data)
