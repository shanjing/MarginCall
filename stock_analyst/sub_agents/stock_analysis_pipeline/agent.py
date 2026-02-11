"""
Stock analysis pipeline - sequential pattern
"""

from google.adk.agents import SequentialAgent
from ..stock_data_collector import stock_data_collector
from ..report_synthesizer import report_synthesizer
from ..presenter import presenter

# The analysis pipeline - only runs when supervisor calls it
stock_analysis_pipeline = SequentialAgent(
    name="stock_analysis_pipeline",
    description="Full stock analysis: fetch data, synthesize report, present",
    sub_agents=[
        stock_data_collector,
        report_synthesizer,
        presenter,
    ],
)
