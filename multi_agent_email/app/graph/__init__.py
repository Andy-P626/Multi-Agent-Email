# This file turns the 'agents' directory into a Python package,
# allowing the orchestrator to import all agent classes directly.

# Import all agent classes from their respective (assumed) modules
# within the 'agents' package.

from .intent_classifier import IntentClassifierAgent
from .retriever import RetrieverAgent
from .drafter import DrafterAgent
from .safety_reviewer import SafetyReviewerAgent
from .external_tool import ExternalToolAgent

# Optionally, define what gets exported when 'from agents import *' is used.
__all__ = [
    "IntentClassifierAgent",
    "RetrieverAgent",
    "DrafterAgent",
    "SafetyReviewerAgent",
    "ExternalToolAgent"
]